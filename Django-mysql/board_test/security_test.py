import os
import requests
import sqlite3
import yaml

BASE_URL = "http://127.0.0.1:8000"
DB_PATH = "mock_db.sqlite3"
SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)

def check_table_exists(table):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists

def check_in_db(table, column, value):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (value,))
    found = cur.fetchone() is not None
    conn.close()
    return found

def run_test(test):
    session = requests.Session()
    # 로그인 여부
    if test.get("login", False):
        user = test.get("login_as", 1)
        session.get(f"{BASE_URL}/login/{user}/")

    # HTTP 요청
    url = BASE_URL + test["url"]
    method = test["method"].upper()
    data = test.get("data", {})
    resp = session.post(url, data=data) if method == "POST" else session.get(url, params=data)

    status_ok = (resp.status_code == test["expected_status"])

    # DB 검증
    db_ok = True
    reason = ""
    if "assert_table_exists" in test:
        tbl = test["assert_table_exists"]
        db_ok = check_table_exists(tbl)
        if not db_ok:
            reason = f"테이블 '{tbl}'가 존재하지 않음"
    if db_ok and "assert_not_in_db" in test:
        v = test["assert_not_in_db"]
        if check_in_db(v["table"], v["column"], v["value"]):
            db_ok = False
            reason = f"악성 내용이 DB에 저장됨 ({v['column']}: {v['value']})"
    if db_ok and "assert_in_db" in test:
        v = test["assert_in_db"]
        if not check_in_db(v["table"], v["column"], v["value"]):
            db_ok = False
            reason = f"정상 레코드가 DB에 없음 ({v['column']}: {v['value']})"

    # 결과 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {test['id']}] {test['name']}")
    print(f"Status Code: {resp.status_code}")
    result = "✅ 안전" if status_ok and db_ok else "❌ 취약"
    print(f"결과: {result}")
    if not status_ok:
        print(f"이유: 예상 상태코드 {test['expected_status']}와 다름")
    elif not db_ok:
        print(f"이유: {reason}")
    print("--------------------------------------------------\n")

def main():
    with open(SCENARIO_PATH, encoding="utf-8") as f:
        scenario = yaml.safe_load(f)
    for test in scenario["tests"]:
        run_test(test)

if __name__ == "__main__":
    main()
