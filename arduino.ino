#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// WiFi 설정
const char* ssid = "admin";
const char* password = "123456789";
const char* commandUrl = "https://voicecardwallet.r-e.kr/command";
const char* ackUrl = "https://voicecardwallet.r-e.kr/ack";

// 핀 설정
const int buzzerPin = 25;
const int motorPinA1 = 5;   // D5 → GPIO5
const int motorPinA2 = 18;  // D18 → GPIO18

// PWM 채널 설정
const int pwmChannel1 = 0;
const int pwmChannel2 = 1;

void setupPWM(int pin, int channel) {
  ledcSetup(channel, 1000, 8);  // 주파수 1kHz, 해상도 8비트
  ledcAttachPin(pin, channel);
}

// 슬라이더 A : 32, B : 35, 
// 스텝모터 27, 12, 14, 13, 

// 부저 울리기
void buzz(int duration_ms) {
  digitalWrite(buzzerPin, HIGH);
  delay(duration_ms);
  digitalWrite(buzzerPin, LOW);
}

// 모터 제어 함수
void runMotorForward() {
  Serial.println(">> 모터 정방향 회전");
  ledcWrite(pwmChannel1, 250); // PWM 출력
  digitalWrite(motorPinA2, LOW);
  delay(3000);
    
  // 정지
  ledcWrite(pwmChannel1, 0);
  digitalWrite(motorPinA2, LOW);
  delay(500);

  // 짧은 역방향 돌리기
  digitalWrite(motorPinA1, LOW);
  ledcWrite(pwmChannel2, 250);
  delay(500);

  ledcWrite(pwmChannel2, 0);
  digitalWrite(motorPinA2, LOW);
  delay(500);
}

// 명령 처리
void handleCommand(String cmd) {
  if (cmd == "l" || cmd == "r" || cmd == "s") {
    runMotorForward();
  } else {
    Serial.println(">> 알 수 없는 명령: " + cmd);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(buzzerPin, OUTPUT);
  pinMode(motorPinA1, OUTPUT);
  pinMode(motorPinA2, OUTPUT);

  // PWM 설정
  setupPWM(motorPinA1, pwmChannel1);
  setupPWM(motorPinA2, pwmChannel2);

  // WiFi 연결
  WiFi.begin(ssid, password);
  Serial.print("WiFi 연결 중...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("WiFi 연결 완료!");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(commandUrl);
    
    int httpCode = http.GET();
    if (httpCode > 0) {
      String payload = http.getString();
      Serial.println("서버 응답: " + payload);

      StaticJsonDocument<200> doc;
      DeserializationError error = deserializeJson(doc, payload);
      if (!error) {
        const char* command = doc["command"];
        if (command && String(command) != "none") {
          Serial.println("받은 명령: " + String(command));

          buzz(500);
          handleCommand(command);

          // ACK 전송
          HTTPClient ackHttp;
          ackHttp.begin(ackUrl);
          ackHttp.addHeader("Content-Type", "application/json");

          StaticJsonDocument<100> ackDoc;
          ackDoc["ack"] = true;
          String ackPayload;
          serializeJson(ackDoc, ackPayload);
          int ackCode = ackHttp.POST(ackPayload);
          Serial.printf("ACK 전송 결과: %d\n", ackCode);
          ackHttp.end();
        }
      } else {
        Serial.println("JSON 파싱 실패");
      }
    } else {
      Serial.printf("HTTP 요청 실패, 코드: %d\n", httpCode);
    }
    http.end();
  } else {
    Serial.println("WiFi 연결 끊김");
  }

  delay(5000);
}
