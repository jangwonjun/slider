from flask import Flask, jsonify, render_template
import threading
from slot_manager import process_text_command, slots
from tts import speak
import speech_recognition as sr

app = Flask(__name__)

def listen_command():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 음성 입력 대기 중...")
        audio = r.listen(source)
    try:
        return r.recognize_google(audio, language='ko-KR')
    except:
        return "인식 실패"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/listen")
def listen():
    def worker():
        text = listen_command()
        print(f"받은 명령어: {text}")
        if text == "인식 실패":
            speak("음성 인식 실패")
            return
        process_text_command(text)
    threading.Thread(target=worker).start()
    return jsonify({"status": "listening"})

@app.route("/slots")
def get_slots():
    return jsonify(slots)

if __name__ == "__main__":
    app.run(debug=True)
