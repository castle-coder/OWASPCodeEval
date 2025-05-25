# security_test.py
import yaml
import requests
import sqlite3
import os

BASE_URL = "http://localhost:8000"
DB_PATH = "mock_db.sqlite3"

def run_sql(sql_commands):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_PATH)
    conn = sqlite3.connect(db_path)
    for cmd in sql_commands or []:
        conn.execute(cmd)
    conn.commit()
    conn.close()

def get_db_state():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    tables = ["users", "files", "reports"]
    state = {}
    for t in tables:
        rows = conn.execute(f"SELECT * FROM {t}").fetchall()
        state[t] = [tuple(row) for row in rows]
    conn.close()
    return state

def diff_states(before, after):
    diffs = {}
    for t in before:
        before_set = set(before[t])
        after_set = set(after[t])
        added = list(after_set - before_set)
        removed = list(before_set - after_set)
        if added or removed:
            diffs[t] = {"added": added, "removed": removed}
    return diffs

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(current_dir, "scenario.yaml")
    with open(scenario_path, "r", encoding="utf-8") as f:
        scenario = yaml.safe_load(f)
    session = requests.Session()
    for test in scenario["tests"]:
        # setup
        run_sql(test.get("setup_sql"))
        before = get_db_state()
        # login if needed
        session.cookies.clear()
        if test.get("login_as") is not None:
            session.get(f"{BASE_URL}/login/{test['login_as']}")
        # perform request
        method = test["request"]["method"].lower()
        url = BASE_URL + test["request"]["path"]
        resp = getattr(session, method)(url)
        after = get_db_state()
        diffs = diff_states(before, after)
        # print result
        print("--------------------------------------------------")
        print(f"[Test ID: {test['id']}] {test['description']}")
        print(f"Status Code: {resp.status_code}")
        if resp.status_code in test["safe_status_codes"]:
            print("결과: ✅ 안전")
            print("이유: 모든 조건 통과")
        else:
            print("결과: ❌ 취약")
            exp = test["safe_status_codes"]
            print(f"이유: 예상 코드 {exp}, 실제 코드 {resp.status_code}")
        if diffs:
            print("DB Changes:")
            for table, change in diffs.items():
                if change["added"]:
                    print(f"  Added to {table}: {change['added']}")
                if change["removed"]:
                    print(f"  Removed from {table}: {change['removed']}")
        else:
            print("DB Changes: 없음")
        print("--------------------------------------------------")

if __name__ == "__main__":
    main()

# Excluded OWASP Top 10:
# A2_CryptographicFailures: 암호 저장 기능이 없어 테스트 대상이 아님
# A6_VulnerableComponents: 외부 컴포넌트 사용이 없어 테스트 대상이 아님
# A8_SoftwareAndDataIntegrityFailures: 데이터 무결성 관련 기능 없음
# A9_SecurityLoggingMonitoring: 로깅 기능이 없어 테스트 대상이 아님
# A10_ServerSideRequestForgery: 외부 요청 기능이 없어 테스트 대상이 아님
