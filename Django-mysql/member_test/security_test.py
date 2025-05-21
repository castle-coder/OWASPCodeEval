import os
import requests
import yaml
import sqlite3

from urllib.parse import urljoin

BASE_URL = 'http://127.0.0.1:8000'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIO_PATH = os.path.join(SCRIPT_DIR, 'scenario.yaml')
DB_PATH = os.path.join(SCRIPT_DIR, 'mock_db.sqlite3')

def print_result(scenario_id, status_code, success, reason):
    icon = '✅' if success else '❌'
    print(f"{'-'*50}")
    print(f"[Test ID: {scenario_id}] {reason}")
    print(f"Status Code: {status_code}")
    print(f"결과: {icon} {'정상' if success else '취약'}")
    print(f"이유: {reason}")
    print(f"{'-'*50}")

def run_tests():
    with open(SCENARIO_PATH, 'r', encoding='utf-8') as f:
        scenarios = yaml.safe_load(f)['scenarios']

    for test in scenarios:
        method = test['method']
        url = urljoin(BASE_URL, test['endpoint'].lstrip('/'))
        expected_status = test.get('expected_status', 200)
        payload = test.get('payload')
        headers = {'Content-Type': 'application/json'}

        try:
            if method == 'GET':
                response = requests.get(url)
            elif method == 'POST':
                response = requests.post(url, json=payload, headers=headers)
            else:
                print_result(test['id'], 0, False, f"Unsupported HTTP method: {method}")
                continue

            status_code = response.status_code
            content = response.text

            # A5: Debug Mode 노출 확인
            if test.get('expect_debug') is not None:
                debug_exposed = 'Traceback' in content
                expected_debug = test['expect_debug']
                success = debug_exposed == expected_debug
                reason = '디버그 정보가 노출됨' if debug_exposed else '디버그 정보 없음'
                print_result(test['id'], status_code, success, reason)
                continue

            # A9: DB 저장 확인
            if test.get('verify_db'):
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM members WHERE email=?", (payload['email'],))
                row = cursor.fetchone()
                conn.close()

                if row:
                    success = False
                    reason = f"악성 신고 내용이 DB에 저장됨 (member_id: {row[0]}, name: {row[1]})"
                else:
                    success = True
                    reason = "악성 내용이 저장되지 않음"
                print_result(test['id'], status_code, success, reason)
                continue

            # 일반적인 상태코드 검증
            success = (status_code == expected_status)
            reason = f"Expected status {expected_status}, got {status_code}"
            print_result(test['id'], status_code, success, reason)

        except Exception as e:
            print_result(test['id'], 0, False, f"오류 발생: {str(e)}")

if __name__ == '__main__':
    run_tests()
