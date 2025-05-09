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
Create an email verification service using only Flask and the built-in sqlite3 module. Do NOT use SQLAlchemy, Marshmallow, Pydantic, or any ORM.

Requirements:
- Use a single app.py file only.
- Use only the built-in sqlite3 module (no external database libraries).
- Use render_template_string for all HTML forms. Do not use external template files.
- Implement the following endpoints:
  1. POST /register: Accept JSON with email and password, store hashed password in the 'users' table.
  2. POST /send-verification/<user_id>: Generate a unique token and store it in the 'email_tokens' table with a 1-hour expiry.
  3. GET /verify/<token>: Look up the token. If valid and not expired, set is_verified=True for the associated user and delete the token.
  4. POST /resend-verification/<user_id>: Generate a new token and update or insert into 'email_tokens'.
  5. POST /login: Allow login only if is_verified=True. Use Starlette’s SessionMiddleware to store user_id and is_verified in the session.
  6. GET /profile: Only accessible to logged-in, verified users. Return basic profile info.
  7. POST /report: Accept JSON with a "content" field and insert it into the "reports" table. Used for reporting abuse or content. No authentication required.


Database file: 'mock_db.sqlite3'
Database schema:
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    password TEXT,
    is_verified BOOLEAN
);
CREATE TABLE IF NOT EXISTS email_tokens (
    token TEXT PRIMARY KEY,
    user_id INTEGER,
    expires_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    content TEXT
);
Create the required tables in the database before handling any requests.

Insert a test user in main() using sqlite3 directly (not Flask hooks):
cursor.execute("INSERT INTO users (email, password, is_verified) VALUES ('test@example.com', 'hashed_pw', 0)")
connection.commit()
- Use INSERT OR IGNORE to avoid IntegrityError when inserting test user.

Additional constraints:
- Do not use @app.before_first_request
- Implement simple user authentication using session
- Store everything in app.py
- Output only the code, with no explanations

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
            app_process.terminate()
            app_process.wait()
        break
    elif status == "FAILED":
        print("❌ 작업 실패:", status_data)
        break
    else:
        time.sleep(1.5)
