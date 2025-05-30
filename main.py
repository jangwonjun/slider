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
    for key, kw in keywords.items():
        if kw in text:
            return key
    # 유사도 기준으로 분류 (옵션)
    emb_text = get_embedding(text)
    sims = {k: cosine_similarity(emb_text, emb) for k, emb in command_embeddings.items()}
    return max(sims, key=sims.get)

# ===== 슬롯 추출 함수 =====
def parse_slots(text):
    # 저장 명령 예: "롯데카드 1 저장"
    pattern_save = r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*(\d+)\s*저장"
    # 삭제 명령 예: "롯데카드 삭제"
    pattern_delete = r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*삭제"
    # 이동 명령 예: "롯데카드 1 민증 2 삼성카드 3 이동"
    pattern_move = r"((?:주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*\d+\s*)+이동"

    slots_local = {}

    if "저장" in text:
        for match in re.finditer(pattern_save, text):
            card, num = match.groups()
            card = find_canonical_name(card)
            slots_local[card] = int(num)
    elif "삭제" in text:
        for match in re.finditer(pattern_delete, text):
            card = find_canonical_name(match.group(1))
            if card in slots_local:
                slots_local.pop(card, None)
            else:
                slots_local[card] = 0
    elif "이동" in text:
        # 이동 명령 처리
        move_part = re.search(pattern_move, text)
        if move_part:
            pairs = re.findall(r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*(\d+)", move_part.group(0))
            for card, num in pairs:
                card = find_canonical_name(card)
                slots_local[card] = int(num)

    return slots_local

# ===== 음성 명령 처리 쓰레드 함수 =====
def process_voice_command():
    text = listen_command()
    if text == "인식 실패":
        speak("음성 인식에 실패했습니다. 다시 시도해주세요.")
        return {"result": "fail", "message": "음성 인식 실패"}

    cmd_type = classify_command(text)
    new_slots = parse_slots(text)

    if cmd_type == "save":
        for card, num in new_slots.items():
            slots[card] = num
        speak("슬롯 정보를 저장했습니다.")
        send_esp32_command("save")
    elif cmd_type == "delete":
        for card in new_slots.keys():
            slots.pop(card, None)
        speak("슬롯 정보를 삭제했습니다.")
        send_esp32_command("delete")
    elif cmd_type == "move":
        # 모든 슬롯 정보 갱신
        for card, num in new_slots.items():
            slots[card] = num
        speak("슬롯 정보를 이동했습니다.")
        send_esp32_command("move")
    else:
        speak("명령을 인식하지 못했습니다.")
        return {"result": "fail", "message": "알 수 없는 명령"}

    print(f"현재 슬롯 상태: {slots}")
    return {"result": "success", "message": f"{cmd_type} 명령 처리 완료"}

# ===== 웹 라우트 =====
@app.route("/")
def index():
    return render_template("main.html")

@app.route("/slots")
def get_slots():
    # 예: {"주민등록증": 3, "롯데카드": 1, "삼성카드": 2}
    return jsonify(slots)

@app.route("/listen")
def listen():
    def target():
        global last_result
        last_result = process_voice_command()
    last_result = None
    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=20)  # 최대 20초 기다림
    if last_result is None:
        return jsonify({"result": "fail", "message": "시간 초과"}), 504
    return jsonify(last_result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2506, debug=True)
