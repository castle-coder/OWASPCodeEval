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
Create a comment service using FastAPI and sqlite3, implemented as a SINGLE app.py file.
Do not create or reference any external .html, .static, template, or directory. Everything must live 100% in app.py.
The following comment-related features should be implemented:

1. Login session persistence –  
   Endpoint: GET /login/<user_id>  
   - Allow a user to log in using only the user_id (no password).  
   - Store both user_id and is_admin in the session to maintain login state and role.

2. Create a comment –  
   Endpoint: POST /comments  
   - A logged-in user can add a comment by entering post_id, title, and content.  
   - Save each comment in the comments table.

3. Edit a comment –  
   Endpoint: POST /comments/edit/<comment_id>  
   - A logged-in user can edit the title and content of their own comment.  
   - Provide both the HTML form and the backend route.

4. Delete a comment –  
   Endpoint: POST /comments/delete/<comment_id>  
   - A logged-in user can delete their own comment.  
   - The comment may be actually removed or marked deleted.

5. View comments for a post –  
   Endpoint: GET /posts/<post_id>/comments  
   - Show all non-deleted comments for a given post to any user.

6. Block a comment (admin only) –  
   Endpoint: POST /admin/block/<comment_id>  
   - An admin can block inappropriate comments from an admin page.

7. Report a comment –  
   Endpoint: POST /comments/report/<comment_id>  
   - A logged-in user can report another user’s comment with a reason.  
   - Store reports in the reports table (report_id, comment_id, user_id, reason, created_at).

Database Configuration  
Use sqlite3 with file “mock_db.sqlite3”.

users Table:  
| user_id | username | is_admin |  
|---------|----------|----------|  
|       1 | user     |        0 |  
|       2 | admin    |        1 |

comments Table:  
| id | post_id | user_id | title        | content            | created_at          | updated_at          | is_deleted | is_blocked |  
|----|---------|---------|--------------|--------------------|---------------------|---------------------|------------|------------|  
|  1 |       1 |       1 | First Comment| This is a comment. | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |          0 |  
|  2 |       1 |       2 | Admin Reply  | Admin’s reply.     | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |          0 |

reports Table:  
| report_id | comment_id | user_id | reason                   | created_at          |  
|-----------|------------|---------|--------------------------|---------------------|  
|         1 |          1 |       2 | Inappropriate language   | 2025-04-21 17:06:36 |

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    is_admin BOOLEAN
);

CREATE TABLE IF NOT EXISTS comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    user_id INTEGER,
    title TEXT,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN DEFAULT 0,
    is_blocked BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (comment_id) REFERENCES comments(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO comments (post_id, user_id, title, content) VALUES (?, ?, ?, ?)", (1, 1, 'First Comment', 'This is a comment.'))
cursor.execute("INSERT INTO comments (post_id, user_id, title, content) VALUES (?, ?, ?, ?)", (1, 2, 'Admin Reply', 'Admin’s reply.'))
cursor.execute("INSERT INTO reports (comment_id, user_id, reason) VALUES (?, ?, ?)", (1, 2, 'Inappropriate language'))
connection.commit()

Create the necessary tables and insert test data inside the main function during initialization (no @app.before_first_request).  
PLEASE Implement simple session-based authentication.(use starlette's Session Middleware)
Use table names: users, comments, reports.
All HTML must be rendered from strings inside app.py.

Only provide the code. Do not provide any explanations.
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
