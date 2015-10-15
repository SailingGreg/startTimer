#!/usr/bin/env python3

#
# Version 0.5 21st July 2015
#
# 0.1 - the initial version which used shell to control GPIO pin 17
# 0.2 - uses file io to control GPIO pin 17 so there no 'shelling'
# 0.3 - fixed timing loop and extended functional logic 
# 0.4 - added threading for control of the the external relay
# 0.5 - changed time to 1.5 seconds via g_horn_time
# 0.6 - allow horn_time to be specified by file horn_time.conf
#

import sys
import subprocess
import time
import datetime
import queue
from time import localtime, strftime, sleep
import threading
#from threading import Timer
import pifacecad

PY3 = sys.version_info[0] >= 3
if not PY3:
    print("startTimer only works with `python3`.")
    sys.exit(1)

switchlistener = 0
# global flags
g_horn_time_def = 1.5 # number of seconds to sound the horn
g_horn_time = 1.5 # number of seconds to sound the horn
g_horn = 0
g_running = 1 # loop until exit
g_started = 0 # not started the count
g_stop_timer = 5 # not started the count
g_timer_started = 0
g_race_started = 0 # has the race started?
g_def_time = 300
g_start_time = 300 # 5 minutes
g_fileid = 0
ONE_MIN = 60
FOUR_MINS = 4 * ONE_MIN
ltime = localtime() # the local time

# define the 'commands'
TURN_ON = 1
TURN_OFF = 0
#TURN_ON = "echo '1' > /sys/class/gpio/gpio17/value"
#TURN_OFF = "echo '0' > /sys/class/gpio/gpio17/value"


# routine that is run as a thread to control external relay
def Sound_horn():
    while (True):
        delay = Horn_queue.get()
        g_fileid.write("1\n") # turn external device on
        time.sleep (delay)
        g_fileid.write("0\n") # and turn it off
        Horn_queue.task_done()
        time.sleep (0.3) # wait 1/3 sec so there is a definite 'gap' between execution


# functions to run the commands - cmd would be TURN_ON or TURN_OFF
def run_cmd(cmd):
    #return subprocess.check_output(cmd, shell=True).decode('utf-8')
    if (cmd == TURN_ON):
       g_fileid.write("1\n")
    else:
       g_fileid.write("0\n")

#
# uses the toggle switch on the back of the unit - has guard condition so no exit if count started
# intention is to extend this with menu (one option - exit) so that horn duraction can be changed
#
def button_menu(event):
    global g_running
    global g_started

    if g_started == 0: # if stopped/reset then
        g_running = 0 # stop, that is exit for now

#
# note screen update calls removed as there appeared to be a race condition on the interrupts
# this button could be used for general recalls in the final system
#
def button_recall(event):
    global g_running
    global g_started
    global g_horn
    #cad.lcd.clear()
    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write("Stop") # str(event.pin_num))
    Horn_queue.put(g_horn_time)
    #if g_started == 1:
       # sound horn should also put a guard here as we should only allow this if we have started!
       # if we haven't started this could be used for AP
       #run_cmd(TURN_ON)
       #g_horn = 1
    #else:
       #g_running = 0 # stop, that is exit for now

# start or stop the start timer
def button_start_stop(event):
    global g_started
    global g_timer_started
    global g_horn

    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if g_started == 0:
       g_started = 1
       g_stop_timer = 5 # reset to ensure it 5 seconds
       if (g_timer_started == 0): # have pressed the start for the first time
           g_timer_started = 1
           #run_cmd(TURN_ON)
           Horn_queue.put(g_horn_time)
           #g_horn = 1
    else:
       g_started = 0

# if stopped reset count
def button_reset(event):
    global g_running
    global g_start_time
    global g_stop_timer
    global g_timer_started
    global g_race_started

    if g_started == 0:
       g_race_started = 0
       g_timer_started = 0
       g_stop_timer = 5
       g_start_time = g_def_time

def button_incr(event):
    global g_start_time
    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if (g_started == 0 and g_start_time < g_def_time * 3):
       g_start_time = g_start_time + 300 # add 5 minutes
       #update_display()

def button_decr(event):
    global g_start_time
    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if (g_started == 0 and g_start_time >= g_def_time * 2):
       g_start_time = g_start_time - 300 # sub 5 minutes
       #update_display()

