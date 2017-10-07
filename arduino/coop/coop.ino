#include <AccelStepper.h>
#include <MultiStepper.h>

#include <SimpleModbusSlave.h>


// Using the enum instruction allows for an easy method for adding and 
// removing registers. Doing it this way saves you #defining the size 
// of your slaves register array each time you want to add more registers
// and at a glimpse informs you of your slaves register layout.

//////////////// registers of your slave ///////////////////
enum 
{     
  // just add or remove registers and your good to go...
  // The first register starts at address 0
  TEMPC10,        //0-600C * 10 = degrees C x 10
  HEATER_PCT_CMD,  //0-100%
  HEATER_PCT_OUT,  //0-100%
  LIGHT_PCT_CMD,  //0-100%
  LIGHT_PCT_OUT,  //0-100%
  DOOR_CMD,
  DOOR_STATUS,
  // leave this one
  TOTAL_ERRORS,
  // leave this one
  TOTAL_REGS_SIZE 
  // total number of registers for function 3 and 16 share the same register array
};

unsigned int holdingRegs[TOTAL_REGS_SIZE]; // function 3 and 16 register array
////////////////////////////////////////////////////////////

const int lightPin = 5;       //D5
const int doorSensorPin = 6;  //D6
const int heaterPin = 3;      //D3 
const int ledPin = 13;        //D13
const int tempSensorPin = A0;  //A0
const int doorStepPin = 7;  //D7
const int doorDirPin = 4;   //D4
const int foodStepPin = 12; //D12
const int foodDirPin = 8;   //D8

const int MAX_LIGHTS = 100; //max brightness (out of 255)
const int MAX_TEMPC = 40;    //above this temperature heater will not turn on
const int MAX_HEATER = 128; //max heater (out of 255)
const int MAX_DOOR_SPEED = 500; //max door motor speed (steps per second)

int lightStepDelay = 100; //Milliseconds between brightness steps
unsigned long lightLastChange = millis();
float tempC;

int lightOut = 0;    //current brightness
int lightCommand = 0; //desired brightness
int heaterCommand = 0;  //desired heater power
int heaterOut = 0;  //current heater power

class debounced 
{
  private:
    int _cyclesRequired = 10;
    int _numCycles = 0;  
  public:
    void process(int raw)
    {
      if (raw != stable) 
      {
        _numCycles++;
      }
      else 
      {
        _numCycles = 0;
      }
      if (_numCycles > _cyclesRequired)
      {
        stable = raw;
        _numCycles = 0;
      }
    }
    int stable;  // Stable value
};

debounced doorSensor = debounced();

AccelStepper doorMotor = AccelStepper(AccelStepper::DRIVER,doorStepPin,doorDirPin);
AccelStepper foodMotor = AccelStepper(AccelStepper::DRIVER,foodStepPin,foodDirPin);

void setup() {
  // Configure digital pins
  pinMode(lightPin, OUTPUT);
  pinMode(doorSensorPin, INPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(doorStepPin, OUTPUT);
  pinMode(doorDirPin, OUTPUT);
  pinMode(foodStepPin, OUTPUT);
  pinMode(foodDirPin, OUTPUT);

  doorMotor.setMaxSpeed(MAX_DOOR_SPEED);
  doorMotor.setSpeed(500);
  
  analogReference(INTERNAL); // Select 1.1V reference for higher accuracy
  holdingRegs[HEATER_PCT_CMD] = 50;
  holdingRegs[LIGHT_PCT_CMD] = 50;

  /* parameters(long baudrate, 
                unsigned char ID, 
                unsigned char transmit enable pin, 
                unsigned int holding registers size,
                unsigned char low latency)
                
     The transmit enable pin is used in half duplex communication to activate a MAX485 or similar
     to deactivate this mode use any value < 2 because 0 & 1 is reserved for Rx & Tx.
     Low latency delays makes the implementation non-standard
     but practically it works with all major modbus master implementations.
  */
 modbus_configure(57600, 1, 0, TOTAL_REGS_SIZE, 0);
 //Serial.begin(57600);
}

// Temp in °C = [(Vout in mV) - 500] / 10
void doTemp() {
  int raw = analogRead(tempSensorPin); // 0 = 0.0V to 1023 = 1.1V  
  float mV = raw * 1100.0 / 1024.0;
  tempC = (mV - 500.0) / 10.0;
}

void doDoorMotor() {
  doorMotor.runSpeed();
}

void doLights() {
  if (lightOut != lightCommand)
  {
    //Light output doesn't match light command
    if ((millis()-lightLastChange) >= lightStepDelay)
    {
      //It's time to make a step
      if (lightOut < lightCommand)
      {
        //Brightening, so step up
        lightOut++;
      }
      else 
      {
        //Dimming, so step down
        lightOut--;  
      }
      //Adjust the PWM at the analog output
      analogWrite(lightPin,lightOut);
      //Make note of the time so we know when it's time to take another step
      lightLastChange = millis();  
    }
  }
}

void doHeater() {
  if (tempC < MAX_TEMPC)
  {
    //It's cold, turn on the heater
    heaterOut = heaterCommand;
  }
  else
  {
    //It's hot, turn off the heater
    heaterOut = 0;
  }
  analogWrite(heaterPin,heaterOut);
}

void loop() {
  // put your main code here, to run repeatedly:
  
  // modbus_update() is the only method used in loop(). It returns the total error
  // count since the slave started. You don't have to use it but it's useful
  // for fault finding by the modbus master.
  holdingRegs[TOTAL_ERRORS] = modbus_update(holdingRegs);

  // Move door motor
  doDoorMotor();
  
  // Read temperature sensor
  doTemp();
  holdingRegs[TEMPC10] = tempC*10.0;

  // Set the heater power
  heaterCommand = (holdingRegs[HEATER_PCT_CMD] * MAX_HEATER) / 100;
  doHeater();
  holdingRegs[HEATER_PCT_OUT] = (heaterOut * 100) / MAX_HEATER;
 
  // Set the light brightness
  lightCommand = holdingRegs[LIGHT_PCT_CMD] * MAX_LIGHTS / 100;
  doLights();
  holdingRegs[LIGHT_PCT_OUT] = lightOut * 100 / MAX_LIGHTS;

  // Debounce the door sensor
  doorSensor.process(digitalRead(doorSensorPin));
  
  //Serial.print("Door: "); Serial.println(doorSensor.stable);
}
