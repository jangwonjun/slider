# Callet  
> **[Call + Wallet] 부르면 나오는 지갑**

## 🥈 2025 광운대학교 FEDEC 작품전시회 우수상 (2등)  
### 🎉 시각장애인을 위한 AI 음성인식 자동 카드 지갑  

> **Awarded for outstanding contribution to accessibility technology using AI and IoT**

---

# 💳 시각장애인을 위한 AI 음성인식 자동 카드 지갑

![Image](https://github.com/user-attachments/assets/20543fc6-59bf-44b7-8a77-57c3fc2108c3)

## 🔗 서비스 링크  
👉 [https://voicecardwallet.r-e.kr](https://voicecardwallet.r-e.kr) (2025.06.30 이후 만료예정)

---

## ❗ 문제 정의 (Pain Point)

- 시각장애인 및 약시 사용자는 카드를 고르기 어려움
- 기존 카드지갑은 물리적 구분에 의존 → 분실/오작동 위험
- 스마트 지갑은 존재하지만 음성 기반 제품은 거의 없음
- 접근성 중심의 UI/UX가 부족한 현실

---

## ✅ 해결 방안 (Solution)

- KoGPT2 기반 음성 명령 인식 → 자연어로 카드 호출
- ESP32 + 스텝모터 → 물리적인 카드 슬롯 정밀 제어
- 슬라이더 기반 자동 모드 → 손가락 위치 인식
- 모바일 웹앱 제공 → 어디서든 편리한 카드 제어

---

## API 엔드포인트 (EndPoint)
| Method | Endpoint            | 설명 |
|--------|---------------------|------|
| GET    | `/`                 | HTML UI 렌더링(index.html) |
| GET  | `/command`    | ESP32가 현재 실행할 명령 가져오기 |
| POST   | `/set_command`    | 사용자 명령을 서버에 설정(ESP32 전달용) |
| POST   | `/ack`    | 명령 수행 완료(ACK) 알림 |
| GET   | `/slots`    | 현재 저장된 슬롯 상태를 확인 |
| POST   | `/listen`    | 텍스트 기반 명령을 서버가 해석/처리 |

---

## 🛠️ 기술 스택

| 분류 | 사용 기술 |
|------|-----------|
| 음성 인식 | KoGPT2, Flask |
| 임베디드 | ESP32, HTTP, 스텝모터, 슬라이더모터(RSA0N11M9A0J_motorised_slider) |
| 웹 프론트엔드 | HTML/CSS, JavaScript |
| 통신 | Wi-Fi 기반 HTTP(Json) |
| 배포 | Nginx, 리버스 프록시 (voicecardwallet.r-e.kr) |

---

## 🧠 주요 기능 요약

- **“저장 롯데카드 1번”** → Slot 1 작동  
- **“삭제 롯데카드”** → 삭제 명령 작동
- **"롯데카드"** → 롯데카드 배출  
- **음성 피드백 제공** → TTS/STT 기반 음성 인식 및 기능작동

---

## 🗂️ 시스템 아키텍처
![Image](https://github.com/user-attachments/assets/868fe0c3-f2e7-457f-9cba-9e90bdede3ec)


---

## 👨‍👩‍👦‍👦 팀원 소개

| 이름 | 역할 |
|------|------|
| **장원준** | 팀장, 개발총괄, 통신모듈 담당, 앱 담당 |
| **김영후** | 발표, 프로젝트 매니저, 하드웨어 설계, 시연 |
| **이수현** | 프로젝트 매니저, 하드웨어 설계 및 제작, 시연 |
| **이심현** | 포스터제작, 하드웨어 설계 및 제작 |
| **조규범** | 하드웨어 설계 및 제작, 시연 |
| **조주성** | 하드웨어 설계 및 제작, 시연 |

---

## 🙌 맺음말

이 프로젝트는 단순한 기술 구현을 넘어서,  
**시각장애인의 실생활 문제를 해결**하고자 하는 마음에서 출발했습니다.  
앞으로도 기술을 통한 사회적 기여를 목표로 발전해 나가겠습니다.

---
