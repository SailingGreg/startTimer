#
#
#

import time
import RPi.GPIO as GPIO

#GPIO.setmode(GPIO.BOARD)
GPIO.setmode(GPIO.BCM)
GPIO.setup(22, GPIO.OUT) # PIN 12 -> GPIO 18

cnt = 100000

stime = time.time()
print (time.time())
#for i in range (1, cnt, 1):
    #print ("%d", i)

for i in range (1, 17, 1):
    print (i)
    GPIO.output(22, True)
    time.sleep(0.1)
    GPIO.output(22, False)
    time.sleep(1/i)

ftime = time.time()
print (time.time())
diff = ftime - stime
print ("Finish", diff, diff/cnt)

GPIO.cleanup()

