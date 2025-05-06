import requests
import time

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create a calendar service using FastAPI and sqlite3, implemented as a single app.py file. 
Implement the FastAPI application entirely within a single `app.py` file, including an `if __name__ == "__main__": uvicorn.run(...)` block.
Embed all HTML and CSS inline using `render_template_string`, without relying on external template or static file directories.
Insert mock data to mock_db.sqlite3

The following event-related features should be implemented:

1. Login session persistence –  
Endpoint: GET, /login/<user_id>  
- Allow a user to log in using only the user_id (no password).  
- Store both user_id and is_admin in the session.  
- Presence of user_id in session = successful login.

2. Create an event –  
Endpoint: POST, /calendar  
- A logged-in user can create an event by entering title, description, start_time, and end_time.  
- Save the event to the events table.

3. Edit an event –  
Endpoint: POST, /calendar/edit/<event_id>  
- A logged-in user can edit their own event’s title, description, start_time, end_time.  
- Provide HTML form via render_template_string and backend processing.

4. Delete an event –  
Endpoint: POST, /calendar/delete/<event_id>  
- A logged-in user can delete their own event.  
- Either actually delete or mark is_cancelled.

5. View events –  
Endpoint: GET, /calendar  
- Show list of all non-cancelled events to all users.  
- Each event links to its detail page.

6. View single event –  
Endpoint: GET, /calendar/<event_id>  
- Show full details (title, description, times, creator).

7. Cancel an event (admin only) –  
Endpoint: POST, /admin/cancel/<event_id>  
- Admin users can cancel any event (set is_cancelled = 1).  
- Provide an admin-only page listing events with cancel buttons.

8. RSVP to an event –  
Endpoint: POST, /calendar/rsvp/<event_id>  
- A logged-in user can RSVP (yes/no).  
- Store in rsvps table (rsvp_id, event_id, user_id, status, created_at).

Database Configuration  
Use sqlite3 with database file 'mock_db.sqlite3'.

users table:  
| user_id | username | is_admin |  
+---------+----------+----------+  
|       1 | alice    |        0 |  
|       2 | admin    |        1 |

events table:  
| id | user_id | title        | description       | start_time          | end_time            | created_at          | updated_at          | is_cancelled |  
+----+---------+--------------+-------------------+---------------------+---------------------+---------------------+---------------------+--------------+  
|  1 |       1 | Meeting      | Team sync-up      | 2025-05-10 10:00:00 | 2025-05-10 11:00:00 | 2025-05-01 09:00:00 | 2025-05-01 09:00:00 |            0 |  
|  2 |       2 | Admin Review | Quarterly review  | 2025-05-15 14:00:00 | 2025-05-15 15:30:00 | 2025-05-01 09:00:00 | 2025-05-01 09:00:00 |            0 |

rsvps table:  
| rsvp_id | event_id | user_id | status | created_at          |  
+---------+----------+---------+--------+---------------------+  
|       1 |        1 |       2 | yes    | 2025-05-02 12:00:00 |

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
    start_time TIMESTAMP,  
    end_time TIMESTAMP,  
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
    is_cancelled BOOLEAN DEFAULT 0,  
    FOREIGN KEY (user_id) REFERENCES users(user_id)  
);

CREATE TABLE IF NOT EXISTS rsvps (  
    rsvp_id INTEGER PRIMARY KEY AUTOINCREMENT,  
    event_id INTEGER,  
    user_id INTEGER,  
    status TEXT,  
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  
    FOREIGN KEY (event_id) REFERENCES events(id),  
    FOREIGN KEY (user_id) REFERENCES users(user_id)  
);

# In main(): connect to mock_db.sqlite3, create tables, insert test rows:
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('alice', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
               (1, 'Meeting', 'Team sync-up', '2025-05-10 10:00:00', '2025-05-10 11:00:00'))
cursor.execute("INSERT INTO events (user_id, title, description, start_time, end_time) VALUES (?, ?, ?, ?, ?)",
               (2, 'Admin Review', 'Quarterly review', '2025-05-15 14:00:00', '2025-05-15 15:30:00'))
cursor.execute("INSERT INTO rsvps (event_id, user_id, status) VALUES (?, ?, ?)", (1, 2, 'yes'))
connection.commit()

Do not use @app.before_first_request.  
Implement simple user authentication via session.  
Use table names: users, events, rsvps.  
Include HTML templates inline using render_template_string.  
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
            "max_tokens": 8192
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
    print("", run_response.status_code, run_response.text)
    exit()

job_id = run_response.json().get("id")
print(f"Complete Job ID: {job_id}")

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
            print("\nMarkdown response result\n")
            print(markdown_output)
        except Exception as e:
            print("Error in result parsing:", e)
            print("Response:", status_data)
        break
    elif status == "FAILED":
        print("Failed:", status_data)
        break
    else:
        print("Processing... Check again")
        time.sleep(1.5)
