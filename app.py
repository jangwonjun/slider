from flask import Flask, jsonify, render_template
import requests
import time
import pyttsx3
import speech_recognition as sr
import threading
import re

# KoGPT2 임포트
from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel
import torch

app = Flask(__name__)

# ESP32 IP 주소 및 포트
ESP32_IP = "192.168.0.100"
ESP32_PORT = 80

tts_engine = pyttsx3.init()
tts_lock = threading.Lock()

slots = {}

# 동의어 사전
synonyms = {
    "주민등록증": ["주민등록증", "민증", "등록증"],
    "롯데카드": ["롯데카드", "롯데"],
    "삼성카드": ["삼성카드", "삼성"],
    # 필요시 추가
}

def get_canonical_name(name):
    for key, syns in synonyms.items():
        if name in syns:
            return key
    return name

# KoGPT2 모델, 토크나이저 로딩 (필요시 사전 다운로드)
tokenizer = PreTrainedTokenizerFast.from_pretrained("skt/kogpt2-base-v2")
model = GPT2LMHeadModel.from_pretrained("skt/kogpt2-base-v2")
model.eval()

def speak(text):
    with tts_lock:
        tts_engine.say(text)
        tts_engine.runAndWait()

def send_esp32_command(command):
    url = f"http://{ESP32_IP}:{ESP32_PORT}/command"
    try:
        response = requests.post(url, json={"command": command}, timeout=3)
        if response.status_code == 200:
            print(f"ESP32 명령 전송 성공: {command}")
        else:
            print(f"ESP32 명령 전송 실패, 상태 코드: {response.status_code}")
    except requests.RequestException as e:
        print(f"ESP32 통신 오류: {e}")

def listen_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 음성 입력 대기 중...")
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio, language='ko-KR')
        print(f"🎧 인식된 텍스트: {text}")
        return text
    except sr.UnknownValueError:
        return "인식 실패"
    except sr.RequestError as e:
        return f"API 오류: {e}"

def kogpt2_classify(text):
    """
    KoGPT2 모델을 실제로 생성형 분류기로 사용하지 않고,
    간단히 명령어 타입(저장, 삭제, 이동)과 파라미터 추출.
    """
    text = text.strip()
    if text.startswith("저장"):
        content = text[2:].strip()
        m = re.match(r"(.+?)\s*(\d+)$", content)
        if m:
            name = get_canonical_name(m.group(1).strip())
            slot_num = int(m.group(2))
            return ("저장", name, slot_num)
        else:
            return ("오류", "슬롯 번호 인식 실패", None)
    elif text.startswith("삭제"):
        name = get_canonical_name(text[2:].strip())
        return ("삭제", name, None)
    else:
        name = get_canonical_name(text)
        return ("이동", name, None)

def process_command(text):
    cmd, name, num = kogpt2_classify(text)
    print(f"명령 분류 결과 -> cmd: {cmd}, name: {name}, num: {num}")

    if cmd == "저장":
        slots[name] = num
        send_esp32_command(f"M{num * 1000};")
        speak(f"{name} 슬롯을 {num}번 위치에 저장했습니다.")
        time.sleep(1)
        send_esp32_command(f"R{num * 1000};")
        speak("카드가 정상적으로 보관되었습니다. 설정이 완료되었습니다!")
    elif cmd == "삭제":
        if name in slots:
            del slots[name]
            speak(f"{name} 슬롯을 삭제했습니다.")
        else:
            speak(f"{name} 슬롯이 없습니다.")
    elif cmd == "이동":
        if name in slots:
            pos = slots[name]
            send_esp32_command(f"M{pos * 1000};")
            speak(f"{name} 슬롯으로 이동합니다.")
        else:
            speak(f"{name} 슬롯 정보가 없습니다.")
    else:
        speak("명령을 이해하지 못했습니다.")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/listen")
def listen():
    def worker():
        text = listen_command()
        print(f"받은 음성 명령: {text}")
        if text in ["인식 실패", "API 오류"]:
            speak("음성 인식에 실패했습니다. 다시 시도해 주세요.")
            return
        process_command(text)
    threading.Thread(target=worker).start()
    return jsonify({"status": "음성 명령 처리 중..."})

@app.route("/slots")
def get_slots():
    return jsonify(slots)

if __name__ == "__main__":
    app.run(debug=True)
