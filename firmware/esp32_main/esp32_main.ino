#include <DHT.h>
#include <TinyGPS++.h>

// ================= MOTOR DRIVER =================

#define IN1 25
#define IN2 26
#define IN3 27
#define IN4 14

// ================= ULTRASONIC =================

#define TRIG_PIN 18
#define ECHO_PIN 19

// ================= MOISTURE SENSOR =================

#define MOISTURE_PIN 34

// ================= RELAY =================

#define RELAY_PIN 23

#define PUMP_ON  LOW
#define PUMP_OFF HIGH

// ================= DHT11 =================

#define DHT_PIN 4
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

// ================= GPS =================

#define GPS_RX 32   // ESP32 RX ← GPS TX
#define GPS_TX 33   // ESP32 TX → GPS RX

HardwareSerial GPS(2);
TinyGPSPlus gps;


// =================================================
// SETUP
// =================================================

void setup()
{
  Serial.begin(115200);

  // Motor pins
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  // Ultrasonic
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  // Moisture
  pinMode(MOISTURE_PIN, INPUT);

  // Relay
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, PUMP_OFF);

  // Motors OFF
  stopMotors();

  // DHT11
  dht.begin();

  // GPS
  GPS.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  Serial.println("================================");
  Serial.println("       AGRICULTURE ROVER");
  Serial.println("================================");
  Serial.println("GPS starting...");
  Serial.println();
}


// =================================================
// MAIN LOOP
// =================================================

void loop()
{
  Serial.println("Motors FORWARD");

  moveForward();

  unsigned long startTime = millis();


  // =================================================
  // MOTORS RUN FOR 10 SECONDS
  // =================================================

  while (millis() - startTime < 10000)
  {
    // ---------------- GPS ----------------

    readGPS();


    // ---------------- MOISTURE ----------------

    int moisture = analogRead(MOISTURE_PIN);


    // ---------------- ULTRASONIC ----------------

    float distance = getDistance();


    // ---------------- DHT11 ----------------

    float humidity = dht.readHumidity();
    float temperature = dht.readTemperature();


    // =================================================
    // DISPLAY READINGS
    // =================================================

    Serial.println("--------------------------------");

    // Moisture
    Serial.print("Moisture: ");
    Serial.println(moisture);


    // Ultrasonic
    Serial.print("Distance: ");

    if (distance >= 999)
    {
      Serial.println("No object");
    }
    else
    {
      Serial.print(distance);
      Serial.println(" cm");
    }


    // DHT11
    if (isnan(humidity) || isnan(temperature))
    {
      Serial.println("DHT: Error reading sensor");
    }
    else
    {
      Serial.print("Humidity: ");
      Serial.print(humidity);
      Serial.println(" %");

      Serial.print("Temperature: ");
      Serial.print(temperature);
      Serial.println(" °C");
    }


    // =================================================
    // GPS
    // =================================================

    if (gps.location.isValid())
    {
      Serial.println("GPS: FIX");

      Serial.print("Latitude: ");
      Serial.println(gps.location.lat(), 6);

      Serial.print("Longitude: ");
      Serial.println(gps.location.lng(), 6);

      Serial.print("Satellites: ");
      Serial.println(gps.satellites.value());

      Serial.print("Google Maps: ");
      Serial.print("https://maps.google.com/?q=");
      Serial.print(gps.location.lat(), 6);
      Serial.print(",");
      Serial.println(gps.location.lng(), 6);
    }
    else
    {
      Serial.println("GPS: Waiting for satellite fix...");
    }

    Serial.println("--------------------------------");

    delay(1000);
  }


  // =================================================
  // STOP MOTORS
  // =================================================

  stopMotors();

  Serial.println();
  Serial.println("10 seconds completed.");
  Serial.println("Motors STOP");
  Serial.println("Pump ON");


  // =================================================
  // PUMP ON FOR 3 SECONDS
  // =================================================

  digitalWrite(RELAY_PIN, PUMP_ON);

  unsigned long pumpStart = millis();

  while (millis() - pumpStart < 3000)
  {
    // Keep GPS receiving data
    readGPS();

    delay(10);
  }


  // =================================================
  // PUMP OFF
  // =================================================

  digitalWrite(RELAY_PIN, PUMP_OFF);

  Serial.println("Pump OFF");
  Serial.println("Starting next cycle...");
  Serial.println();

  delay(500);
}


// =================================================
// GPS READING FUNCTION
// =================================================

void readGPS()
{
  while (GPS.available() > 0)
  {
    gps.encode(GPS.read());
  }
}


// =================================================
// MOVE FORWARD
// =================================================

void moveForward()
{
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}


// =================================================
// STOP MOTORS
// =================================================

void stopMotors()
{
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);

  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}


// =================================================
// ULTRASONIC DISTANCE
// =================================================

float getDistance()
{
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);

  long duration = pulseIn(ECHO_PIN, HIGH, 30000);

  if (duration == 0)
  {
    return 999;
  }

  float distance = duration * 0.0343 / 2.0;

  return distance;
}