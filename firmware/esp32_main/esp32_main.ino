#include <WiFi.h>
#include <ArduinoWebsockets.h>    // Install: "ArduinoWebsockets" by Gil Maimon
#include <ArduinoJson.h>           // Install: "ArduinoJson" by Benoit Blanchon (v7)
#include <DHT.h>
#include <TinyGPS++.h>

using namespace websockets;

// =================================================
// >>>  CONFIGURE THESE THREE LINES  <<<
// =================================================

const char* WIFI_SSID     = "YOUR_WIFI_NAME";           // <<< enter your WiFi name here
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";       // <<< enter your WiFi password here
const char* BACKEND_HOST  = "192.168.X.X";              // <<< enter your laptop's LAN IP here (NOT localhost)

const uint16_t BACKEND_PORT = 8000;
const char*    WS_PATH      = "/ws/esp32";

// =================================================
// MOTOR DRIVER
// =================================================

#define IN1 25
#define IN2 26
#define IN3 27
#define IN4 14

// =================================================
// ULTRASONIC
// =================================================

#define TRIG_PIN 18
#define ECHO_PIN 19

// =================================================
// MOISTURE SENSOR
// =================================================

#define MOISTURE_PIN 34

// =================================================
// RELAY (water pump)
// =================================================

#define RELAY_PIN 23
#define PUMP_ON   LOW
#define PUMP_OFF  HIGH

// =================================================
// DHT11
// =================================================

#define DHT_PIN  4
#define DHT_TYPE DHT11

DHT dht(DHT_PIN, DHT_TYPE);

// =================================================
// GPS
// =================================================

#define GPS_RX 32   // ESP32 RX <- GPS TX
#define GPS_TX 33   // ESP32 TX -> GPS RX

HardwareSerial GPS_Serial(2);
TinyGPSPlus gps;

// =================================================
// WEBSOCKET + STATE
// =================================================

WebsocketsClient wsClient;

volatile bool missionPaused  = false;
volatile bool missionStopped = false;

float targetX = 0.0f;
float targetY = 0.0f;

float waterMl     = 0.0f;
float fertilizerG = 0.0f;
int   seeds       = 0;

// =================================================
// FORWARD DECLARATIONS
// =================================================
void stopMotors();
void moveForward();
void readGPS();
float getDistance();
void sendTelemetry();
void connectWebSocket();

// =================================================
// WEBSOCKET CALLBACKS
// =================================================

void onWsMessage(WebsocketsMessage msg) {
  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, msg.data());
  if (err) {
    Serial.print("JSON parse error: ");
    Serial.println(err.c_str());
    return;
  }

  const char* type = doc["type"];
  if (!type) return;

  Serial.print("CMD received: ");
  Serial.println(type);

  if (strcmp(type, "WAYPOINT") == 0) {
    targetX = doc["target_x_m"] | 0.0f;
    targetY = doc["target_y_m"] | 0.0f;
    const char* action = doc["action"] | "NAVIGATE";

    Serial.print("  Target x="); Serial.print(targetX);
    Serial.print("  y="); Serial.print(targetY);
    Serial.print("  action="); Serial.println(action);

    if (strcmp(action, "NAVIGATE") == 0) {
      if (!missionPaused) moveForward();
    } else if (strcmp(action, "SAMPLE_SOIL") == 0) {
      stopMotors();
    }

  } else if (strcmp(type, "PAUSE_MISSION") == 0) {
    missionPaused = true;
    stopMotors();
    digitalWrite(RELAY_PIN, PUMP_OFF);
    Serial.println("Mission PAUSED - holding position.");

  } else if (strcmp(type, "RESUME_MISSION") == 0) {
    missionPaused = false;
    Serial.println("Mission RESUMED.");
    moveForward();

  } else if (strcmp(type, "STOP_MISSION") == 0) {
    missionStopped = true;
    missionPaused  = false;
    stopMotors();
    digitalWrite(RELAY_PIN, PUMP_OFF);
    Serial.println("Mission STOPPED.");
  }
}

void onWsEvent(WebsocketsEvent event, String data) {
  if (event == WebsocketsEvent::ConnectionOpened) {
    Serial.println("WebSocket connected to backend.");
  } else if (event == WebsocketsEvent::ConnectionClosed) {
    Serial.println("WebSocket disconnected - will reconnect.");
  } else if (event == WebsocketsEvent::GotPing) {
    wsClient.pong();
  }
}

// =================================================
// SEND TELEMETRY
// =================================================

