#To use this program run the following from admin command prompt:
#pip install flask weather-api
#
from flask import Flask, render_template
import os.path
import requests
import random
import pickle
import atexit
from threading import Thread
import time
import datetime

app = Flask(__name__)

def backgroundLoop():
    print ("Background loop started.")
    while True:
        time.sleep(1)
        #print(sunriseTime)
        
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
        print ("loading settings from save.p")
        return pickle.load( open( "save.p", "rb" ) )
    else:
        print ("loading default settings")
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
    lookup = getWeather()
    return lookup['item']['condition']['text']

def getInternalTemperature():
    return random.randint(32,100)

def getExternalTemperature():
    lookup = getWeather()
    return int(lookup['item']['condition']['temp'])

def getSunrise():
    lookup = getWeather()
    return lookup['astronomy']['sunrise']

def getSunset():
    lookup = getWeather()
    return lookup['astronomy']['sunset']

#Modbus memory map for communication with slave
#Address   Description
#1         Motor enable (0=off, 1=on)
#2         Heater power (0-100%)
#3         Door Status (0=unknown, 1=opening, 2=closing, 3=open, 4=closed)
#4         Door Command (0=done, 1=open, 2=close)
#5         Lighting power (0-100%)
#6         Auger turns remaining (0-100)
#7         Temperature (0-120) degrees F
       
@app.route("/")
def hello():
    templateData = {
        'outsidecondition' : getOutsideCondition(),
        'internaltemperature': "{}".format(getInternalTemperature()),
        'externaltemperature' : "{}".format(getExternalTemperature()),
        'sunrise': getSunrise(),
        'sunset': getSunset(),
        'title' : 'The Cutting Coop'
        }
    return render_template('main.html', **templateData)

if __name__ == "__main__":
    #t = Thread(target=backgroundLoop)
    #t.start()
    app.run(host='0.0.0.0', port=8080, debug=True)
    #w = getWeather()
    #print(w)
    
