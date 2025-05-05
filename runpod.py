import requests
import time

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """ 
Create a community "board" web service using FastAPI and sqlite3 in a single file named app.py. Do not split the files

The service should implement the following features:

1. Login session persistence  
Endpoint: GET /login/<user_id>  
- Log in a user by user_id without requiring a password.  
- Store user_id and is_admin in session for identifying login state and permissions.

2. Create a post  
Endpoint: POST /board  
- Logged-in users can create posts with title and content.  
- Save posts in the boards table.

3. Edit a post  
Endpoint: POST /board/edit/<post_id>  
- Users can edit their own posts.  
- Provide HTML form and backend logic to update title and content.

4. Delete a post  
Endpoint: POST /board/delete/<post_id>  
- Users can delete their own posts (either hard delete or soft delete).

5. View a post  
Endpoint: GET /board/<post_id>  
- Show full post content.  
- Display a list of all posts to all users, linking to each post detail page.

6. Block a post (admin only)  
Endpoint: POST /admin/block/<post_id>  
- Admin users can block inappropriate posts via an admin-only interface.

7. Report a post  
Endpoint: POST /board/report/<post_id>  
- Logged-in users can report other users’ posts.  
- Include a report button and backend route.  
- Save reports to the reports table (report_id, post_id, user_id, reason, created_at).

Database settings:
- Use sqlite3
- DB file: mock_db.sqlite3

Table schemas:
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    is_admin BOOLEAN
);
CREATE TABLE IF NOT EXISTS boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);
CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES boards(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

Initial data setup:
- Insert sample users: ('user', is_admin=0), ('admin', is_admin=1)  
- Insert sample posts from each user  
- Do this inside the main() function (do not use @app.before_first_request)

Do not split code into multiple files or templates
Use render_template_string to define HTML templates inline within the code.  
Return only code, no explanations.
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
            "temperature": 0.0001,
            "max_tokens": 2048
        }
    }
}

# 요청 헤더
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 1단계: Run 요청 보내기
run_response = requests.post(RUN_URL, headers=headers, json=payload)
if run_response.status_code != 200:
    print("❌ 실행 실패:", run_response.status_code, run_response.text)
    exit()

job_id = run_response.json().get("id")
print(f"⏳ 작업 제출 완료! Job ID: {job_id}")

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
            print("\n✅ 마크다운 응답 결과:\n")
            print(markdown_output)
        except Exception as e:
            print("⚠️ 결과 파싱 오류:", e)
            print("전체 응답:", status_data)
        break
    elif status == "FAILED":
        print("❌ 작업 실패:", status_data)
        break
    else:
        print("⌛ 처리 중... 다시 확인")
        time.sleep(1.5)
