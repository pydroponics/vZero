#!/usr/bin/python
# Pydroponics Control
# Author: Stark Pister
# 5/11/13

import threading
import re
import sys
import subprocess
import serial
import time
import io
import string
import pyCamera
import psycopg2
import RPIO
import logging

#========================#
#  Function Definitions  #
#========================#

def initializeThreads():
    """ Initializes the threads. Returns thread list. """
    threadList = []
    fanThread = threading.Thread(name = 'Fan Thread',
                                 target = fanStartup)
    threadList.append(fanThread)
    airPumpThread = threading.Thread(name = 'Air Pump Thread',
                                     target = airPumpOn)
    threadList.append(airPumpThread)
    #phThread = sensorThread(name = 'pH Data Thread',
    #                        target = phGetValue,
    #                        period = 60)
    #threadList.append(phThread)
    tdsThread = sensorThread(name = 'TDS Data Thread',
                             target = tdsGetValue,
                             period = 60)
    threadList.append(tdsThread)
    dhtThread = sensorThread(name = 'DHT Data Thread',
                             target = dhtGetValue,
                             period = 60)
    threadList.append(dhtThread)
    camThread = threading.Thread(name = 'Cam Data Thread',
                                 target = heightGetValue)
    threadList.append(camThread)
    lightThread = scheduleThread(name = 'Light Schedule Thread',
                                 period = 86400, 
                                 duration = 50400,
                                 on = 'L1',
                                 off = 'L0',
                                 table = 'user_light') #86400 and 50400 real defaults
    threadList.append(lightThread)
    pumpThread = scheduleThread(name = 'Pump Schedule Thread',
                                period = 21600,
                                duration = 600,
                                on = 'W1',
                                off = 'W0',
                                table = 'user_water') #21600 and 600 real defaults
    threadList.append(pumpThread)
    return threadList

