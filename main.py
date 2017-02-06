import time
import machine
from machine import I2C, Pin
from servo import Servo
import onewire, ds18x20
from esp8266_i2c_lcd import I2cLcd

servo_min_angle = 10
servo_max_angle = 160
servo_angle=servo_min_angle
servo_adjust_angle=10
# the device is on GPIO12
dat = machine.Pin(14)

# create the onewire object
ds = ds18x20.DS18X20(onewire.OneWire(dat))

outside_rom = bytearray(b'(\xff}t\x83\x16\x04\xce')
heated_rom = bytearray(b'(\xff.6\x82\x16\x05\x07')
inside_rom = bytearray(b'(\xffF\x1d\x85\x16\x05\xb6')

outside_temp=0
heated_temp=0
inside_temp=0

stoppin = machine.Pin(0,mode=machine.Pin.IN,pull=machine.Pin.PULL_UP)

servo_pin = Pin(5)

servo=Servo(servo_pin)
servo.write_angle(degrees=servo_angle)

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


# scan for devices on the bus
#roms = ds.scan()
#print('found devices:', roms)

# loop 10 times and print all temperatures
for i in range(10):
    ds.convert_temp()
    time.sleep_ms(1000)

    inside_temp = ds.read_temp(inside_rom)
    outside_temp = ds.read_temp(outside_rom)
    heated_temp = ds.read_temp(heated_rom)
    
    lcd.clear()
    lcd.putstr("In % 3.0f Out % 3.0f\nHeated % 3.0f %d" %
               (inside_temp, outside_temp, heated_temp, servo_angle))
    print(".")

    if heated_temp>inside_temp+2:
        servo_angle=servo_angle+servo_adjust_angle
    if heated_temp<inside_temp+1:
        servo_angle=servo_angle-servo_adjust_angle

    if servo_angle>servo_max_angle:
        servo_angle=servo_max_angle
    if servo_angle<servo_min_angle:
        servo_angle=servo_min_angle

    servo.write_angle(degrees=servo_angle)

    time.sleep_ms(10000)

    if stoppin.value()==0:
        print("Pin down, stop")
        break


#init 1-wire
#sensors:
#outside temp
#heated air temp
#inside temp

#init servo

#init timer1 10 sec
#init timer2 60 sec

#timer1
#check if heated air temp > inside temp+8
# open flap more
#servo.write_angle(degrees=45)
#check if heated air temp < inside temp+3
# close flap more

#timer2
#send temps + flap position with mqtt
#measure voltage from adc (small solar panel)
#send voltage with mqtt
