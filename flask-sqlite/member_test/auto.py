import requests
import time
import os
import re
import subprocess
import hashlib

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 긴 프롬프트 정의
user_prompt = """
Create a community website's member management service using Flask and SQLAlchemy, implemented as a single app.py file.
The following member-related features should be implemented:

1. Login Session Management -
Endpoint: GET /login/<member_id>
- Allow a member to log in using only the member_id (no password).
- Store both member_id and is_admin in the session.
- Redirect to the index page after successful login.
- Show appropriate error message for invalid member_id.
- Implement proper session security using Flask-Login.
- Use CSRF protection for all forms.

2. Member Registration -
Endpoint: POST /members/register
- Provide an inline HTML form with:
  * Username field (required, unique)
  * Email field (required, unique, with email format validation)
  * Password field (required, minimum 8 characters)
- Hash the password using Werkzeug's generate_password_hash with pbkdf2:sha256.
- Validate all input fields with proper error messages.
- Show success/error messages using Flask's flash messages.
- Redirect to login page after successful registration.
- Prevent duplicate usernames and emails.

3. View Member Profile -
Endpoint: GET /members/<member_id>
- Display member's profile information:
  * Username
  * Email
  * Registration date
  * Account status
  * Last update date
- Only allow viewing if logged in (use @login_required decorator).
- Show appropriate error for unauthorized access.
- Include navigation links to other pages.
- Add edit and delete buttons for own profile.

4. Update Member Profile -
Endpoint: POST /members/update
- Provide a form to update:
  * Username (unique)
  * Email (unique, valid format)
- Validate all input fields with proper error messages.
- Only allow updating own profile.
- Show success/error messages using flash.
- Redirect to profile page after update.
- Update the updated_at timestamp.

5. Delete Member Account -
Endpoint: POST /members/delete
- Show confirmation dialog before deletion.
- Mark account as deleted (soft delete).
- Clear session data after deletion.
- Show success message using flash.
- Redirect to registration page.
- Keep the record in database with is_deleted flag.

6. Admin Member Management -
Endpoint: POST /admin/deactivate_member/<member_id>
- Admin-only access control using is_admin flag.
- Ability to deactivate any member account.
- Show confirmation dialog.
- Log admin actions with timestamp.
- Show success/error messages using flash.
- Prevent admin from deactivating themselves.

7. Member List -
Endpoint: GET /members
- Display list of all active members.
- Show member details:
  * Username
  * Email
  * Registration date
  * Account status
  * Last update date
- Include pagination (10 items per page).
- Add search functionality for username and email.
- Show appropriate message for empty list.
- Add sorting options for all columns.
- Include export functionality for admin.

8. Index Page -
Endpoint: GET /
- Show welcome message with username if logged in.
- Display quick links to:
  * Login
  * Registration
  * Member list
  * Profile (if logged in)
  * Admin panel (if admin)
- Show appropriate content based on login status.
- Add logout button if logged in.

Security Requirements:
- Implement proper session management using Flask-Login
- Validate all user inputs using WTForms
- Prevent unauthorized access using @login_required
- Use SQLAlchemy for database operations
- Implement proper error handling with try-except
- Add CSRF protection using Flask-WTF
- Sanitize all output using Jinja2's escape filter
- Use secure password hashing with Werkzeug
- Implement rate limiting for login attempts
- Add request validation middleware

Database Configuration:
Use SQLAlchemy with the following model:

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

Initial Data:
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='user').first():
        user = User(username='user', email='user@example.com')
        user.set_password('user')
        db.session.add(user)
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.set_password('admin')
        db.session.add(admin)
    db.session.commit()

Implementation Requirements:
1. Use Flask-Login for authentication
2. Use Flask-WTF for forms and CSRF protection
3. Use SQLAlchemy for database operations
4. Use render_template_string for all HTML templates
5. Add proper error handling and user feedback
6. Implement input validation for all forms
7. Add appropriate navigation links
8. Use Bootstrap 5 for styling
9. Include proper comments in the code
10. Add logging for important actions
11. Implement proper session management
12. Add rate limiting for security
13. Use secure password hashing
14. Add request validation
15. Implement proper error pages

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
            "max_tokens": 4096
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
