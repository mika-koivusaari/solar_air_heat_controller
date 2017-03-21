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

#get ntp time
#retry=0 try once and ignore errors silently
#retry>0 try retry times and raise error if not
#succesfull
def getntptime(retry=0):
    retryleft=retry
    while retryleft>=0:
        try:
            lcd.clear()
            lcd.putstr("Set NTP time")
            ntptime.settime()
            lcd.putstr(" OK")
            return
        except:
            if retry>0:
                if retryleft==0:
                    raise
                retryleft=retryleft-1
                lcd.putstr(".")
                utime.sleep(5)
            else:
                retryleft=-1
                

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

outside_rom = ubinascii.unhexlify('28cfbece010000cf')
#bytearray(b'(\xcf\xbe\xce\x01\x00\x00\xcf')
heated_rom = ubinascii.unhexlify('28ff7041821603c3')
#bytearray(b'(\xffpA\x82\x16\x03\xc3')
inside_rom = ubinascii.unhexlify('28ff0aa3811603b9')
#bytearray(b'(\xff\n\xa3\x81\x16\x03\xb9')

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
        print('Outside sensor found.', ubinascii.hexlify(rom).decode())
    elif rom == heated_rom:
        print('Heated air sensor found.', ubinascii.hexlify(rom).decode())
    elif rom == inside_rom:
        print('Inside sensor found.', ubinascii.hexlify(rom).decode())
    else:
        print('Unknown sensor found. ', ubinascii.hexlify(rom).decode())

# Check if we have wifi, and wait for connection if not.
print("Check wifi connection.")
lcd.clear()
lcd.putstr("Connect to wifi")
wifi = network.WLAN(network.STA_IF)
i = 0
while not wifi.isconnected():
    if (i>10):
        print("No wifi connection.")
        lcd.putstr("No wifi")
        raise Warning
    print(".")
    lcd.putstr(".")
    utime.sleep(1)
    i=i+1

getntptime(retry=10)

lcd.clear()
lcd.putstr("Connect to MQTT broker")
c = MQTTClient('solar_client', '192.168.0.106')
c.connect()
lcd.putstr(" OK")

topic="raw/esp8266/"+ubinascii.hexlify(machine.unique_id()).decode()+"/messages"
_time=gettimestr()
message=_time+" started "+str(machine.reset_cause())
c.publish(topic,message)

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

    try:
        if update_time_i==0:
            getntptime(retry=0)
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
    except Exception as e:
        try:
            #Print exception in case someone is looking.
            #This should allways work.
            print(e)
            #Second option is to put the exception on LCD
            #This will work if we have an LCD connected
            lcd.clear()
            lcd.putstr(repr(e))
            #Third option is to send exception via MQTT
            #This should work if we have a connection,
            topic="raw/esp8266/"+ubinascii.hexlify(machine.unique_id()).decode()+"/messages"
            _time=gettimestr()
            message=_time+" exception "+repr(e)
            c.publish(topic,message)
        except:
            #If we can't do all of the above then
            #we have a fatal error and should stop
            #so that the error stays in the LCD
            tim.deinit()
            raise


tim = machine.Timer(-1)
tim.init(period=sleep_time, mode=machine.Timer.PERIODIC, callback=loop_callback)
