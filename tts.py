import pyttsx3
import threading

engine = pyttsx3.init()
lock = threading.Lock()

def speak(text):
    with lock:
        engine.say(text)
        engine.runAndWait()
