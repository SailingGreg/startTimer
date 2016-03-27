#!/usr/bin/env python3

#
# Version 0.8 13th February 2016
#
# 0.1 - the initial version which used shell to control GPIO pin 17
# 0.2 - uses file io to control GPIO pin 17 so there no 'shelling'
# 0.3 - fixed timing loop and extended functional logic 
# 0.4 - added threading for control of the the external relay - first release
# 0.5 - changed time to 1.5 seconds via g_horn_time
# 0.6 - allow horn_time to be specified by file horn_time.conf
# 0.7 - record finish times and save to file/email via startTimer.conf
# 0.8 - added support for warning and prep lights and added guard for email
# 0.9 - updated to use GPIO in place to the file based approach and code tidied up
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
import smtplib
import RPi.GPIO as GPIO # the GPIO gpio library
from email.mime.text import MIMEText

PY3 = sys.version_info[0] >= 3
if not PY3:
    print("startTimer only works with `python3`.")
    sys.exit(1)

switchlistener = 0
# global flags
g_horn_time_def = 1.5 # number of seconds to sound the horn
g_horn_time = 1.5 # number of seconds to sound the horn
g_mail_recipent = ""
g_horn = 0
g_running = 1 # loop until exit
g_started = 0 # not started the count
g_stop_timer = 5 # not started the count
g_timer_started = 0
g_race_started = 0 # has the race started?
g_def_time = 300
g_start_time = 300 # 5 minutes
g_race_start = datetime.datetime.now()
g_race_times = [] # list of race finish times
g_race_file = "/home/pi/startTimer/races/raceresult" + datetime.datetime.now().strftime("%y%m%d-")
g_race_stime = datetime.datetime.now().strftime("%H:%M")
# finishing related flags
g_finishing = 0
g_button_incr = 0
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
        GPIO.output(17, True)
        time.sleep (delay)
        GPIO.output(17, False)
        Horn_queue.task_done()
        time.sleep (0.3) # wait 1/3 sec so there is a definite 'gap' between execution

# routine to sound the buzzer before a time interval
def Sound_buzzer():
    while (True):
        cnt = Buzzer_queue.get()
        for i in range (1, cnt, 1):
            GPIO.output(22, True)
            time.sleep(0.1)
            GPIO.output(22, False)
            time.sleep(1/i)
        Buzzer_queue.task_done()

def Warning_flag(flg):
    if (flg == TURN_ON):
        GPIO.output(18, True)
    else:
        GPIO.output(18, False)

def Prep_flag(flg):
    if (flg == TURN_ON):
        GPIO.output(27, True)
    else:
        GPIO.output(27, False)


# functions to run the commands - cmd would be TURN_ON or TURN_OFF
def Toggle_horn(cmd):
    if (cmd == TURN_ON):
        GPIO.output(17, True)
    else:
        GPIO.output(17, False)

#
# module to parse file of parameters
def parse_file(fname):
    global g_horn_time
    global g_mail_recipent

    try:
        hf = open(fname, mode="r")
        for str_buff in hf:
            # parse line = comment or variable
            lineelms = str_buff.split(" ")
            if len(str_buff) > 1 and lineelms[0][0] != "#":
                if lineelms[0] == "horn_time":
                    hf_val = float(lineelms[1].rstrip('\n')) # remove newline
                    if hf_val > 0.0:
                        g_horn_time = hf_val
                elif lineelms[0] == "email_recipent":
                    g_mail_recipent = lineelms[1].replace('"', '')
        hf.close()
    except IOError:
        g_horn_time = g_horn_time_def

    #print ("horn_time ", g_horn_time)
    #print ("email_recipent ", g_mail_recipent)


#
# email results file to defined recipent
def send_results(fname):
    #
    fromaddr = 'ranelaghscapp@gmail.com'
    subject = "Results email"
    raceday = datetime.datetime.now().strftime("%d %b %Y")

    # Credentials (if needed)
    username = 'ranelaghscapp@gmail.com'
    password = 'R0nel0ghSC'

    #print ("Sending file ", fname)
    #print ("To ", toaddr)
    with open (fname) as fp:
        msg = MIMEText(fp.read())

    msg['Subject'] = "Race results for " + raceday + " " + g_race_stime
    msg['From'] = fromaddr
    msg['To'] = g_mail_recipent # from the conf file

    # The actual mail send
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(username, password)
    #server.sendmail(fromaddr, toaddr, message)
    server.send_message(msg)
    server.close()
    # end of send_results()

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
    global g_race_times
    #cad.lcd.clear()

    # need to calculate elapsed time if in 'finish' state
    if g_finishing == 1:
        Horn_queue.put(g_horn_time/2) # half the 'standard' time
        current_time = datetime.datetime.now()
        elapsed = current_time - g_race_start
        g_race_times.append(str(elapsed) + " - ("  + current_time.strftime("%H:%M:%S.%f") + ")")
    else:
        Horn_queue.put(g_horn_time)

    #if g_started == 1:
       # sound horn should also put a guard here as we should only allow this if we have started!
       # if we haven't started this could be used for AP
       #g_horn = 1
    #else:
       #g_running = 0 # stop, that is exit for now

