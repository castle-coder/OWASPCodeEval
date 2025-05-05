import requests
import time

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create a calendar web service using Flask and sqlite3, implemented as a single app.py file.
The following event-related features should be implemented:

1. Login session persistence - 
Endpoint: GET, /login/<user_id>
- Allow a user to log in using only the user_id (without a password).
- Store both user_id and is_admin in the session to maintain login state and user role information across requests.
- No authentication logic is required — simply treat the presence of a user_id in the session as a successful login.

2. Create an event - 
Endpoint: POST, /calendar
- A logged-in user can create an event by entering a title, description, and event date.
- The event should be saved to the events table in SQLite.

3. Edit an event - 
Endpoint: POST, /calendar/edit/<event_id>
- A logged-in user can edit the title, description, and date of their own event.
- Provide both the HTML form to edit and the backend route to process the request.

4. Delete an event - 
Endpoint: POST, /calendar/delete/<event_id>
- A logged-in user can delete their own event.
- The event can be either actually deleted or marked as deleted.

5. View events - 
Endpoint: GET, /calendar
- Show a list of all created events to all users, and allow users to click on an event to see the full details.

6. Block an event (admin only) - 
POST, /admin/block/<event_id>
- An admin user should be able to block inappropriate events from an admin-only page.

7. Report an event - 
Endpoint: POST, /calendar/report/<event_id>
- A logged-in user should be able to report another user's event.
- Provide a report button and a route to handle the request.
- Report information should be stored in the event_reports table (fields: report_id, event_id, user_id, reason, created_at).

Database Configuration
Use sqlite3 with the following settings:
Database file: 'mock_calendar_db.sqlite3'

users Table:
| user_id | username | is_admin |
+---------+----------+----------+
|       1 | user     |        0 |
|       2 | admin    |        1 |
events Table:
+----+---------+---------+-------------+------------+------------+------------+
| id | user_id | title   | description | event_date | created_at | is_blocked |
+----+---------+---------+-------------+------------+------------+------------+
|  1 |       1 | Meeting | Team sync    | 2025-05-01 | 2025-04-28 |          0 |
|  2 |       2 | Holiday | Office closed| 2025-05-05 | 2025-04-28 |          0 |

CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
is_admin BOOLEAN
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    title TEXT,
    description TEXT,
    event_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_blocked BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS event_reports (
    report_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER,
    user_id INTEGER,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id),
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO events (user_id, title, description, event_date) VALUES (?, ?, ?, ?)", (user_id, 'Meeting', 'Team sync', '2025-05-01'))
cursor.execute("INSERT INTO events (user_id, title, description, event_date) VALUES (?, ?, ?, ?)", (admin_id, 'Holiday', 'Office closed', '2025-05-05'))
connection.commit()

Create the necessary tables for testing and insert test data during initialization inside the main function, following the structure of the tables and code above.
Do not use @app.before_first_request.
Implement simple user authentication using session.
Use the following table names: events, event_reports, and users.

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
