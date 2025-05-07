import requests
import yaml
import sqlite3
import os

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir,'mock_db.sqlite3')
session = requests.Session()

def login(base_url, username, password):
    return session.post(f"{base_url}/login", data={'username': username, 'password': password})

def check_db_user(username):
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

def run_test(base_url, test):
    print(f"[Test ID: {test['id']}] {test['title']}")

    if test.get("login"):
        login_resp = login(base_url, test['login']['username'], test['login']['password'])
        if login_resp.status_code != 200:
            print("⚠️ 로그인 실패 - 테스트 건너뜀")
            return

    method = test['method'].upper()
    url = base_url + test['endpoint']
    data = test.get('data', {})

    response = session.post(url, data=data) if method == "POST" else session.get(url, params=data)

    status, reason = evaluate_response(test, response)
    print(f"Status Code: {response.status_code}")

    if test.get('check_db'):
        username = data.get('username')
        result = check_db_user(username)
        if result:
            if any(tag in result['username'] for tag in ['<script>', '<img', "'"]):
                status, reason = "❌ 취약", f"DB에 악성 데이터 삽입됨 (user_id: {result['id']})"
            else:
                reason += " + DB 저장 정상"

    print(f"결과: {status}")
    print(f"이유: {reason}")
    print("-" * 50)

if __name__ == "__main__":
    # 현재 파일이 위치한 디렉토리 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 절대 경로로 scenario.yaml 접근
    yaml_path = os.path.join(base_dir, "scenario.yaml")

    with open(yaml_path, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    base_url = scenario['base_url']
    for test in scenario['tests']:
        run_test(base_url, test)
