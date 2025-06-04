from flask import Flask, jsonify, render_template, request
import paho.mqtt.client as mqtt
import ssl
import time
import pyttsx3
import speech_recognition as sr
import threading
import re
from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel
import torch
import numpy as np

app = Flask(__name__)

# ===== MQTT 설정 =====
MQTT_BROKER = "voicecardwallet.r-e.kr"  # 실제 MQTT 브로커 주소로 변경하세요
MQTT_PORT = 8883


MQTT_TOPIC = "esp32/commands"  # ESP32가 구독하는 토픽

mqtt_client = mqtt.Client()

mqtt_client.tls_set(
    ca_certs="/etc/ssl/certs/ca-certificates.crt",  # 대부분 이걸로 충분함
    tls_version=ssl.PROTOCOL_TLSv1_2
)
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT 브로커 연결 성공")
    else:
        print(f"MQTT 연결 실패, 코드: {rc}")

mqtt_client.on_connect = on_connect
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# ===== TTS 엔진 및 락 =====
tts_engine = pyttsx3.init()
tts_lock = threading.Lock()

# ===== 슬롯 데이터 =====
slots = {}

# ===== KoGPT2 모델 로드 =====
tokenizer = PreTrainedTokenizerFast.from_pretrained("skt/kogpt2-base-v2")
model = GPT2LMHeadModel.from_pretrained("skt/kogpt2-base-v2")
model.eval()

# ===== 동의어 그룹 =====
synonym_groups = [
    ["주민등록증", "민증", "등록증"],
    ["롯데카드", "롯데"],
    ["삼성카드", "삼성"],
]

# ===== 음성 합성 함수 =====
def speak(text):
    with tts_lock:
        tts_engine.say(text)
        tts_engine.runAndWait()

# ===== 음성 인식 함수 =====
def listen_command():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("🎤 음성 입력 대기 중...")
            audio = r.listen(source, timeout=5, phrase_time_limit=7)
    except Exception as e:
        print(f"마이크 에러: {e}")
        return "인식 실패"

    try:
        text = r.recognize_google(audio, language='ko-KR')
        print(f"🎿 인식된 텍스트: {text}")
        return text
    except sr.UnknownValueError:
        return "인식 실패"
    except sr.RequestError as e:
        return f"API 오류: {e}"
# ===== MQTT 명령 전송 함수 =====
def send_esp32_command(command):
    try:
        mqtt_client.publish(MQTT_TOPIC, command)
        print(f"MQTT 명령 전송: {command}")
    except Exception as e:
        print(f"MQTT 명령 전송 오류: {e}")

# ===== 음성 인식 함수 =====
def listen_command():
    r = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            print("🎤 음성 입력 대기 중...")
            audio = r.listen(source, timeout=5, phrase_time_limit=7)
    except Exception as e:
        print(f"마이크 에러: {e}")
        return "인식 실패"

    try:
        text = r.recognize_google(audio, language='ko-KR')
        print(f"🎿 인식된 텍스트: {text}")
        return text
    except sr.UnknownValueError:
        return "인식 실패"
    except sr.RequestError as e:
        return f"API 오류: {e}"
    
