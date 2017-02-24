import utime
import machine
from machine import I2C, Pin
from servo import Servo
import onewire, ds18x20
from esp8266_i2c_lcd import I2cLcd
import ubinascii
from umqtt.simple import MQTTClient
import ntptime
import network

def gettimestr():
    rtc=machine.RTC()
    curtime=rtc.datetime()
    _time="%04d" % curtime[0]+ "%02d" % curtime[1]+ "%02d" % curtime[2]+" "+ "%02d" % curtime[4]+ "%02d" % curtime[5]
    return _time

servo_min_angle = 10
servo_max_angle = 160
servo_angle=servo_min_angle
servo_adjust_angle=10
# the device is on GPIO12
dat = machine.Pin(14)

#sleep time in every loop
sleep_time=10000
#send values every Nth loop
send_values=6 #every minute
#update time from ntp every Nth loop
update_time=6*60 #every hour

# create the onewire object
ds = ds18x20.DS18X20(onewire.OneWire(dat))

outside_rom = bytearray(b'(\xff}t\x83\x16\x04\xce')
heated_rom = bytearray(b'(\xff.6\x82\x16\x05\x07')
inside_rom = bytearray(b'(\xffF\x1d\x85\x16\x05\xb6')

outside_temp=0
heated_temp=0
inside_temp=0

stoppin = Pin(0,mode=machine.Pin.IN,pull=machine.Pin.PULL_UP)

servo_pin = Pin(5)

servo=Servo(servo_pin)
servo.write_angle(degrees=servo_angle)
servo_angle_old=servo_angle

adc = machine.ADC(0)

i2c = I2C(scl=Pin(13), sda=Pin(12), freq=400000)
lcd = I2cLcd(i2c, 0x3f, 2, 16)

#check that we have correct sensors
roms = ds.scan()
for rom in roms:
    if rom == outside_rom:
        print('Outside sensor found.', rom)
    elif rom == heated_rom:
        print('Heated air sensor found.', rom)
    elif rom == inside_rom:
        print('Inside sensor found.', rom)
    else:
        print('Unknown sensor found. ', rom)

# Check if we have wifi, and wait for connection if not.
print("Check wifi connection.")
wifi = network.WLAN(network.STA_IF)
i = 0
while not wifi.isconnected():
    if (i>10):
        print("No wifi connection.")
        raise Warning
    print(".")
    utime.sleep(1)
    i=i+1

ntptime.settime()

c = MQTTClient('solar_client', '192.168.0.106')
c.connect()

update_time_i=update_time
send_values_i=send_values

def loop_callback(temp):
    global update_time_i
    global update_time
    global send_values_i
    global send_values
    global c
    global ds
    global servo_angle
    global servo_angle_old
    global servo
    global lcd
    global stoppin

    if update_time_i==0:
        ntptime.settime()
        update_time_i=update_time
    else:
        update_time_i=update_time_i-1
    
    ds.convert_temp()
    utime.sleep_ms(1000)

    inside_temp = ds.read_temp(inside_rom)
    outside_temp = ds.read_temp(outside_rom)
    heated_temp = ds.read_temp(heated_rom)

    if heated_temp>inside_temp+2:
        servo_angle=servo_angle+servo_adjust_angle
    if heated_temp<inside_temp:
        servo_angle=servo_angle-servo_adjust_angle

    if servo_angle>servo_max_angle:
        servo_angle=servo_max_angle
    if servo_angle<servo_min_angle:
        servo_angle=servo_min_angle

    if (servo_angle_old!=servo_angle):
        servo.write_angle(degrees=servo_angle)
        servo_angle_old=servo_angle

    if send_values_i==0:
        _time=gettimestr()
        #temps
        topic="raw/1wire/"+ubinascii.hexlify(inside_rom).decode()+"/temperature"
        message=_time+' '+str(inside_temp)
        c.publish(topic,message)
        topic="raw/1wire/"+ubinascii.hexlify(outside_rom).decode()+"/temperature"
        message=_time+' '+str(outside_temp)
        c.publish(topic,message)
        topic="raw/1wire/"+ubinascii.hexlify(heated_rom).decode()+"/temperature"
        message=_time+' '+str(heated_temp)
        c.publish(topic,message)
        #servo angle
        topic="raw/esp8266/"+ubinascii.hexlify(machine.unique_id()).decode()+"/servo"
        message=_time+" "+str(servo_angle)
        c.publish(topic,message)
        #solar panel voltage
        voltage = adc.read();
        topic="raw/esp8266/"+ubinascii.hexlify(machine.unique_id()).decode()+"/adc"
        message=_time+" "+str(voltage)
        c.publish(topic,message)
        send_values_i=send_values
    else:
        send_values_i=send_values_i-1

    lcd_str = "In % 3.0f Out % 3.0f\nHeated % 3.0f   %d" %(inside_temp, outside_temp, heated_temp, servo_angle)
    lcd.clear()
    lcd.putstr(lcd_str)
    print(lcd_str)

    if stoppin.value()==0:
        print("Pin down, stop")
        tim.deinit()


tim = machine.Timer(-1)
tim.init(period=sleep_time, mode=machine.Timer.PERIODIC, callback=loop_callback)
