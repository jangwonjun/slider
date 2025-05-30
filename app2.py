from flask import Flask, jsonify, render_template
import paho.mqtt.client as mqtt
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
MQTT_BROKER = "your.mqtt.broker.address"  # 실제 MQTT 브로커 주소로 변경하세요
MQTT_PORT = 1883
MQTT_TOPIC = "esp32/commands"  # ESP32가 구독하는 토픽

mqtt_client = mqtt.Client()

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

def find_canonical_name(name):
    name = name.strip()
    for group in synonym_groups:
        if name in group:
            return group[0]
    return name

# ===== 음성 합성 함수 =====
def speak(text):
    with tts_lock:
        tts_engine.say(text)
        tts_engine.runAndWait()

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
    with sr.Microphone() as source:
        print("🎤 음성 입력 대기 중...")
        audio = r.listen(source)
    try:
        text = r.recognize_google(audio, language='ko-KR')
        print(f"🎿 인식된 텍스트: {text}")
        return text
    except sr.UnknownValueError:
        return "인식 실패"
    except sr.RequestError as e:
        return f"API 오류: {e}"

# ===== 문장 임베딩 함수 =====
def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs, output_hidden_states=True)
    last_hidden = outputs.hidden_states[-1]
    sentence_embedding = torch.mean(last_hidden, dim=1).squeeze().cpu().numpy()
    return sentence_embedding

# ===== 명령 템플릿과 임베딩 =====
command_templates = {
    "save": "저장 롯데카드 1 저장 삼성카드 2번 저장 민증 3",
    "delete": "삭제 롯데카드 삭제 민증 삭제 삼성카드",
    "move": "롯데카드 민증 삼성카드 이동"
}
command_embeddings = {k: get_embedding(v) for k, v in command_templates.items()}

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# ===== 명령 분류 함수 =====
def classify_command(text):
    keywords = {"save": "저장", "delete": "삭제", "move": "이동"}
    for intent, keyword in keywords.items():
        if keyword in text:
            return intent

    emb = get_embedding(text)
    sims = {cmd: cosine_similarity(emb, command_embeddings[cmd]) for cmd in command_embeddings}
    best_cmd = max(sims, key=sims.get)
    print(f"AI 분류: {best_cmd} (유사도: {sims[best_cmd]:.3f})")
    return best_cmd

# ===== 명령 처리 함수 =====
def process_text_command(text):
    cmd_type = classify_command(text)

    if cmd_type == "save":
        content = text.replace("저장", "").strip()
        slot_num_match = re.search(r'(\d+)', content)
        if not slot_num_match:
            speak("슬롯 번호가 인식되지 않았습니다.")
            return
        slot_num = int(slot_num_match.group(1))
        slot_name = content[:slot_num_match.start()].strip()
        if not slot_name:
            speak("슬롯 이름이 인식되지 않았습니다.")
            return
        slot_name = find_canonical_name(slot_name)
        slots[slot_name] = slot_num
        send_esp32_command(f"M{slot_num * 1000};")
        speak(f"{slot_name} 슬롯을 {slot_num}번 위치에 저장했습니다.")
        time.sleep(1)
        send_esp32_command(f"R{slot_num * 1000};")
        speak("카드가 정상적으로 보관되었습니다. 설정이 완료되었습니다!")

    elif cmd_type == "delete":
        slot_name = text.replace("삭제", "").strip()
        slot_name = find_canonical_name(slot_name)
        if slot_name in slots:
            del slots[slot_name]
            speak(f"{slot_name} 슬롯을 삭제했습니다.")
        else:
            speak(f"{slot_name} 슬롯이 없습니다.")

    elif cmd_type == "move":
        slot_name = find_canonical_name(text.strip())
        if slot_name in slots:
            pos = slots[slot_name]
            send_esp32_command(f"M{pos * 1000};")
            speak(f"{slot_name} 슬롯으로 이동합니다.")
        else:
            speak("해당 슬롯이 없습니다. 다시 말씀해 주세요.")
    else:
        speak("명령을 이해하지 못했습니다.")

# ===== Flask 라우터 =====
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/listen")
def listen():
    def worker():
        text = listen_command()
        print(f"받은 음성 명령: {text}")
        if text == "인식 실패" or text.startswith("API 오류"):
            speak("음성 인식에 실패했습니다. 다시 시도해 주세요.")
            return
        process_text_command(text)
    threading.Thread(target=worker).start()
    return jsonify({"status": "listening..."})

@app.route("/slots")
def get_slots():
    return jsonify(slots)

if __name__ == "__main__":
    app.run(debug=True)
