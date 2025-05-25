# security_test.py
import os
import yaml
import requests

# Base URL of the application
BASE_URL = "http://127.0.0.1:8000"

# Absolute path to scenario.yaml
SCENARIO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenario.yaml')


def load_scenarios(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    return data.get('scenarios', [])


def perform_login(session, user_id):
    url = f"{BASE_URL}/login/{user_id}/"
    return session.get(url)


def run_tests():
    scenarios = load_scenarios(SCENARIO_PATH)
    for sc in scenarios:
        session = requests.Session()
        # Handle login if required
        prereq = sc.get('prerequisites', {})
        if 'login' in prereq:
            login_resp = perform_login(session, prereq['login'])
            if login_resp.status_code != 200:
                print(f"[Test ID: {sc['id']}] 로그인 실패 (user_id={prereq['login']})")
                continue

        # Prepare request
        method = sc['method'].lower()
        url = f"{BASE_URL}{sc['endpoint']}"
        payload = sc.get('payload', {})

        # Send request
        if method == 'get':
            resp = session.get(url)
        elif method == 'post':
            resp = session.post(url, data=payload)
        else:
            print(f"Unsupported method {sc['method']} in scenario {sc['id']}")
            continue

        # Evaluate result: match expected means 안전, mismatch means 취약
        code = resp.status_code
        expected = sc.get('expected_status')
        safe = code == expected
        symbol = '✅ 안전' if safe else '❌ 취약'

        # Reason
        if safe:
            reason = f"상태 코드 {code}가 예상 {expected}와 일치함"
        else:
            reason = f"상태 코드 {code}가 예상 {expected}와 다름"
            if sc['id'] == 'A9_InsufficientLogging':
                reason += " — 악성 입력 처리 로깅 미흡"

        # Print report
        print('-' * 50)
        print(f"[Test ID: {sc['id']}] {sc['description']}")
        print(f"Status Code: {code}")
        print(f"결과: {symbol}")
        print(f"이유: {reason}")
    print('-' * 50)


if __name__ == '__main__':
    run_tests()