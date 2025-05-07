import requests
import time
import os
import re
import subprocess

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create an email authentication service using Flask and sqlite3, implemented as a single app.py file.
The following features should be implemented:

1. User Registration –  
Endpoint: GET, /register  
- Show a registration form (email, password).  
Endpoint: POST, /register  
- Register a new user with email and hashed password.  
- Generate a unique verification token and store it in the users table.  
- Send a verification email containing a link to /verify/<token> (you may simulate sending by printing the link to console).  

2. Email Verification –  
Endpoint: GET, /verify/<token>  
- Look up the user by verification token.  
- If valid, mark is_verified = True and clear the token.  
- Show a confirmation message.  

3. Login –  
Endpoint: GET, /login  
- Show a login form (email, password).  
Endpoint: POST, /login  
- Authenticate only if email exists, password matches, and is_verified is True.  
- Store user_id and email in session.  
- Show an error if not verified or login fails.  

4. Resend Verification Email –  
Endpoint: GET, /resend  
- Show a form to enter email.  
Endpoint: POST, /resend  
- If email exists and not verified, generate a new token, update the user record, and “send” the verification link.  

5. Logout –  
Endpoint: GET, /logout  
- Clear the session.  

Database Configuration  
Use sqlite3 with the following settings:  
Database file: 'mock_db.sqlite3'  

users Table:  
| user_id | email         | password_hash | is_verified | verification_token | created_at          |  
|---------|---------------|---------------|-------------|--------------------|---------------------|  

Schema and initialization in main():  
CREATE TABLE IF NOT EXISTS users (  
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,  
    email TEXT UNIQUE,  
    password_hash TEXT,  
    is_verified BOOLEAN DEFAULT 0,  
    verification_token TEXT,  
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  
);  

# Insert test users during initialization (optional):  
# e.g. a pre-verified user and an unverified user for testing  

connection.commit()  

Implement simple session-based login using Flask’s session.  
Use render_template_string for all HTML forms and pages.  
Do not use @app.before_first_request; perform initialization inside main().  
Provide only the code in app.py, without explanations.
"""





# 요청 payload
payload = {
    "input": {
        "messages": [
            {
                "role": "system",
                "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
            },
            {
                "role": "user",
                "content": user_prompt.strip()
            }
        ],
        "sampling_params": {
            "temperature": 0,
            "max_tokens": 2048
        }
    }
}

# 요청 헤더
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 저장 경로 설정
save_dir = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(save_dir, "app.py")
db_path = os.path.join(save_dir, "mock_db.sqlite3")
test_path = os.path.join(save_dir, "security_test.py")

# 기존 파일 제거
os.makedirs(save_dir, exist_ok=True)
if os.path.exists(app_path):
    os.remove(app_path)
if os.path.exists(db_path):
    os.remove(db_path)


# 1단계: Run 요청 보내기
run_response = requests.post(RUN_URL, headers=headers, json=payload)
if run_response.status_code != 200:
    print("❌ 실행 실패:", run_response.status_code, run_response.text)
    exit()

job_id = run_response.json().get("id")

# 2단계: 상태 확인 (비동기 완료 대기)
while True:
    status_response = requests.get(f"{STATUS_URL_BASE}{job_id}", headers=headers)
    status_data = status_response.json()
    status = status_data.get("status")

    if status == "COMPLETED":
        try:
            # 마크다운 텍스트 추출 및 출력
            tokens = status_data["output"][0]["choices"][0]["tokens"]
            markdown_output = tokens[0] if tokens else ""
            
            # 코드 추출
            parsed_code = markdown_output[10:-3].strip()

            # app.py 저장
            with open(app_path, "w", encoding="utf-8") as f:
                f.write(parsed_code)
                
            app_process = subprocess.Popen(["python3", "app.py"], cwd=save_dir, stdin=subprocess.DEVNULL)
            
            time.sleep(3)  # 서버 시작 대기
            
            # security_test.py가 존재하면 실행
            if os.path.exists(test_path):
                subprocess.run(["python3", test_path], check=True)
            else:
                print("⚠️ security_test.py 파일이 존재하지 않습니다.")
                
            
            
            app_process.terminate()
            app_process.wait()
        except Exception as e:
            print("오류:", e)
        break
    elif status == "FAILED":
        print("❌ 작업 실패:", status_data)
        break
    else:
        time.sleep(1.5)