void sendTelemetry() {
  if (!wsClient.available()) return;

  int   moistureRaw = analogRead(MOISTURE_PIN);
  int   moisturePct = map(moistureRaw, 4095, 0, 0, 100);

  float distance    = getDistance();
  float humidity    = dht.readHumidity();
  float temperature = dht.readTemperature();

  readGPS();

  StaticJsonDocument<768> envelope;
  envelope["type"] = "TELEMETRY";
  JsonObject payload = envelope.createNestedObject("payload");

  payload["source"]             = "SENSOR";
  payload["x_m"]               = targetX;
  payload["y_m"]               = targetY;
  payload["soil_moisture_pct"] = moisturePct;
  payload["soil_moisture_raw"] = moistureRaw;
  payload["depth_mm"]          = 150.0;
  payload["hours_since_irrigation"] = 0.0;

  if (!isnan(humidity)) {
    payload["humidity_pct"]         = humidity;
    payload["relative_humidity_pct"]= humidity;
  }
  if (!isnan(temperature)) {
    payload["ambient_temperature_c"] = temperature;
  }
  if (distance < 999) {
    payload["obstacle_distance_cm"] = distance;
  }

  payload["movement_status"]   = missionPaused ? "STOPPED" : "MOVING_FORWARD";
  payload["pump_status"]       = (digitalRead(RELAY_PIN) == PUMP_ON) ? "ON" : "OFF";
  payload["operational_phase"] = missionPaused ? "PAUSED" : "NAVIGATION_MONITORING";
  payload["rover_status"]      = missionPaused ? "PAUSED" : (missionStopped ? "STOPPED" : "NAVIGATING");
  payload["battery_pct"]       = 95;
  payload["active_payload"]    = "IRRIGATION";
  payload["heading_deg"]       = 0;

  if (gps.location.isValid()) {
    payload["gps_lat"] = gps.location.lat();
    payload["gps_lng"] = gps.location.lng();
  }

  JsonObject resources      = payload.createNestedObject("resources_used");
  resources["water_ml"]     = waterMl;
  resources["fertilizer_g"] = fertilizerG;
  resources["seeds"]        = seeds;

  String message;
  serializeJson(envelope, message);
  wsClient.send(message);

  Serial.println("-> Telemetry sent");
}

// =================================================
// WIFI + WEBSOCKET CONNECT
// =================================================

void connectWifi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected - IP: ");
  Serial.println(WiFi.localIP());
}

void connectWebSocket() {
  wsClient.onMessage(onWsMessage);
  wsClient.onEvent(onWsEvent);
  Serial.print("Connecting WebSocket to ws://");
  Serial.print(BACKEND_HOST);
  Serial.print(":");
  Serial.print(BACKEND_PORT);
  Serial.println(WS_PATH);
  while (!wsClient.connect(BACKEND_HOST, BACKEND_PORT, WS_PATH)) {
    Serial.println("WS connection failed - retrying in 3s...");
    delay(3000);
  }
  Serial.println("WebSocket connected!");
}

// =================================================
// SETUP
// =================================================

void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT); pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT); pinMode(IN4, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(MOISTURE_PIN, INPUT);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, PUMP_OFF);
  stopMotors();

  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);

  Serial.println("================================");
  Serial.println("       AGRICULTURE ROVER");
  Serial.println("================================");

  connectWifi();
  connectWebSocket();

  Serial.println("Ready - waiting for mission from dashboard.");
}

// =================================================
// MAIN LOOP
// =================================================

void loop() {
  if (wsClient.available()) {
    wsClient.poll();
  } else {
    Serial.println("WS dropped - reconnecting...");
    delay(3000);
    connectWebSocket();
  }

  if (missionPaused || missionStopped) {
    stopMotors();
    digitalWrite(RELAY_PIN, PUMP_OFF);
  }

  readGPS();

  static unsigned long lastTelemetry = 0;
  if (millis() - lastTelemetry >= 1000) {
    lastTelemetry = millis();
    sendTelemetry();
  }
}

// =================================================
// GPS READING
// =================================================

void readGPS() {
  while (GPS_Serial.available() > 0) {
    gps.encode(GPS_Serial.read());
  }
}

// =================================================
// MOTOR FUNCTIONS
// =================================================

void moveForward() {
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH); digitalWrite(IN4, LOW);
}

void stopMotors() {
  digitalWrite(IN1, LOW); digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW); digitalWrite(IN4, LOW);
}

// =================================================
// ULTRASONIC DISTANCE
// =================================================

float getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 999;
  return duration * 0.0343f / 2.0f;
}
