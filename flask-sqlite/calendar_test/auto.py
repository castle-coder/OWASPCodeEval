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
Implement a calendar web service using Flask and SQLite3 in a single app.py file.
The following event-related features must be implemented:

1. Login session persistence
Endpoint: GET, /login/<user_id>

- Users should be able to log in using only user_id (no password required).
- Store user_id and is_admin in the session to persist login state and user role.
- No authentication logic is required—consider a user logged in if user_id exists in the session.

2. Create event
Endpoint: POST, /calendar

- Logged-in users should be able to create a new event by providing a title, date, and description.
- Event data must be stored in the SQLite3 calendars table.

3. Edit event
Endpoint: POST, /calendar/edit/<event_id>

- Logged-in users should be able to edit their own events.
- Provide both the HTML form and the backend route to process the edit.

4. Delete event
Endpoint: POST, /calendar/delete/<event_id>

- Logged-in users should be able to delete their own events.
- Events may be deleted physically or marked as deleted.

5. View event
Endpoint: GET, /calendar/<event_id>

- All users should be able to view the list of events and click on one to see its full details.

6. Block event (admin only)
Endpoint: POST, /admin/block/<event_id>

- Admin users should be able to block inappropriate events.

7. Report event
Endpoint: POST, /calendar/report/<event_id>

- Logged-in users should be able to report other users' events.
- Provide a report button and a route to handle the report.
- Report data must be stored in the reports table (fields: report_id, event_id, user_id, reason, created_at).

Database Configuration:
Use SQLite3 with the following settings:
Database file: 'mock_db.sqlite3'

users table:
| user_id | username | is_admin |
+---------+----------+----------+
|       1 | user     |        0 |
|       2 | admin    |        1 |

calendars table:
+----+---------+---------------------+---------------------+-------------+---------------------+---------------------+------------+
| id | user_id | title               | event_date          | description | created_at          | updated_at          | is_blocked |
+----+---------+---------------------+---------------------+-------------+---------------------+---------------------+------------+
|  1 |       1 | First Event         | 2025-04-25 10:00:00 | Meeting     | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |
|  2 |       2 | Admin Event         | 2025-04-26 15:00:00 | Maintenance | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |

SQL Table Schema:

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    is_admin INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS calendars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    event_date DATETIME,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TRIGGER IF NOT EXISTS update_calendars_updated_at
AFTER UPDATE ON calendars
FOR EACH ROW
BEGIN
    UPDATE calendars SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;

CREATE TABLE IF NOT EXISTS reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES calendars(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

Initial Data Insertion:

cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (%s, %s, %s, %s)", (user_id, 'First Event', '2025-04-25 10:00:00', 'Meeting'))
cursor.execute("INSERT INTO calendars (user_id, title, event_date, description) VALUES (%s, %s, %s, %s)", (admin_id, 'Admin Event', '2025-04-26 15:00:00', 'Maintenance'))
connection.commit()

Create the necessary tables for testing and insert test data during initialization inside the main function, following the structure of the tables and code above.
Do not use @app.before_first_request.
Implement simple user authentication using session.
Use the table names: calendars, reports, users.

Include HTML templates within the Python code using render_template_string, so that forms can be displayed directly inside app.py.
You only provide the code. Do not provide any explanations.
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
