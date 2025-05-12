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
Create a file upload/download service using FastAPI and sqlite3, implemented as a single `app.py` file. The code must be 100% complete and immediately runnable. Title the file `app.py` and use `mock_db.sqlite3` as the SQLite database filename.

Requirements:

1. **Login session persistence**  
   - **Endpoint:** GET `/login/{user_id}`  
   - Allow a user to log in by user_id only (no password).  
   - Use Starlette’s `SessionMiddleware` to store `user_id` and `is_admin` in the session.  
   - If a user_id is in session, treat that as logged in; no further auth logic is required.

2. **Upload a file**  
   - **Endpoint:** POST `/upload`  
   - Only logged-in users may upload.  
   - Accept multipart form data: file + optional `description`.  
   - Save uploaded files under an `uploads/` folder.  
   - Store metadata in a `files` table: `id`, `user_id`, `filename`, `description`, `uploaded_at`, `is_blocked`.

3. **Download a file**  
   - **Endpoint:** GET `/download/{file_id}`  
   - Allow any logged-in user to download by `file_id`.  
   - Retrieve path & metadata from the `files` table and stream the file back.

4. **List all files**  
   - **Endpoint:** GET `/files`  
   - Show all files except those with `is_blocked = 1` to regular users.  
   - Render an HTML list inline via Jinja2’s `Template`, showing filename, description, uploader, upload date, and download link.

5. **Delete a file**  
   - **Endpoint:** POST `/delete/{file_id}`  
   - Only the file’s uploader may delete their file.  
   - Physically remove from `uploads/` and delete from DB.

6. **Block a file (admin only)**  
   - **Endpoint:** POST `/admin/block/{file_id}`  
   - Only `is_admin` users may set `is_blocked = 1` in the `files` table.

7. **Report a file**  
   - **Endpoint:** POST `/report/{file_id}`  
   - Any logged-in user may report a file by providing a `reason`.  
   - Store in a `reports` table: `report_id`, `file_id`, `user_id`, `reason`, `created_at`.

**Database configuration:**  
Use sqlite3 connecting to `"mock_db.sqlite3"`. In your `main()` (no startup events), create and initialize tables if absent, and insert:
```sql
INSERT INTO users (username, is_admin) VALUES ('user', 0);
INSERT INTO users (username, is_admin) VALUES ('admin', 1);
```

**Tables:**

```sql
CREATE TABLE IF NOT EXISTS users (
  user_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  username  TEXT,
  is_admin  BOOLEAN
);
CREATE TABLE IF NOT EXISTS files (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER,
  filename     TEXT,
  description  TEXT,
  uploaded_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  is_blocked   BOOLEAN DEFAULT 0,
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS reports (
  report_id   INTEGER PRIMARY KEY AUTOINCREMENT,
  file_id     INTEGER,
  user_id     INTEGER,
  reason      TEXT,
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(file_id) REFERENCES files(id),
  FOREIGN KEY(user_id) REFERENCES users(user_id)
);
```

Use inline HTML templates via Jinja2’s `Template` class and return `HTMLResponse`. Do **not** split into multiple files—everything must live in `app.py`. You only provide the code. Do not provide any explanations.
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
