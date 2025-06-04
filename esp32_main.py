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
import requests

app = Flask(__name__)

# ===== MQTT 설정 =====
MQTT_BROKER = "voicecardwallet.r-e.kr"
MQTT_PORT = 8883
MQTT_TOPIC = "esp32/commands"
HTTP_COMMAND_URL = "https://voicecardwallet.r-e.kr/set_command"

slot_num_to_cmd = {
    1: "r",
    2: "s",
    3: "l"
}


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("MQTT 브로커 연결 성공")
    else:
        print(f"MQTT 연결 실패, 코드: {rc}")



# ===== TTS 엔진 =====
tts_engine = pyttsx3.init()
tts_lock = threading.Lock()

# ===== 슬롯 저장 =====
slots = {}

# ===== KoGPT2 모델 로딩 =====
tokenizer = PreTrainedTokenizerFast.from_pretrained("skt/kogpt2-base-v2")
model = GPT2LMHeadModel.from_pretrained("skt/kogpt2-base-v2")
model.eval()

# ===== 동의어 그룹 처리 =====
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

def speak(text):
    with tts_lock:
        tts_engine.say(text)
        tts_engine.runAndWait()


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

def get_embedding(text):
    inputs = tokenizer(text, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs, output_hidden_states=True)
    last_hidden = outputs.hidden_states[-1]
    sentence_embedding = torch.mean(last_hidden, dim=1).squeeze().cpu().numpy()
    return sentence_embedding

command_templates = {
    "save": "저장 롯데카드 1 저장 삼성카드 2번 저장 민증 3",
    "delete": "삭제 롯데카드 삭제 민증 삭제 삼성카드",
    "move": "롯데카드 민증 삼성카드 이동"
}
command_embeddings = {k: get_embedding(v) for k, v in command_templates.items()}

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def classify_command(text):
    keywords = {"save": "저장", "delete": "삭제", "move": "이동"}
    for key, kw in keywords.items():
        if kw in text:
            return key
    emb_text = get_embedding(text)
    sims = {k: cosine_similarity(emb_text, emb) for k, emb in command_embeddings.items()}
    return max(sims, key=sims.get)

def parse_slots(text):
    pattern_save = r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*(\d+)\s*저장"
    pattern_delete = r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*삭제"
    pattern_move = r"((?:주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*\d+\s*)+이동"

    slots_local = {}

    if "저장" in text:
        for match in re.finditer(pattern_save, text):
            card, num = match.groups()
            slots_local[find_canonical_name(card)] = int(num)
    elif "삭제" in text:
        for match in re.finditer(pattern_delete, text):
            card = find_canonical_name(match.group(1))
            slots_local[card] = slots.get(card, 0)
    elif "이동" in text:
        move_part = re.search(pattern_move, text)
        if move_part:
            pairs = re.findall(r"(주민등록증|민증|등록증|롯데카드|롯데|삼성카드|삼성)\s*(\d+)", move_part.group(0))
            for card, num in pairs:
                slots_local[find_canonical_name(card)] = int(num)
    return slots_local

def process_text_command(text):
    cmd_type = classify_command(text)

    if cmd_type == "save":
        content = text.replace("저장", "").strip()
        slot_num_match = re.search(r'(\d+)', content)
        if not slot_num_match:
            return {"result": "fail", "message": "번호 인식 실패"}
        slot_num = int(slot_num_match.group(1))
        slot_name = content[:slot_num_match.start()].strip()
        if not slot_name:
            return {"result": "fail", "message": "이름 인식 실패"}

        slot_name = find_canonical_name(slot_name)
        slots[slot_name] = slot_num
        command_char = slot_num_to_cmd[slot_num]
        response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
        print(f"🔄 요청 보냄 → {command_char}")
        print(f"📬 응답 코드: {response.status_code}")
        print(f"📨 응답 본문: {response.text}")
        return {"result": "success", "message": f"{slot_name} → {slot_num} 저장 완료"}

    elif cmd_type == "delete":
        slot_name = find_canonical_name(text.replace("삭제", "").strip())
        if slot_name in slots:
            slot_num = slots[slot_name]
            command_char = slot_num_to_cmd[slot_num]
            del slots[slot_name]
            response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
            print(f"🔄 요청 보냄 → {command_char}")
            print(f"📬 응답 코드: {response.status_code}")
            print(f"📨 응답 본문: {response.text}")
            return {"result": "success", "message": f"{slot_name} 삭제 완료"}
        return {"result": "fail", "message": "해당 슬롯 없음"}

    elif cmd_type == "move":
        slot_name = find_canonical_name(text.strip())
        if slot_name in slots:
            slot_num = slots[slot_name]
            command_char = slot_num_to_cmd[slot_num]
            response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
            print(f"🔄 요청 보냄 → {command_char}")
            print(f"📬 응답 코드: {response.status_code}")
            print(f"📨 응답 본문: {response.text}")
            return {"result": "success", "message": f"{slot_name} 이동 완료"}
        return {"result": "fail", "message": "해당 슬롯 없음"}

    return {"result": "fail", "message": "명령 분류 실패"}

