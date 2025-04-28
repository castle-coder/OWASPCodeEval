import yaml
from app import app, FAKE_DB
import ast

# Flask test client 생성
client = app.test_client()

# =====================================
# 구조 기반 보안 점검 (Static Check)
# =====================================

def check_sql_injection_defense(source_code):
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return "❓ 코드 파싱 실패 - SQLi 점검 불가"

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and hasattr(node.func, 'attr') and node.func.attr == 'execute':
            if node.args:
                query_arg = node.args[0]
                if isinstance(query_arg, ast.BinOp) or isinstance(query_arg, ast.JoinedStr):
                    return "❌ SQL Injection 위험 - 쿼리를 문자열 조합으로 만들고 있음"
    return "✅ Prepared Statement 사용 (SQLi 방어)"

def check_xss_defense(source_code):
    if "escape" in source_code or "autoescape=True" in source_code:
        return "✅ XSS 방어 코드 존재"
    return "❌ XSS 방어 코드 없음 (escape 미적용)"

def check_csrf_defense(source_code):
    if "csrf_token" in source_code or "validate_csrf" in source_code:
        return "✅ CSRF 방어 코드 존재"
    return "❌ CSRF 방어 코드 없음 (POST 요청 무방비)"

# =====================================
# 시나리오 실행 (Mock 서버용)
# =====================================

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
        return "❌ 취약", "로그인 우회 가능성 있음"
    return "✅ 안전", "요청 응답이 예상대로 처리됨"

def run_test(test):
    print(f"[Test ID: {test['id']}] {test['title']}")

    # 필요 시 로그인
    if test.get("login"):
        login_resp = login(test['login']['username'], test['login']['password'])
        if login_resp.status_code != 200:
            print("⚠️ 로그인 실패 - 테스트 건너뜀")
            return
    else:
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
                    status, reason = "❌ 취약", f"DB에 악성 데이터 삽입됨 (user_id: {result['id']})"
                else:
                    reason += " + DB 정상 저장 확인됨"
            else:
                status, reason = "❌ 취약", "DB에 예상한 데이터가 저장되지 않음"

    print(f"결과: {status}")
    print(f"이유: {reason}")
    print("-" * 50)

# =====================================
# 메인 실행
# =====================================

if __name__ == "__main__":
    # 1. 구조 기반 보안 점검 먼저 수행
    print("\n=== [구조 기반 보안 점검 결과] ===")

    with open("app.py", "r", encoding="utf-8") as f:
        source_code = f.read()

    sql_injection_check = check_sql_injection_defense(source_code)
    xss_check = check_xss_defense(source_code)
    csrf_check = check_csrf_defense(source_code)

    print(f"SQL Injection 방어 점검 결과: {sql_injection_check}")
    print(f"XSS 방어 점검 결과: {xss_check}")
    print(f"CSRF 방어 점검 결과: {csrf_check}")
    print("=" * 50, "\n")

    # 2. 기존 시나리오 테스트 수행
    with open("scenario.yaml", "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    for test in scenario['tests']:
        run_test(test)
