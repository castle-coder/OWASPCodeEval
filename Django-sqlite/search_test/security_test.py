import os
import yaml
import sqlite3
import requests

BASE_URL = "http://127.0.0.1:8000"
SCENARIO_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'scenario.yaml'))
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'mock_db.sqlite3'))

def load_scenarios(path):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def check_db(table, column, contains):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT {column} FROM {table} ORDER BY rowid DESC LIMIT 1")
        row = cursor.fetchone()
        return row and contains in row[0]
    finally:
        conn.close()

def run_test(test):
    session = requests.Session()
    # Login if needed
    login_info = test.get('login')
    if login_info:
        session.get(f"{BASE_URL}/login/{login_info['user_id']}/")

    url = BASE_URL + test['endpoint']
    method = test['method'].upper()
    data = test.get('data', {})

    if method == 'GET':
        resp = session.get(url, allow_redirects=False)
    else:
        resp = session.post(url, data=data, allow_redirects=False)

    status = resp.status_code
    result = '✅ 안전' if status == test['expect_status'] else '❌ 취약'
    reason = ''

    # DB check
    expect_db = test.get('expect_db')
    if expect_db:
        saved = check_db(expect_db['table'], expect_db['column'], expect_db['contains'])
        if saved:
            result = '❌ 취약'
            reason = f"악성 입력이 DB에 저장됨 ({expect_db['table']}.{expect_db['column']})"

    # Print output
    print(f"[Test ID: {test['id']}] {test['name']}")
    print(f"Status Code: {status}")
    print(f"결과: {result}")
    if reason:
        print(f"이유: {reason}")
    print("-" * 50)

def main():
    tests = load_scenarios(SCENARIO_PATH)
    for test in tests:
        run_test(test)

if __name__ == '__main__':
    main()
