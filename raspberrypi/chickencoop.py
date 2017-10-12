#To use this program run the following from admin command prompt:
#pip install flask pymodbus
#
from flask import Flask, render_template, request
import os.path
import requests
import random
import pickle
import atexit
from threading import Thread, Lock, Event
import time
import datetime
from pymodbus.client.sync import ModbusSerialClient as ModbusClient
from pymodbus.exceptions import ModbusIOException
import logging

ioStatus = {'tempC':0.0,
            'heaterPctCmd':0,
            'heaterPctOut':0,
            'lightPctCmd':0,
            'lightPctOut':0,
            'doorCmd':0,
            'doorStatus':0}

ioStatusLock = Lock()
stopNow = Event()

#Set up logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

#Set up Modbus client to talk to Arduino. Be sure to use port by ID so we always
#get the right one (it can switch from /dev/ttyUSB0 to /dev/ttyUSB1 without warning)
client = ModbusClient(method='rtu',
                      port='/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_AH05HBFT-if00-port0',
                      timeout=1,
                      baudrate=57600,
                      stopbits = 1,
                      bytesize = 8,
                      parity = 'N')
clientLock = Lock()
client.connect()

weather = None

#Set up web server
app = Flask(__name__)

def backgroundLoop():
    log.info("Background loop started.")
    while not stopNow.wait(1):
        doModbus()

def weatherLoop():
    global weather
    log.info("Weather thread started")
    weather = getWeather()
    while not stopNow.wait(600):
        weather = getWeather()
        
def doorCommand(number):
    pass

def doorStatus():
    return 0

#def isItSunrise():
    #global sunriseTime
    #sunriseTime = datetime.datetime.strptime(getSunrise(), '%H:%M %p').time()

def saveSettings():
    pickle.dump( settings, open( "save.p", "wb" ) )

def loadSettings():
    if os.path.isfile("save.p"):
        log.info("loading settings from save.p")
        return pickle.load( open( "save.p", "rb" ) )
    else:
        log.info("loading default settings")
        return  {
            'WOEID' : "2396147"
        }
# Lookup WOEID via http://weather.yahoo.com.

settings = loadSettings()
atexit.register(saveSettings)
    
def getWeather():
    baseurl = "https://query.yahooapis.com/v1/public/yql?q="
    yql_query = "select astronomy, item.condition from weather.forecast where woeid=" + settings['WOEID']
    yql_url = baseurl + yql_query + "&format=json"
    r = requests.get(yql_url)
    if r.status_code != 200:
        #There was a problem
        return None
    #
    return r.json()['query']['results']['channel']

def getOutsideCondition():
    return weather['item']['condition']['text']

def getInternalTemperature():
    with ioStatusLock:
        #We're thread protected in here
        t = ioStatus['tempC']
    return t

def getExternalTemperature():
    return int(weather['item']['condition']['temp'])

def getSunrise():
    return weather['astronomy']['sunrise']

def getSunset():
    return weather['astronomy']['sunset']



#Modbus memory map for communication with slave
#0  TEMPC10,        //0-600C * 10 = degrees C x 10
#1  HEATER_PCT_CMD,  //0-100%
#2  HEATER_PCT_OUT,  //0-100%
#3  LIGHT_PCT_CMD,  //0-100%
#4  LIGHT_PCT_OUT,  //0-100%
#5  DOOR_CMD,
#6  DOOR_STATUS,
#7  TOTAL_ERRORS,

def doModbus():
    try:
        #Read 8 holding registers from address 0
        with clientLock:
            #We're thread protected in here
            rr = client.read_holding_registers(0, 8, unit=1)
            #Make sure the read was successful
            assert(rr.function_code < 0x80)
            
        with ioStatusLock:
            #We're thread protected in here
            #Copy the read values
            ioStatus['tempC'] = rr.registers[0]/10.0
            ioStatus['heaterPctOut'] = rr.registers[2]
            ioStatus['lightPctOut'] = rr.registers[4]
            ioStatus['doorStatus'] = rr.registers[6]
            ioStatus['totalErrors'] = rr.registers[7]

    except Exception as e:
        log.exception(e)

#Sets ioStatus key/value pair and writes to specified Modbus register
def writeRegister(key, value, addr):
    try:
        with ioStatusLock:
            #We're thread protected in here
            ioStatus[key] = value
        #Write the register
        with clientLock:
            #We're thread protected in here
            rq = client.write_register(addr,value,unit=1)
            assert(rq.function_code < 0x80)
    except Exception as e:
        log.exception(e)

def setHeaterPct(value):
    writeRegister('heaterPctCmd',value,1)

def setLightPct(value):
    writeRegister('lightPctCmd',value,3)

def setDoor(value):
    writeRegister('doorCmd',value,5)
       
@app.route("/", methods=['GET', 'POST'])
def hello():
    with ioStatusLock:
        templateData = {
            'outsidecondition' : getOutsideCondition(),
            'internaltemperature': "{}".format(ioStatus['tempC']),
            'externaltemperature' : "{}".format(getExternalTemperature()),
            'sunrise': getSunrise(),
            'sunset': getSunset(),
            'doorStatus': ioStatus['doorStatus'],
            'heaterPctOut': ioStatus['heaterPctOut'],
            'lightPctOut': ioStatus['lightPctOut'],
            'title' : 'The Cutting Coop'
            }
    
    #Check button presses
    for s in request.values:
        app.logger.info(s)
    if 'doorOpen' in request.values:
        app.logger.info("Button clicked: Open door")
        setDoor(1)
    elif 'doorClose' in request.values:
        app.logger.info("Button clicked: Close door")
        setDoor(2)

    return render_template('main.html', **templateData)

if __name__ == "__main__":
    t = Thread(target=backgroundLoop)
    w = Thread(target=weatherLoop)
    w.start()
    t.start()
    app.run(host='0.0.0.0', port=8080, debug=True, use_reloader=False)
    #All done
    stopNow.set()
    t.join()
    w.join()
    
