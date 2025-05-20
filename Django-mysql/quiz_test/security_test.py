import os
import requests
import yaml

BASE_URL = "http://127.0.0.1:8000"

def print_result(test_id, description, status_code, expected_status, vulnerable=False, reason=None):
    print("--------------------------------------------------")
    print(f"[Test ID: {test_id}] {description}")
    print(f"Status Code: {status_code}")
    print(f"결과: {'❌ 취약' if vulnerable else '✅ 안전'}")
    if reason:
        print(f"이유: {reason}")
    print("--------------------------------------------------\n")

def main():
    # 1) 현재 스크립트 파일 위치를 기준으로 scenario.yaml 절대경로 생성
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(script_dir, "scenario.yaml")

    # 2) 절대경로로 파일 열기
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)

    session = requests.Session()

    for test in scenario['tests']:
        test_id = test['id']
        desc = test.get('description', '')
        method = test.get('method', 'GET').upper()
        path = test.get('path', '/')
        expected_status = test.get('expected_status', 200)
        data = test.get('data', {})
        login_as = test.get('login_as', None)
        expected_vuln = test.get('expected_vulnerability', None)

        # 로그인 필요 시 처리
        if login_as:
            r_login = session.get(f"{BASE_URL}/login/{login_as}/")
            if r_login.status_code != 200:
                print_result(test_id, desc, r_login.status_code, 200, True, "로그인 실패")
                continue

        # 요청 실행
        if method == "GET":
            r = session.get(f"{BASE_URL}{path}")
        elif method == "POST":
            r = session.post(f"{BASE_URL}{path}", data=data)
        else:
            print(f"Unsupported method {method} for test {test_id}")
            continue

        # 취약 여부 판단
        vulnerable = False
        reason = None

        if r.status_code != expected_status:
            vulnerable = True
            reason = f"예상 상태 코드 {expected_status}와 다름 (실제: {r.status_code})"
        elif expected_vuln:
            if expected_vuln == "악성 입력이 DB에 저장됨":
                vulnerable = True
                reason = "악성 입력이 DB에 저장되어 있음 (심볼릭 판단)"

        print_result(test_id, desc, r.status_code, expected_status, vulnerable, reason)


if __name__ == "__main__":
    main()
