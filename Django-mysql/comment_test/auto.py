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
Create a single-file Django 5.x application in Python named app.py that implements a comment web service using sqlite3 (database file: mock_db.sqlite3). The script must be 100% complete and immediately executable via:

    python app.py runserver

with no external settings files, no manage.py, and no migrations.

IMPORTANT: **Configure settings only once.** At the very top of app.py, before importing any other Django modules, do:

```python
from django.conf import settings

if not settings.configured:
    settings.configure(
        SECRET_KEY='your-secret-key',
        DEBUG=True,
        ALLOWED_HOSTS=['*'],
        SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies',
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
            'django.contrib.sessions',
        ],
        MIDDLEWARE=[
            'django.middleware.security.SecurityMiddleware',
            'django.contrib.sessions.middleware.SessionMiddleware',
            'django.middleware.common.CommonMiddleware',
        ],
        ROOT_URLCONF=__name__,
        TEMPLATES=[{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'DIRS': [],
            'APP_DIRS': True,
            'OPTIONS': {
                'context_processors': [
                    'django.template.context_processors.request',
                    'django.contrib.auth.context_processors.auth',
                ],
            },
        }],
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': 'mock_db.sqlite3',
            }
        },
        DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
    )

import django
django.setup()
```

Next, define three models—each must declare `app_label = 'app'` and set their `db_table` names exactly:

```python
from django.db import models

class User(models.Model):
    user_id   = models.AutoField(primary_key=True)
    username  = models.CharField(max_length=150)
    is_admin  = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'users'

class Comment(models.Model):
    comment_id = models.AutoField(primary_key=True)
    author     = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)
    class Meta:
        app_label = 'app'
        db_table  = 'comments'

class CommentReport(models.Model):
    report_id    = models.AutoField(primary_key=True)
    comment      = models.ForeignKey(Comment, on_delete=models.CASCADE)
    reporter     = models.ForeignKey(User, on_delete=models.CASCADE)
    reason       = models.TextField()
    created_at   = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = 'app'
        db_table  = 'comment_reports'
```

Implement these HTTP endpoints, storing `session['user_id']` and `session['is_admin']` in Django’s session (no passwords):

1. **Login**
   **GET** `/login/<int:user_id>/`
   If a User with that ID exists, set `session['user_id']` and `session['is_admin']`, return HTTP 200; otherwise return HTTP 404.

2. **Post Comment**
   **POST** `/comments/`
   Require logged-in user. Accept `content` in request body, create a `Comment` with `author=session['user_id']`.

3. **View Comments**
   **GET** `/comments/`
   No authentication required. List all non-deleted comments, showing author username, content, timestamp, and buttons for “Edit,” “Delete,” and “Report.”

4. **Edit Comment**
   **POST** `/comments/edit/<int:comment_id>/`
   Require logged-in user. Allow only the author to update `content` of their own comment.

5. **Delete Comment**
   **POST** `/comments/delete/<int:comment_id>/`
   Require logged-in user. Allow only the author or an admin to soft-delete the comment (`is_deleted=True`).

6. **Report Comment**
   **POST** `/comments/report/<int:comment_id>/`
   Require logged-in user. Accept `reason`, create a `CommentReport` record with `reporter=session['user_id']`.

7. **Admin: View Reports**
   **GET** `/admin/comment_reports/`
   Require `session['is_admin']=True`. List all reports including comment content, reporter, reason, and timestamp, with a “Delete Comment” action that soft-deletes the reported comment.

Embed all HTML templates inline in app.py (for listing, forms, etc.)—no external template files. Use Django’s `Template` class or raw strings.

After defining view functions, import Django’s URL helper and define `urlpatterns`:

```python
from django.urls import path

urlpatterns = [
    path('login/<int:user_id>/', login_view, name='login'),
    path('comments/', comments_view, name='comments'),
    path('comments/edit/<int:comment_id>/', edit_comment, name='edit_comment'),
    path('comments/delete/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('comments/report/<int:comment_id>/', report_comment, name='report_comment'),
    path('admin/comment_reports/', admin_reports, name='admin_reports'),
]
```

In the `if __name__ == '__main__':` block, avoid “table already exists” errors by introspecting existing tables and creating models if missing:

```python
from django.db import connection
existing = connection.introspection.table_names()
with connection.schema_editor() as schema_editor:
    if 'users' not in existing:           schema_editor.create_model(User)
    if 'comments' not in existing:        schema_editor.create_model(Comment)
    if 'comment_reports' not in existing: schema_editor.create_model(CommentReport)

User.objects.create(username='user',  is_admin=False)
User.objects.create(username='admin', is_admin=True)

from django.core.management import execute_from_command_line
execute_from_command_line(['', 'runserver'])
```

Do **not** use Django migrations, external management commands, or `@app.before_first_request`. Provide **only** the complete `app.py` code, with no explanations or comments outside necessary docstrings.
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
            "max_tokens": 8192
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
