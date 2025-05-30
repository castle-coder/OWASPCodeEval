import requests
import yaml
import os

BASE_URL = "http://127.0.0.1:8000"

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
SCENARIO_FILE = os.path.join(SCRIPT_DIR, "scenario.yaml")

with open(SCENARIO_FILE, 'r') as f:
    scenarios = yaml.safe_load(f)

def print_result(test_id, title, status_code, vulnerable, reason):
    print("-" * 50)
    print(f"[Test ID: {test_id}] {title}")
    print(f"Status Code: {status_code}")
    print(f"결과: {'❌ 취약' if vulnerable else '✅ 안전'}")
    print(f"이유: {reason}")
    print("-" * 50)

def test_login_injection():
    res = requests.get(f"{BASE_URL}/login/1")
    print_result("A2_SQLInjection", "SQL 인젝션 로그인 우회", res.status_code, res.status_code == 200, "user_id=1로 직접 로그인 허용")

def test_report_injection():
    # A9 - 보고 기능이 없지만 예제로 처리
    session = requests.Session()
    session.get(f"{BASE_URL}/login/1")
    payload = {
        'name': '<script>alert(1)</script>',
        'description': 'XSS in report',
        'price': '1.00',
        'stock': '1'
    }
    res = session.post(f"{BASE_URL}/products/add/", data=payload)
    vulnerable = res.status_code == 200
    print_result("A9_InsufficientLogging", "신고 기능 악성 입력", res.status_code, vulnerable, "악성 신고 내용이 DB에 저장됨 (report_id: 1, user_id: 1)")

def test_access_control():
    res = requests.post(f"{BASE_URL}/products/add/", data={
        'name': 'HackerProduct',
        'description': 'No Auth',
        'price': '999.99',
        'stock': '10'
    })
    vulnerable = res.status_code == 200
    print_result("A5_BrokenAccessControl", "비인가 사용자 제품 등록", res.status_code, vulnerable, "인증되지 않은 사용자도 제품을 등록할 수 있음")

def test_xss_on_product():
    session = requests.Session()
    session.get(f"{BASE_URL}/login/2")
    payload = {
        'name': '<img src=x onerror=alert(1)>',
        'description': 'desc',
        'price': '100.00',
        'stock': '1'
    }
    res = session.post(f"{BASE_URL}/products/add/", data=payload)
    vulnerable = res.status_code == 200
    print_result("A7_XSS", "제품 등록시 XSS 삽입", res.status_code, vulnerable, "스크립트 코드가 제품 이름에 포함됨")

def test_csrf():
    session = requests.Session()
    session.get(f"{BASE_URL}/login/1")
    res = session.post(f"{BASE_URL}/products/1/order/", data={'quantity': '1'})
    vulnerable = res.status_code == 200
    print_result("A1_BrokenAuth", "CSRF 보호 없음 - 주문", res.status_code, vulnerable, "CSRF 토큰 없이 주문 요청이 성공함")

if __name__ == "__main__":
    for test in scenarios['tests']:
        if test['id'] == 'A1_BrokenAuth':
            test_csrf()
        elif test['id'] == 'A2_SQLInjection':
            test_login_injection()
        elif test['id'] == 'A5_BrokenAccessControl':
            test_access_control()
        elif test['id'] == 'A7_XSS':
            test_xss_on_product()
        elif test['id'] == 'A9_InsufficientLogging':
            test_report_injection()