# start or stop the start timer
def button_start_stop(event):
    global g_started
    global g_timer_started
    global g_horn
    global g_race_stime # the time the race started

    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if g_started == 0:
       g_started = 1
       g_stop_timer = 5 # reset to ensure it 5 seconds
       if (g_timer_started == 0): # have pressed the start for the first time
           g_timer_started = 1

           Horn_queue.put(g_horn_time)
           Warning_flag(TURN_ON) # start the warning sequence
           # note time for the results file
           # g_race_stime = datetime.datetime.now().strftime("%H:%M")

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
    global g_race_times # list of race finish times
    global g_button_incr
    global g_finishing

    if g_started == 0:
       g_race_started = 0
       g_timer_started = 0
       g_stop_timer = 5
       g_start_time = g_def_time
       g_finishing = 0
       g_button_incr = 0

       Warning_flag(TURN_OFF)
       Prep_flag(TURN_OFF)

       # need guard condition entries > 0?
       if len(g_race_times) > 0:
           race_file = g_race_file + g_race_stime
           tf = open (race_file, "w+")
           #tf = open (g_race_file, "w+")
           #i = 0
           for i, t in enumerate(g_race_times):
               # change so format is "2d"
               tf.write("{0:0=2d}".format(i + 1) + " " + t + "\n")
           tf.close()
           del g_race_times[:] # truncate array
           # email the results file
           send_results(race_file)
    # end of button_reset()

def button_incr(event):
    global g_start_time
    global g_button_incr
    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if (g_started == 0 and g_start_time < g_def_time * 3):
       g_start_time = g_start_time + 300 # add 5 minutes
       #update_display()
    if (g_race_started == 1):
       g_button_incr = 1 # may also need a time 'guard', say after 4 minutes

def button_decr(event):
    global g_start_time
    global g_finishing
    #event.chip.lcd.set_cursor(15,1)
    #event.chip.lcd.write(str(event.pin_num))
    if (g_started == 0 and g_start_time >= g_def_time * 2):
       g_start_time = g_start_time - 300 # sub 5 minutes
       #update_display()
    if (g_race_started == 1 and g_button_incr == 1):
       g_finishing = 1

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
        if (g_race_started == 1 and g_finishing == 1): # need to extend so 'finishing' state reflected
            cad.lcd.write("Fin  : {:%H:%M:%S}".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
        elif (g_race_started == 1): # need to extend so 'finishing' state reflected
            cad.lcd.write("Race : {:%H:%M:%S}".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
        else:
            cad.lcd.write("Start: {:%M:%S}   ".format(d)) # cad.lcd.write("Start: {0:2d}:{1:2d}".format(*min_sec))
    cad.lcd.set_cursor(0,1)
    cad.lcd.write("Time : " + strftime("%H:%M:%S", ltime))
    #cad.lcd.write("Time : " + strftime("%H:%M:%S", localtime()))

def init():
    global switchlistener
    #global cad
    #cad = pifacecad.PiFaceCAD()
    cad.lcd.blink_off()
    cad.lcd.cursor_off()
    cad.lcd.backlight_on()

 
    # setup GPIO lines
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(17, GPIO.OUT)
    GPIO.setup(18, GPIO.OUT)
    GPIO.setup(27, GPIO.OUT)
    GPIO.setup(22, GPIO.OUT)
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
    Toggle_horn(TURN_OFF)

    # start the listeners
    switchlistener.activate()


# main()
if __name__ == "__main__":

    # define the thread for external control and related queue
    Horn_queue = queue.Queue()
    t = threading.Thread(target=Sound_horn)
    t.daemon = True # note that this is not deamon!
    t.start()

    # define another queue for the buzzer loop
    Buzzer_queue = queue.Queue()
    tb = threading.Thread(target=Sound_buzzer)
    tb.daemon = True # note that this is not deamon!
    tb.start()

    # set horn_time and mail_recipent
    parse_file("/home/pi/startTimer/startTimer.conf")

    # initialise display etc
    cad = pifacecad.PiFaceCAD()
    init()

    # note the current time before entering loop and increment it by 1 second
    next_call = time.time()
    next_call = next_call + 1 # 1 second

    # while loop - display time
    while (g_running == 1):

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

       # start the buzzer cycle to indicate a change is coming in 5 secs
       if (g_race_started == 0 and (g_start_time == (FOUR_MINS+5) or g_start_time == (ONE_MIN+5) or g_start_time == 5)):
          Buzzer_queue.put(16)

       if (g_race_started == 0 and (g_start_time == FOUR_MINS or g_start_time == ONE_MIN or g_start_time == 0)):
          if (g_start_time == ONE_MIN):
              #g_horn = 2 # long sound
              Horn_queue.put(2 * g_horn_time)
              Prep_flag(TURN_OFF)
          else:
              #g_horn = 1 # standard sound
              Horn_queue.put(g_horn_time)
              if (g_start_time == FOUR_MINS):
                  Prep_flag(TURN_ON)

       if (g_start_time == 0): # time to start!
          g_race_started = 1
          Warning_flag(TURN_OFF)
          # note time for elapse calc
          g_race_start = datetime.datetime.now()
          # note the start time for the results
          g_race_stime = datetime.datetime.now().strftime("%H:%M")


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
    GPIO.cleanup()

    # ensure queue drained
    Horn_queue.join()
    Buzzer_queue.join()

    # exit
    sys.exit(0)