def serialRequest(command = 'Invalid Command'):
    """ Send command to UART. Returns response.  """
    logger = logging.getLogger("Main.Serial")
    uartLock.acquire()
    ser.write(command + '\n')
    response = ser.readline()
    print ('Sent ' + command + ' - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    uartLock.release()
    if command == 'L1':
        lightStartup.set()
    print ('Received ' + response + ' - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    return response

def writeDatabase(*args, **kwargs):
    """ Send data to writeTable. """
    logger = logging.getLogger("Main.Database")
    writeArgs = [time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()),]
    writeString = "INSERT INTO " + kwargs.get('writeTable') + " VALUES (%s"
    for index, writeValue in enumerate(args):
        writeArgs.append(writeValue)
        writeString += ", %s"
    writeString += ")"
    print ('Sending ' + writeString + ' - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    dbLock.acquire()
    dbCursor = dbConnection.cursor()
    dbCursor.execute(writeString, writeArgs)
    dbConnection.commit()
    dbCursor.close()
    dbLock.release()

def readDatabase(**kwargs):
    logger = logging.getLogger("Main.Database")
    readString = "SELECT * FROM " + kwargs.get('readTable') + " ORDER BY timestamp DESC LIMIT 1"
    dbLock.acquire()
    dbCursor = dbConnection.cursor()
    dbCursor.execute(readString)
    readArgs = dbCursor.fetchone()
    dbCursor.close()
    dbLock.release()
    print ("Received {} - {}".format(readArgs[1:],time.strftime("%m/%d/%Y %H:%M:%S", time.localtime())))
    return readArgs[1:]

def phGetValue():
    """ Get temp, get pH, update database, adjust pH. """
    phValue = serialRequest('PV')
    phValue = float(phValue)
    writeDatabase(phValue,
                  writeTable = 'ph')
    phRange = readDatabase(readTable = 'user_ph')
    if phValue > phRange[0]: #phMax
        response = serialRequest('P-999')
        writeDatabase(False,True,False,False,
                      writeTable = 'solenoids')
    elif phValue < phRange[1]: #phMin
        response = serialRequest('P+999')
        writeDatabase(True,False,False,False,
                      writeTable = 'solenoids')

def tdsGetValue():
    """ Get temp, get tds, update database, adjust tds. """
    response = serialRequest('TV')
    conductivity,tdsValue,salinity = response.split(',')
    tdsValue = float(tdsValue)
    writeDatabase(tdsValue,
                  writeTable = 'tds')
    tdsRange = readDatabase(readTable = 'user_tds')
    if tdsValue > tdsRange[0]: #tdsMax
        response = serialRequest('T-999')
        writeDatabase(False,False,False,True,
                      writeTable = 'solenoids')
    elif tdsValue < tdsRange[1]: #tdsMin
        response = serialRequest('T+999')
        writeDatabase(False,False,True,False,
                      writeTable = 'solenoids')

def dhtGetValue():
    """ Get air temp, humid, update database, adjust fans/dehumidifier. """
    airTemp, humidity = getDhtData()
    writeDatabase(airTemp,
                  humidity,
                  writeTable = 'atmosphere')
    ranges = readDatabase(readTable = 'user_atmosphere')
    if airTemp > ranges[0]+4: #airTempMax
        response = serialRequest('FE200')
        response = serialRequest('FI200')
        response = serialRequest('FH200')
    elif airTemp > ranges[0]+2: #airTempMax
        response = serialRequest('FE150')
        response = serialRequest('FI150')
        response = serialRequest('FH150')
    elif airTemp > ranges[0]: #airTempMax
        response = serialRequest('FE100')
        response = serialRequest('FI100')
        response = serialRequest('FH100')
    elif airTemp < ranges[1]: #airTempMin
        response = serialRequest('FE30')
        response = serialRequest('FI30')
        response = serialRequest('FH30')
    if humidity > ranges[2]: #humidityMax
        response = serialRequest('D')
    elif airTemp < ranges[3]: #humidityMin
        response = "Low Humidity"

def heightGetValue():
    """ Get plant, lamp height, update database, adjust height. """
    lightStartup.wait()
    plantHeight = pyCamera.getCameraData()
    lampHeight = serialRequest('LH')
    writeDatabase(plantHeight,
                  lampHeight, 
                  writeTable = 'height')
    heightDiff = readDatabase(readTable = 'user_height')
    desiredLampHeight = plantHeight + heightDiff[0]
    difference = abs(float(lampHeight) - desiredLampHeight)
    shiftDistance = "%d" % (difference) 
    if lampHeight > desiredLampHeight:
        response = serialRequest('L-' + shiftDistance)
    elif lampHeight < desiredLampHeight:
        response = serialRequest('L+' + shiftDistance)
    lightStartup.clear()
    heightGetValue()

def getDhtData():
    """ Query DHT. Return air temp, humidity. """
    while (1):
        output = subprocess.check_output(["./Adafruit_DHT", "22", "18"]);
        matches = re.search("Temp =\s+([0-9.]+)", output)
        if (not matches):
            continue
        airTemp = float(matches.group(1))
        matches = re.search("Hum =\s+([0-9.]+)", output)
        if (not matches):
            continue
        humidity = float(matches.group(1))
        logger = logging.getLogger("Main.DHT")
        print ("Temperature: %.1f C" % airTemp) 
        print ("Humidity:    %.1f %%" % humidity) 
        break
    return airTemp, humidity

def airPumpOn():
    logger = logging.getLogger("Main.Startup")
    print ('Air Pump On - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    response = serialRequest('A1')

def lightHeightReset():
    logger = logging.getLogger("Main.Startup")
    print ('Light Height Reset - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    response = serialRequest('LR')

def fanStartup():
    logger = logging.getLogger("Main.Startup")
    print ('Fan Startup - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
    response = serialRequest('FE60')
    response = serialRequest('FI60')
    response = serialRequest('FH60')
    

#========================#
#   Class Definitions    #
#========================#

class sensorThread(threading.Thread):
    """ Run 'target' every 'period'. Print 'name' and time. """
    def __init__(self, name=None, target=None, period = 60):
        threading.Thread.__init__(self, name=name)
        self.target = target
        self.period = period
    def run(self):
        self.runNext = threading.Timer(self.period, self.run)
        self.runNext.start()
        logger = logging.getLogger("Main.Sensor")
        print (self.name + ' - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
        self.target()

class scheduleThread(threading.Thread):
    """ 'on' every 'period'. 'off' after 'duration'. Print 'name' and time. """
    def __init__(self, name=None, period = 86400, duration = 60, on = None, off = None, table = None):
        threading.Thread.__init__(self, name=name)
        self.period = period
        self.duration = duration
        self.on = on
        self.off = off
        self.table = table
    def run(self):
        self.period, self.duration = readDatabase(readTable = self.table)
        self.runNext = threading.Timer(self.period, self.run)
        self.runNext.start()
        logger = logging.getLogger("Main.Schedule")
        print (self.name + ' - ' + time.strftime("%m/%d/%Y %H:%M:%S", time.localtime()))
        response = serialRequest(self.on)
        self.endCycle = threading.Timer(self.duration, serialRequest, [self.off])
        self.endCycle.start()

#========================#
#          Main          #
#========================#
        
# Locks and Serial 
lightStartup = threading.Event()
uartLock = threading.Lock()
dbLock = threading.Lock()
ser = serial.Serial(port = '/dev/ttyACM0',
                    baudrate = 38400,
                    timeout = 5)
dbConnection = psycopg2.connect(host = "web377.webfaction.com",
                                database = "hydrodata",
                                user = "pydroponics",
                                password = "AutoHydro")
logger = logging.getLogger("Main")
logger.setLevel(logging.DEBUG)
ch = logging.FileHandler('Logfiles/Pydroponics.log')
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

threadList = initializeThreads()

lightHeightReset() # Reset light to top position.
for thread in threadList:
    thread.start()
    time.sleep(2)
