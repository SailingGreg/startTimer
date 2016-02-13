# start startTimer
#set -x

for PIN in 17 18 27; do
    #echo $PIN
    /home/pi/startTimer/gpio${PIN}setup
done

#chmod 666 /sys/class/gpio/gpio17/value
/usr/bin/python3 /home/pi/startTimer/startTimer.py

exit 0