def process_voice_command():
    text = listen_command()
    if text == "인식 실패":
        return {"result": "fail", "message": "음성 인식 실패"}

    cmd_type = classify_command(text)
    new_slots = parse_slots(text)

    if cmd_type == "save":
        for card, num in new_slots.items():
            slots[card] = num
            command_char = slot_num_to_cmd[num]
            response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
            print(f"🔄 요청 보냄 → {command_char}")
            print(f"📬 응답 코드: {response.status_code}")
            print(f"📨 응답 본문: {response.text}")

    elif cmd_type == "delete":
        for card in new_slots.keys():
            if card in slots:
                num = slots[card]
                command_char = slot_num_to_cmd[num]
                response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
                print(f"🔄 요청 보냄 → {command_char}")
                print(f"📬 응답 코드: {response.status_code}")
                print(f"📨 응답 본문: {response.text}")
                del slots[card]

    elif cmd_type == "move":
        for card in new_slots.keys():
            if card in slots:
                num = slots[card]
                command_char = slot_num_to_cmd[num]
                response = requests.post(HTTP_COMMAND_URL, json={"command": command_char})
                print(f"🔄 요청 보냄 → {command_char}")
                print(f"📬 응답 코드: {response.status_code}")
                print(f"📨 응답 본문: {response.text}")
    else:
        return {"result": "fail", "message": "알 수 없는 명령"}

    print(f"📦 현재 슬롯 상태: {slots}")
    return {"result": "success", "message": f"{cmd_type} 명령 처리 완료"}




# ===== 웹 라우트 =====

@app.route("/")
def index():
    return render_template("index.html")

current_command = {"command": "none"}
command_acknowledged = False

@app.route("/command", methods=["GET"])
def command():
    global current_command, command_acknowledged

    if not command_acknowledged and current_command["command"] != "none":
        return jsonify(current_command)
    else:
        return jsonify({"command": "none"})

@app.route("/set_command", methods=["POST"])
def set_command():
    global current_command, command_acknowledged

    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"error": "No command provided"}), 400

    current_command = {"command": data["command"]}
    command_acknowledged = False
    return jsonify({"status": "ok", "command": current_command})

@app.route("/ack", methods=["POST"])
def ack_command():
    global current_command, command_acknowledged

    data = request.get_json()
    if not data or "ack" not in data or not data["ack"]:
        return jsonify({"error": "No acknowledgment provided"}), 400

    # ESP32가 ack 보냈으니 명령 초기화
    command_acknowledged = True
    current_command = {"command": "none"}
    return jsonify({"status": "acknowledged"})

@app.route("/slots")
def get_slots():
    # 예: {"주민등록증": 3, "롯데카드": 1, "삼성카드": 2}
    return jsonify(slots)

@app.route("/listen", methods=["POST"])
def listen():
    data = request.get_json()
    if not data or "command" not in data:
        return jsonify({"result": "fail", "message": "명령어가 없습니다."}), 400

    text_command = data["command"]
    print(f"클라이언트에서 받은 명령어: {text_command}")
    result = process_text_command(text_command)
    print(result)
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2506, debug=True)

