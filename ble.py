import sys
from arduino_alvik import ArduinoAlvik

from micropython import const

import asyncio
import aioble
import bluetooth

import random
import struct
import ustruct

import math

current_angle = 0
button_state = False

# org.bluetooth.service.environmental_sensing
_ENV_SENSE_UUID = bluetooth.UUID(0x181A)
# org.bluetooth.characteristic.temperature
_ENV_SENSE_TEMP_UUID = bluetooth.UUID(0x2A6E)
# org.bluetooth.characteristic.gap.appearance.xml
_ADV_APPEARANCE_GENERIC_THERMOMETER = const(768)


# Sensors Characteristic
# org.bluetooth.service.environmental_sensing
_SENSOR_SERV_UUID = bluetooth.UUID("19b10000-e8f2-537e-4f6c-d104768a1214")
# Accelerometer Characteristic
_ACC_CHARACTERISTIC_UUID = bluetooth.UUID("19b10001-e8f2-537e-4f6c-d104768a1214")
# Gyroscope Characteristic
_GYRO_CHARACTERISTIC_UUID = bluetooth.UUID("19b10002-e8f2-537e-4f6c-d104768a1214")

# Control Characteristic
_CONTROL_SERVICE_UUID = bluetooth.UUID("19b10003-e8f2-537e-4f6c-d104768a1214")
# org.bluetooth.characteristic.temperature
_CONTROL_CHARACTERISTIC_UUID = bluetooth.UUID("19b10004-e8f2-537e-4f6c-d104768a1214")
# org.bluetooth.characteristic.temperature
_BUTTON_CHARACTERISTIC_UUID = bluetooth.UUID("19b10005-e8f2-537e-4f6c-d104768a1214")



# How frequently to send advertising beacons.
_ADV_INTERVAL_MS = 250_000


alvik = ArduinoAlvik()
alvik.begin()

# Register GATT server.
temp_service = aioble.Service(_ENV_SENSE_UUID)
temp_characteristic = aioble.Characteristic(
    temp_service, _ENV_SENSE_TEMP_UUID, read=True, notify=True
)

# Register Sensor Service.
sensor_service = aioble.Service(_SENSOR_SERV_UUID)
acc_characteristic = aioble.Characteristic(
    sensor_service, _ACC_CHARACTERISTIC_UUID, read=True, notify=True ,capture=True
)
gyro_characteristic = aioble.Characteristic(
    sensor_service, _GYRO_CHARACTERISTIC_UUID, read=True,notify=True ,capture=True
)

# Register Control Service.
control_service = aioble.Service(_CONTROL_SERVICE_UUID)
control_characteristic = aioble.Characteristic(
    control_service, _CONTROL_CHARACTERISTIC_UUID, read=True, write=True ,notify=True ,capture=True
)
button_characteristic = aioble.Characteristic(
    control_service, _BUTTON_CHARACTERISTIC_UUID, read=True, write=True ,notify=True ,capture=True
)


aioble.register_services(temp_service,sensor_service,control_service)



# Helper to encode the temperature characteristic encoding (sint16, hundredths of a degree).
def _encode_temperature(numb):
    return struct.pack(">h", int(numb))

def _econde_sensors(x,y,z):
    return struct.pack("fff",x,y,z)

control_characteristic.write(_encode_temperature(0xABCD))

# This would be periodically polling a hardware sensor.
async def sensor_task():
    while True:
        #print("sensor task")
        acc_x,acc_y,acc_z = alvik.get_accelerations()
        gyro_x,gyro_y,gyro_z = alvik.get_gyros()             
        acc_characteristic.write(_econde_sensors(acc_x,acc_y,acc_z),send_update=True)
        gyro_characteristic.write(_econde_sensors(gyro_x,gyro_y,gyro_z),send_update=True)
        
        await asyncio.sleep_ms(100)

async def control_task():
    while True:
        global current_angle
        connection,data = await control_characteristic.written(timeout_ms=None)
        angle = ustruct.unpack(">hhh", data)[0]
        position_x = ustruct.unpack(">hhh", data)[1]
        position_y = ustruct.unpack(">hhh", data)[2]
        position_vect = math.sqrt(position_x**2 + position_y**2)
        #data_int = int.from_bytes(angle,"big",True)


        #print("Something Written raw",data)  

        if (angle > 90 and angle <= 180):
            angle = angle - 180
        elif (angle > 0 and angle <= 90):
            position_vect = position_vect*(-1)
        elif (angle < -90 and angle >= -180):
            angle = angle + 180
        else:
            position_vect = position_vect*(-1)

        print("Something Written ",angle,position_x,position_y,round(position_vect)/10*1.3)
        alvik.drive(round(position_vect)/10*1.3,angle);
   
async def button_task():
    while True:
        global button_state
        connection,data = await button_characteristic.written(timeout_ms=None)    
        buttonA_state = ustruct.unpack(">h", data)[0]
        print("ButtonAState ",buttonA_state)

        if (buttonA_state == 10):
          alvik.left_led.set_color(0, 0, 1)
          alvik.right_led.set_color(0, 0, 1)
        elif (buttonA_state == 0):
          alvik.left_led.set_color(0, 0, 0)
          alvik.right_led.set_color(0, 0, 0)
          

# Serially wait for connections. Don't advertise while a central is
# connected.
async def peripheral_task():
    while True:
        async with await aioble.advertise(
            _ADV_INTERVAL_MS,
            name="Arduino_Alvik",
            services=[_ENV_SENSE_UUID],
            appearance=_ADV_APPEARANCE_GENERIC_THERMOMETER,
        ) as connection:
            print("Connection from", connection.device)
            await connection.disconnected(timeout_ms=None)


# Run both tasks.
async def main():
    t1 = asyncio.create_task(peripheral_task())
    t2 = asyncio.create_task(sensor_task())
    t3 = asyncio.create_task(control_task())
    t4 = asyncio.create_task(button_task())
    await asyncio.gather(t1,t2,t3,t4)


asyncio.run(main())