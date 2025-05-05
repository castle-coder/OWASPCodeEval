import requests
import time

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create a notification web service using Flask and sqlite3, implemented as a single app.py file.
The following notification-related features should be implemented:

Login session persistence –
Endpoint: GET, /login/<user_id>

Allow a user to log in using only the user_id (without a password).

Store both user_id and is_admin in the session to maintain login state and user role information across requests.

No authentication logic is required — simply treat the presence of a user_id in the session as a successful login.

Send a notification –
Endpoint: POST, /notifications

A logged-in user can send a notification by entering a recipient_user_id and message.

The notification should be saved to the notifications table in SQLite with a timestamp and is_read defaulting to FALSE.

View notifications –
Endpoint: GET, /notifications

Show a list of all notifications for the logged-in user, including message, created_at timestamp, and read/unread status.

Mark as read –
Endpoint: POST, /notifications/read/<notification_id>

A logged-in user can mark their own notification as read.

Delete a notification –
Endpoint: POST, /notifications/delete/<notification_id>

A logged-in user can delete their own notification (either actually delete or mark as deleted).

Block a notification (admin only) –
Endpoint: POST, /admin/block_notification/<notification_id>

An admin user should be able to block inappropriate notifications from an admin-only page.

Report a notification –
Endpoint: POST, /notifications/report/<notification_id>

A logged-in user should be able to report another user’s notification.

Provide a report button and a route to handle the request.

Report information should be stored in the notification_reports table (fields: report_id, notification_id, user_id, reason, created_at).

Database Configuration
Use sqlite3 with the following settings:
Database file: ‘mock_db.sqlite3’

users Table:

user_id	username	is_admin
1	user	0
2	admin	1

CREATE TABLE IF NOT EXISTS users (
user_id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT,
is_admin BOOLEAN
);

notifications Table:

id	recipient_user_id	sender_user_id	message	created_at	is_read	is_blocked
1	1	2	“System update”	2025-04-30 15:00:00	0	0
2	2	1	“Hello, admin!”	2025-04-30 15:05:00	0	0

CREATE TABLE IF NOT EXISTS notifications (
id INTEGER PRIMARY KEY AUTOINCREMENT,
recipient_user_id INTEGER,
sender_user_id INTEGER,
message TEXT,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
is_read BOOLEAN DEFAULT 0,
is_blocked BOOLEAN DEFAULT 0,
FOREIGN KEY (recipient_user_id) REFERENCES users(user_id),
FOREIGN KEY (sender_user_id) REFERENCES users(user_id)
);

notification_reports Table:

report_id	notification_id	user_id	reason	created_at
1	1	1	“Spam content”	2025-04-30 16:00:00

CREATE TABLE IF NOT EXISTS notification_reports (
report_id INTEGER PRIMARY KEY AUTOINCREMENT,
notification_id INTEGER,
user_id INTEGER,
reason TEXT,
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
FOREIGN KEY (notification_id) REFERENCES notifications(id),
FOREIGN KEY (user_id) REFERENCES users(user_id)
);

cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?, ?, ?)", (1, 2, 'System update'))
cursor.execute("INSERT INTO notifications (recipient_user_id, sender_user_id, message) VALUES (?, ?, ?)", (2, 1, 'Hello, admin!'))
connection.commit()

Create the necessary tables for testing and insert test data during initialization inside the main function, following the structure above.
Do not use @app.before_first_request.
Implement simple user authentication using session.
Use the following table names: users, notifications, notification_reports.
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
