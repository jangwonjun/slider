from flask import Flask, jsonify, render_template
import requests
import time
import pyttsx3
import threading
import re
import speech_recognition as sr
from google.cloud import speech

app = Flask(__name__)

tts_engine = pyttsx3.init()
tts_lock = threading.Lock()
slots = {}

ESP32_URL = "http://192.168.0.50"  # ESP32 주소

def speak(text):
    with tts_lock:
        tts_engine.say(text)
        tts_engine.runAndWait()

def send_to_esp32(slot_value):
    try:
        response = requests.post(f"{ESP32_URL}/move", json={"slot": slot_value})
        if response.status_code == 200:
            print("✅ ESP32로 명령 전송 성공")
        else:
            print(f"❌ ESP32 응답 오류: {response.status_code}")
    except Exception as e:
        print(f"ESP32 통신 실패: {e}")

def listen_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 음성 입력 대기 중...")
        audio = r.listen(source)

    with open("audio.wav", "wb") as f:
        f.write(audio.get_wav_data())

    try:
        # Google Cloud Speech-to-Text 클라이언트 초기화
        client = speech.SpeechClient()

        with open("audio.wav", "rb") as audio_file:
            content = audio_file.read()

        audio_data = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,  # 마이크 샘플링레이트 맞춰야함
            language_code="ko-KR",
        )

        response = client.recognize(config=config, audio=audio_data)

        if response.results:
            result_text = response.results[0].alternatives[0].transcript
            print(f"🧠 Google Speech 인식 결과: {result_text}")
            return result_text
        else:
            print("음성 인식 결과 없음")
            return "인식 실패"

    except Exception as e:
        print(f"Google Speech 오류: {e}")
        return "인식 실패"

def process_voice_command():
    text = listen_command()
    print(f"받은 음성 명령: {text}")

    if text.startswith("저장"):
        try:
            content = text[2:].strip()
            slot_num_match = re.search(r'(\d+)', content)
            if not slot_num_match:
                speak("슬롯 번호가 인식되지 않았습니다.")
                return
            slot_num = int(slot_num_match.group(1))
            slot_name = content[:slot_num_match.start()].strip()
            if not slot_name:
                speak("슬롯 이름이 인식되지 않았습니다.")
                return

            slots[slot_name] = slot_num
            send_to_esp32(slot_num * 1000)
            speak(f"{slot_name} 슬롯을 {slot_num}번 위치에 저장했습니다.")
            time.sleep(1)
            send_to_esp32(slot_num * 1000)
            speak("카드가 정상적으로 보관되었습니다. 설정이 완료되었습니다!")
        except Exception as e:
            speak("저장 명령 처리 중 오류가 발생했습니다.")
            print(f"저장 명령 오류: {e}")

    elif text.startswith("삭제"):
        try:
            slot_name = text[2:].strip()
            if slot_name in slots:
                del slots[slot_name]
                speak(f"{slot_name} 슬롯을 삭제했습니다.")
            else:
                speak(f"{slot_name} 슬롯이 없습니다.")
        except Exception as e:
            speak("삭제 명령 처리 중 오류가 발생했습니다.")
            print(f"삭제 명령 오류: {e}")

    elif text in slots:
        pos = slots[text]
        send_to_esp32(pos * 1000)
        speak(f"{text} 슬롯으로 이동합니다.")
    else:
        speak("명령을 이해하지 못했습니다.")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/listen")
def listen():
    threading.Thread(target=process_voice_command).start()
    return jsonify({"status": "음성 명령 인식 시작"})

@app.route("/slots")
def get_slots():
    return jsonify(slots)

if __name__ == "__main__":
    app.run(debug=True)
