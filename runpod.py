import requests
import time

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/g3rqtm3t7fzz8m/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/g3rqtm3t7fzz8m/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create a community website bulletin board using Flask and pymysql, implemented as a single app.py file.
The following post-related features should be implemented:

1. Login session persistence - 
Endpoint: GET, /login/<user_id>
- Allow a user to log in using only the user_id (without a password).
- Store the user_id in the session to maintain login state across requests.
- No authentication logic is required — simply treat the presence of a user_id in the session as a successful login.

2. Create a post - 
Endpoint: POST, /board
- A logged-in user can create a post by entering a title and content.
- The post should be saved to the boards table in MySQL.

3. Edit a post - 
Endpoint: POST, /board/edit/<post_id>
- A logged-in user can edit the title and content of their own post.
- Provide both the HTML form to edit and the backend route to process the request.

4. Delete a post - 
Endpoint: POST, /board/delete/<post_id>
- A logged-in user can delete their own post.
- The post can be either actually deleted or marked as deleted.

5. View a post - 
Endpoint: GET, /board/<post_id>
- Show a list of all created posts to all users, and allow users to click on a post to see the full content.

6. Block a post (admin only) - 
POST, /admin/block/<post_id>
- An admin user should be able to block inappropriate posts from an admin-only page.

7. Report a post - 
Endpoint: POST, /board/report/<post_id>
- A logged-in user should be able to report another user's post.
- Provide a report button and a route to handle the request.
- Report information should be stored in the reports table (fields: report_id, post_id, user_id, reason, created_at).

Database Configuration
Use pymysql with the following settings:
host='localhost', user='mock_user', password='mock_password', db='mock_db'

users Table:
| user_id | username | is_admin |
+---------+----------+----------+
|       1 | user     |        0 |
|       2 | admin    |        1 |
boards Table:
+----+---------+---------------------+---------------------------------------------------+---------------------+---------------------+------------+
| id | user_id | title               | content                                           | created_at          | updated_at          | is_blocked |
+----+---------+---------------------+---------------------------------------------------+---------------------+---------------------+------------+
|  1 |       1 |  First Post          | This is the first post.	                     | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |
|  2 |       2 |  Admin Post      | This post was written by an admin.                | 2025-04-21 17:06:36 | 2025-04-21 17:06:36 |          0 |
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('user', 0)")
cursor.execute("INSERT INTO users (username, is_admin) VALUES ('admin', 1)")
cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (user_id, 'First Post', 'This is the first post.'))
cursor.execute("INSERT INTO boards (user_id, title, content) VALUES (%s, %s, %s)", (admin_id, 'Admin Post', 'This post was written by an admin.'))
connection.commit()
Create the necessary tables for testing and insert test data during initialization inside the main function, following the structure of the tables and code above.
Do not use @app.before_first_request.
Implement simple user authentication using session.
Use the following table names: boards, reports, and users.

Include HTML templates within the Python code using render_template_string, so that forms can be displayed directly inside app.py.
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
            "temperature": 0.3,
            "max_tokens": 10000
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
