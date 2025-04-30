# import requests
# import yaml
# import pymysql
# from bs4 import BeautifulSoup

# DB_CONFIG = {
#     'host': 'localhost',
#     'user': 'mock_user',
#     'password': '1234',
#     'db': 'mock_db',
#     'charset': 'utf8mb4',
#     'cursorclass': pymysql.cursors.DictCursor
# }

# session = requests.Session()

# def login(base_url, username, password):
#     return session.post(f"{base_url}/login", data={'username': username, 'password': password})

# def check_db_user(username):
#     with pymysql.connect(**DB_CONFIG) as conn:
#         with conn.cursor() as cursor:
#             cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
#             return cursor.fetchone()

# def evaluate_response(test, response):
#     if response.status_code != test['expected_status']:
#         return "❌ 취약", f"예상 상태코드 {test['expected_status']}이 아닌 {response.status_code} 반환됨"
#     if test.get("expect_login") is False and "로그아웃" in response.text:
#         return "❌ 취약", "로그인 우회 가능성이 있음"
#     return "✅ 안전", "요청 응답이 예상대로 처리됨"

# def run_test(base_url, test):
#     print(f"[Test ID: {test['id']}] {test['title']}")

#     if test.get("login"):
#         login_resp = login(base_url, test['login']['username'], test['login']['password'])
#         if login_resp.status_code != 200:
#             print("⚠️ 로그인 실패 - 테스트 건너뜀")
#             return

#     method = test['method'].upper()
#     url = base_url + test['endpoint']
#     data = test.get("data", {})
#     response = session.post(url, data=data) if method == "POST" else session.get(url, params=data)

#     status, reason = evaluate_response(test, response)
#     print(f"Status Code: {response.status_code}")

#     if test.get("check_db"):
#         username = data.get("username")
#         result = check_db_user(username)
#         if result:
#             if any(x in result['username'] for x in ['<script>', '<img', "'"]):
#                 status, reason = "❌ 취약", f"DB에 악성 데이터가 삽입됨 (user_id: {result['id']})"
#             else:
#                 reason += " + DB 저장 정상 확인됨"

#     print(f"결과: {status}")
#     print(f"이유: {reason}")
#     print("-" * 50)

# if __name__ == "__main__":
#     with open("scenario.yaml", "r", encoding="utf-8") as f:
#         scenario = yaml.safe_load(f)

#     base_url = scenario['base_url']
#     for test in scenario['tests']:
#         run_test(base_url, test)


import requests
import yaml
<<<<<<< HEAD:flask-mysql/member_test/security_test.py
import pymysql
from bs4 import BeautifulSoup

DB_CONFIG = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': '1234',
    'db': 'mock_db',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
=======
import sqlite3
>>>>>>> origin/main:flask-sqlite/member_test/security_test.py

DB_PATH = 'mock_db.sqlite3'
session = requests.Session()

def login(base_url, username, password):
    return session.post(f"{base_url}/login", data={'username': username, 'password': password}, allow_redirects=True)

def logout(base_url):
    return session.get(f"{base_url}/logout", allow_redirects=True)

def check_db_user(username):
<<<<<<< HEAD:flask-mysql/member_test/security_test.py
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE username = %s AND is_deleted=FALSE", (username,))
            return cursor.fetchone()

def evaluate_response(test, response):
    if response.status_code != test['expected_status']:
        return "❌ 취약", f"예상 상태코드 {test['expected_status']}이 아닌 {response.status_code} 반환됨"
    if test.get("expect_login") is False and "Logout" in response.text:
        return "❌ 취약", "로그인 우회 가능성이 있음"
    return "✅ 안전", "요청 응답이 예상대로 처리됨"
=======
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cursor.fetchone()
    finally:
        conn.close()

def evaluate_response(test, response):
    if response.status_code != test['expected_status']:
        return "❌ 취약", f"예상 코드 {test['expected_status']}이 아닌 {response.status_code} 반환됨"
    if test.get('expect_login') is False and "로그아웃" in response.text:
        return "❌ 취약", "로그인 우회 가능성 있음"
    return "✅ 안전", "요청 응답 정상"
>>>>>>> origin/main:flask-sqlite/member_test/security_test.py

def run_test(base_url, test):
    print(f"[Test ID: {test['id']}] {test['title']}")

    # 필요 시 로그인
    if test.get("login"):
        login_resp = login(base_url, test['login']['username'], test['login']['password'])
        if login_resp.status_code != 200:
            print("⚠️ 로그인 실패 - 테스트 건너뜀")
            return
    else:
        # 로그인 필요 없으면 강제 로그아웃
        logout(base_url)

    method = test['method'].upper()
    url = base_url + test['endpoint']
<<<<<<< HEAD:flask-mysql/member_test/security_test.py
    data = test.get("data", {})

    # 요청 전송
    if method == "POST":
        response = session.post(url, data=data, allow_redirects=True)
    else:
        response = session.get(url, params=data, allow_redirects=True)
=======
    data = test.get('data', {})

    response = session.post(url, data=data) if method == "POST" else session.get(url, params=data)
>>>>>>> origin/main:flask-sqlite/member_test/security_test.py

    status, reason = evaluate_response(test, response)
    print(f"Status Code: {response.status_code}")

<<<<<<< HEAD:flask-mysql/member_test/security_test.py
    # DB 삽입 여부 확인
    if test.get("check_db"):
        username = data.get("username")
        if username:
            result = check_db_user(username)
            if result:
                if any(x in result['username'] for x in ['<script>', '<img', "'"]):
                    status, reason = "❌ 취약", f"DB에 악성 데이터 삽입됨 (user_id: {result['id']})"
                else:
                    reason += " + DB 정상 저장 확인"
            else:
                status, reason = "❌ 취약", "DB에 예상한 데이터가 저장되지 않음"
=======
    if test.get('check_db'):
        username = data.get('username')
        result = check_db_user(username)
        if result:
            if any(tag in result['username'] for tag in ['<script>', '<img', "'"]):
                status, reason = "❌ 취약", f"DB에 악성 데이터 삽입됨 (user_id: {result['id']})"
            else:
                reason += " + DB 저장 정상"
>>>>>>> origin/main:flask-sqlite/member_test/security_test.py

    print(f"결과: {status}")
    print(f"이유: {reason}")
    print("-" * 50)

if __name__ == "__main__":
    with open("scenario.yaml", "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    base_url = scenario['base_url']
    for test in scenario['tests']:
        run_test(base_url, test)
