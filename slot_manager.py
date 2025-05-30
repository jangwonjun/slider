import re
import time
from pattern import find_canonical_name
from tts import speak
from command_classifier import classify_command

slots = {}  # 글로벌 슬롯 저장소

def send_esp32_command(command):
    import requests
    url = "http://192.168.0.100:80/command"
    try:
        response = requests.post(url, json={"command": command}, timeout=3)
        if response.status_code == 200:
            print(f"ESP32 명령 전송 성공: {command}")
        else:
            print(f"ESP32 명령 전송 실패: {response.status_code}")
    except requests.RequestException as e:
        print(f"ESP32 통신 오류: {e}")

def process_text_command(text):
    cmd_type = classify_command(text)
    
    if cmd_type == "save":
        slot_num_match = re.search(r'(\d+)', text)
        if not slot_num_match:
            speak("슬롯 번호를 찾을 수 없습니다.")
            return
        slot_num = int(slot_num_match.group(1))
        name = text[:slot_num_match.start()].strip()
        name = find_canonical_name(name)
        slots[name] = slot_num
        send_esp32_command(f"M{slot_num * 1000};")
        speak(f"{name}를 {slot_num}번에 저장합니다.")
        time.sleep(1)
        send_esp32_command(f"R{slot_num * 1000};")
        speak("보관 완료!")

    elif cmd_type == "delete":
        name = find_canonical_name(text.replace("삭제", "").strip())
        if name in slots:
            del slots[name]
            speak(f"{name} 정보를 삭제했습니다.")
        else:
            speak(f"{name} 정보가 없습니다.")

    elif cmd_type == "move":
        name = find_canonical_name(text.strip())
        if name in slots:
            slot_num = slots[name]
            send_esp32_command(f"M{slot_num * 1000};")
            speak(f"{name}를 꺼냅니다.")
        else:
            speak(f"{name} 슬롯이 없습니다.")