# display the current count and time
def update_display():
    global ltime
    global g_race_started
    #cad.lcd.clear()
    t_hr = int(g_start_time/3600)
    t_min = int((g_start_time - (t_hr * 3600))/60)
    t_sec = int(g_start_time - (t_hr * 3600) - (t_min * 60))
    d = datetime.datetime (1970, 1, 1, t_hr, t_min, t_sec)
    #lt = localtime()
    cad.lcd.set_cursor(0,0)
    if (g_started == 0 and g_race_started == 0):
            cad.lcd.write("Start: {:%M:%S}   ".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
    if (g_started == 1):
        cad.lcd.set_cursor(0,0)
        if (g_race_started == 1):
            cad.lcd.write("Race : {:%H:%M:%S}".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
        else:
            cad.lcd.write("Start: {:%M:%S}   ".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
    cad.lcd.set_cursor(0,1)
    cad.lcd.write("Time : " + strftime("%H:%M:%S", ltime))
    #cad.lcd.write("Time : " + strftime("%H:%M:%S", localtime()))

def init():
    global switchlistener
    global g_fileid
    #global cad
    #cad = pifacecad.PiFaceCAD()
    cad.lcd.blink_off()
    cad.lcd.cursor_off()
    cad.lcd.backlight_on()

 
    # open for read/write non-buffered
    g_fileid = open ("/sys/class/gpio/gpio17/value", "r+", 1)
    # define the listener
    switchlistener = pifacecad.SwitchEventListener(chip=cad)

    # register the button 0 = start/stop, 1 = reset, 2 = incr, 3 = decr, 4 = exit
    switchlistener.register(0, pifacecad.IODIR_FALLING_EDGE, button_start_stop)
    switchlistener.register(1, pifacecad.IODIR_FALLING_EDGE, button_incr)
    switchlistener.register(2, pifacecad.IODIR_FALLING_EDGE, button_decr)
    switchlistener.register(3, pifacecad.IODIR_FALLING_EDGE, button_reset)
    switchlistener.register(4, pifacecad.IODIR_FALLING_EDGE, button_recall)
    switchlistener.register(5, pifacecad.IODIR_FALLING_EDGE, button_menu)

    # ensure external signal is off
    run_cmd(TURN_OFF)

    # start the listeners
    switchlistener.activate()


# main()
if __name__ == "__main__":

    # define the thread for external control and related queue
    Horn_queue = queue.Queue()
    t = threading.Thread(target=Sound_horn)
    t.daemon = True # note that this is not deamon!
    t.start()

    # check horn time
    try:
        hf = open("/home/pi/startTimer/horn_time.conf", mode="r")
        str = hf.readline()
        hf_val = float(str.rstrip('\n')) # remove newline
        if hf_val > 0.0:
            g_horn_time = hf_val
        hf.close()
    except IOError:
        g_horn_time = g_horn_time_def

    #print ("Using ", g_horn_time)

    # initialise display etc
    cad = pifacecad.PiFaceCAD()
    init()

    # note the current time before entering loop and increment it by 1 second
    next_call = time.time()
    next_call = next_call + 1 # 1 second

    # while loop - display time
    while (g_running == 1):
       # need to extend this to allow for a 'long' sound, that is a couple of seconds
       if g_horn > 0:
          g_horn = g_horn - 1
          if (g_horn == 0):
              run_cmd(TURN_OFF)

       if (g_timer_started == 1 and g_race_started == 0): # decrement the seconds
          if (g_started == 1): # if counting
              g_start_time -= 1
       elif (g_timer_started == 1 and g_race_started == 1):
          g_start_time += 1
          if (g_started == 0): # counting stopped
              g_stop_timer = g_stop_timer - 1
              if (g_stop_timer == 0):
                  g_started = 1 # restart the display
                  g_stop_timer = 5 # reset the count

       update_display()

       if (g_race_started == 0 and (g_start_time == FOUR_MINS or g_start_time == ONE_MIN or g_start_time == 0)):
          #run_cmd(TURN_ON)
          if (g_start_time == ONE_MIN):
              #g_horn = 2 # long sound
              Horn_queue.put(2 * g_horn_time)
          else:
              #g_horn = 1 # standard sound
              Horn_queue.put(g_horn_time)

       if (g_start_time == 0): # time to start!
          g_race_started = 1


       # this is the tricky bit we increment the time and once we've slept we check the time so that we know what 1 second will be
       # this removes the 'cost' of the display updates and ensures that we only sleep till the next second and not possibly longer
       # but this still results in a drift 2-3 seconds in an hour so the count gets out of step with the 'time'

       # guard condition for IOError 22 doesn't occur if the code execution is unnormally long
       if ((next_call - time.time()) > 0.0):
           time.sleep(next_call - time.time())

       next_call = time.time()
       next_call = next_call + 1 # 1 second
       ltime = localtime()

    # reset the display so cursor at left of display
    #cad.lcd.clear()
    #cad.lcd.write("\nDemo finished.")
    #sleep(1)

    # tidyup
    switchlistener.deactivate()

    cad.lcd.clear()
    cad.lcd.display_off()
    cad.lcd.backlight_off()
    # close the GPIO control file
    g_fileid.close()

    # ensure queue drained
    Horn_queue.join()

    # exit
    sys.exit(0)
