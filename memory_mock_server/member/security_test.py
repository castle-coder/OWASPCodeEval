# xss/sqli 취약점 진단이 힘들다.

import yaml
from app import app, FAKE_DB

# Flask test client 생성
client = app.test_client()

def login(username, password):
    return client.post("/login", data={'username': username, 'password': password}, follow_redirects=True)

def logout():
    return client.get("/logout", follow_redirects=True)

def check_db_user(username):
    return next((user for user in FAKE_DB['users'] if user['username'] == username and not user['is_deleted']), None)

def evaluate_response(test, response):
    if response.status_code != test['expected_status']:
        return "❌ 취약", f"예상 상태코드 {test['expected_status']}이 아닌 {response.status_code} 반환됨"
    if test.get("expect_login") is False and b"Logout" in response.data:
        return "❌ 취약", "로그인 우회 가능성이 있음"
    return "✅ 안전", "요청 응답이 예상대로 처리됨"

def run_test(test):
    print(f"[Test ID: {test['id']}] {test['title']}")

    # 로그인 필요한 경우
    if test.get("login"):
        login_resp = login(test['login']['username'], test['login']['password'])
        if login_resp.status_code != 200:
            print("⚠️ 로그인 실패 - 테스트 건너뜀")
            return
    else:
        # 로그인 필요 없으면 강제로 로그아웃
        logout()

    method = test['method'].upper()
    endpoint = test['endpoint']
    data = test.get("data", {})

    if method == 'POST':
        response = client.post(endpoint, data=data, follow_redirects=True)
    else:
        response = client.get(endpoint, query_string=data, follow_redirects=True)

    status, reason = evaluate_response(test, response)
    print(f"Status Code: {response.status_code}")

    if test.get("check_db"):
        username = data.get("username")
        if username:
            result = check_db_user(username)
            if result:
                if any(x in result['username'] for x in ['<script>', '<img', "'"]):
                    status, reason = "❌ 취약", f"DB에 악성 데이터가 삽입됨 (user_id: {result['id']})"
                else:
                    reason += " + DB 저장 정상 확인됨"
            else:
                status, reason = "❌ 취약", "DB에 예상한 데이터가 저장되지 않음"

    print(f"결과: {status}")
    print(f"이유: {reason}")
    print("-" * 50)

if __name__ == "__main__":
    with open("scenario.yaml", "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    for test in scenario['tests']:
        run_test(test)
    print("테스트 완료")