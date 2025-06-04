import requests
import json

def send_command_to_esp32(command: str):
    url = "http://172.20.10.7/api/data"  # ESP32의 IP와 경로
    payload = { "command": command }
    headers = { "Content-Type": "application/json" }

    print("[INFO] ESP32에 명령 전송 중:", payload)
    print("[INFO] 요청 URL:", url)

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=3)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            print("[ERROR] JSON 파싱 실패, 원본 응답:", response.text)
            return {"result": "fail", "error": "Invalid JSON response"}

        print("[SUCCESS] ESP32 응답:", data)
        return data

    except requests.exceptions.RequestException as e:
        print("[ERROR] 요청 실패:", e)
        return {"result": "fail", "error": str(e)}

if __name__ == "__main__":
    send_command_to_esp32("left")
