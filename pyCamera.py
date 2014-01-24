import cv2
import numpy as np
import math

#values for real plant
#hueL, hueH = 35, 59
#satL, satH = 72, 177
#valL, valH = 81, 171


def getCameraData():
	#values for fake plant
	hueL, hueH = 0, 109
	satL, satH = 0, 255
	valL, valH = 0, 255

	DEBUG = False
	WEBCAM = True	
	min_height = 6.5
	screen_height_inches_value = 17.75 
	#Height of Camera (inches) FROM top of base
	height_of_camera = 14.5
	#Distance of plant (inches)
	distance_of_plant = 21.5
	#Camera Field Of View (degrees)
	camera_FOV = 52
	if WEBCAM:
		camera = cv2.VideoCapture(0)
		for i in xrange(30):
			retval, im = camera.read()
	else:
		im = cv2.imread("Images/Webcam.png")
	if DEBUG:
		cv2.namedWindow('window', cv2.CV_WINDOW_AUTOSIZE)
		#Show Original Image
		cv2.imshow('window', im)
		cv2.waitKey(0)
		#print "SHAPE:", im.shape
	hsv = cv2.cvtColor(im,cv2.COLOR_BGR2HSV)
	COLOR_MIN = np.array([hueL, satL, valL], np.uint8)
	COLOR_MAX = np.array([hueH, satH, valH], np.uint8)
	filtered_hsv = cv2.inRange(im, COLOR_MIN, COLOR_MAX)
	if DEBUG:
		cv2.imshow('window', filtered_hsv)	
		cv2.waitKey(0)
	contours,hierarchy = cv2.findContours(filtered_hsv,cv2.RETR_TREE,cv2.CHAIN_APPROX_SIMPLE)
	mask = np.zeros(filtered_hsv.shape, np.uint8)
	largest_contour = 0  
	largest_contour_area = 0
	i = 0
	for contour in contours:
		#print "CURRENT AREA:", largest_contour_area, "--- NEW AREA:", cv2.contourArea(contour) 
		if cv2.contourArea(contour) > largest_contour_area:
			largest_contour_area = cv2.contourArea(contour)
			largest_contour = i
			#print "largest_contour_area:", largest_contour_area, "--- largest_contour:", largest_contour
		i+=1
	#print largest_contour, "LARGEST CONTOUR"	
	#print cv2.contourArea(contours[largest_contour]), "AREA LARGE CONTOUR"
	cv2.drawContours(mask,[contours[largest_contour]],-1,(255),-1)
	if DEBUG:
		cv2.imshow('window', mask)
		cv2.waitKey(0)	
	#Determine Plant Pixel Height
	#By grabbing all the values that includes the plant
	#LargestValue - SmallestValue = Plant Height (Pixels)
	yVals = []
	maskT = cv2.transpose(mask)
	#print "MASKT:", maskT.shape
	for y in range(maskT.shape[0]):
		#print "Y:", y, "ANY:", any(maskT[y])	
		if any(maskT[y]):
			yVals.append(639-y)
	yVals.sort()
	#print "yVALS:", yVals
	plant_height_pixels = yVals[-1]#-yVals[0]
	screen_height_inches = 2*distance_of_plant*math.tan(camera_FOV*(math.pi/180)/2)
	screen_height_inches = screen_height_inches_value 
	screen_height_pixels = im.shape[1]
	#print screen_height_inches, screen_height_pixels
	height_per_pixel = screen_height_inches/screen_height_pixels
	#print height_per_pixel
	plant_height_inches = plant_height_pixels*height_per_pixel
	plant_height_millimeters = (plant_height_inches+min_height)*25.4
	if DEBUG:
		#Print out calculations
		#print "Plant Distance(in) :", distance_of_plant
		print "yHigh =",yVals[-1],"; yLow =",yVals[0]
		#print "Plant Height(pixels) :", plant_height_pixels
		#Calculations to figure out height (inches) per pixel
		print "screen_height_inches",screen_height_inches
		print "shape", im.shape[0], im.shape[1]
		print "height_per_pixel", height_per_pixel
		print "Plant Height(inches) :", plant_height_inches+min_height

	cv2.destroyAllWindows()
	return plant_height_millimeters-50.8
