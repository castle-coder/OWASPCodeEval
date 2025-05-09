# security_test.py

import yaml
import requests
import sqlite3
import os


base_dir = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(base_dir,'mock_db.sqlite3')

def load_scenarios(path='scenario.yaml'):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, path), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def check_db(table, column, expected_value):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = f"SELECT * FROM {table} WHERE {column} = ?"
    result = conn.execute(query, (expected_value,)).fetchone()
    conn.close()
    return result is not None

def matches_expected_status(expected, actual):
    if isinstance(expected, str) and expected.endswith("xx"):
        prefix = int(expected[0])
        return prefix * 100 <= actual < (prefix + 1) * 100
    try:
        return int(expected) == actual
    except:
        return False

def run_test(test, base_url):
    test_id = test.get('test_id', 'UNKNOWN')
    desc = test.get('description', test.get('name', 'Unnamed Test'))
    method = test['method'].lower()
    endpoint = test['endpoint']
    url = base_url + endpoint
    headers = test.get('headers', {})
    payload = test.get('payload')
    expected_status = test.get('expected_status')
    reason = test.get('reason', '')

    func = getattr(requests, method)
    if payload:
        resp = func(url, json=payload, headers=headers)
    else:
        resp = func(url, headers=headers)

    
    passed = matches_expected_status(expected_status, resp.status_code)
    db_info = ""

    # DB 검증 조건이 있다면 수행
    if "db_check" in test:
        table = test["db_check"]["table"]
        column = test["db_check"]["column"]
        expected = test["db_check"]["expected_value"]
        should_exist = test["db_check"]["result_should_exist"]

        exists = check_db(table, column, expected)
        if exists != should_exist:
            passed = False
            db_info = f"(DB record {'found' if exists else 'not found'}: {column}={expected})"
            if should_exist:
                reason = f"{column}={expected} 값이 DB에 존재하지 않음 {db_info}"
            else:
                reason = f"{column}={expected} 값이 DB에 존재함 {db_info}"
        else:
            reason += f" (DB check passed)"

    elif not passed:
        reason = f"Expected {expected_status}, got {resp.status_code}"

    # 결과 출력
    print("-" * 50)
    print(f"[Test ID: {test_id}] {desc}")
    print(f"Status Code: {resp.status_code}")
    print(f"결과: {'✅ 안전' if passed else '❌ 취약'}")
    print(f"이유: {reason}")
    print("-" * 50 + "\n")

    return passed

def main():
    print("lask-sqlite : EmailAuth_test 보안 테스트 시작")
    cfg = load_scenarios()
    base_url = cfg.get('base_url', 'http://127.0.0.1:5000').rstrip('/')
    tests = cfg.get('tests', [])
    total = len(tests)
    passed = 0

    for test in tests:
        if run_test(test, base_url):
            passed += 1

    print(f"▶ 테스트 완료: {passed}/{total} PASSED")

if __name__ == "__main__":
    main()
