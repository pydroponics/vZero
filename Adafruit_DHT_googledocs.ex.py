#!/usr/bin/python

import subprocess
import re
import sys
import time
import datetime
import gspread
import serial, RPIO

while(True):
    output = subprocess.check_output(["./Adafruit_DHT", "22", "18"]);
    print "dht output is : %s" % output
    matches = re.search("Temp =\s+([0-9.]+)", output)
    if (not matches):
        time.sleep(.5)
    	continue
    temp = float(matches.group(1))
      
# search for humidity printout
    matches = re.search("Hum =\s+([0-9.]+)", output)
    if (not matches):
    	time.sleep(.5)
    	continue
    humidity = float(matches.group(1))
    
    print "Temperature: %.1f C" % temp
    print "Humidity:    %.1f %%" % humidity