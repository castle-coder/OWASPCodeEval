# security_test.py
import os
import yaml
import requests
import sqlite3

BASE_URL = "http://127.0.0.1:8000"

def load_scenarios():
    here = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(here, "scenario.yaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)["scenarios"]

def run_test(s):
    session = requests.Session()
    # 로그인 필요 시
    if s.get("login_member_id"):
        session.get(f"{BASE_URL}/login/{s['login_member_id']}/")

    url = BASE_URL + s["endpoint"]
    method = s["method"].upper()
    if method == "GET":
        res = session.get(url)
    else:
        res = session.post(url, data=s.get("data", {}))

    status = res.status_code
    vulnerable = False
    reason = ""

    # 상태 코드 검증
    if status != s["expected_status"]:
        vulnerable = True
        reason = f"예상 상태 코드 {s['expected_status']}이(가) 아니므로 실패 (실제: {status})"
    # DB 검사 필요 시
    elif "check_db" in s:
        here = os.path.dirname(os.path.realpath(__file__))
        db_path = os.path.join(here, "mock_db.sqlite3")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(s["check_db"]["query"])
        row = cur.fetchone()
        cols = [d[0] for d in cur.description]
        conn.close()

        payload = s["check_db"]["expected_payload"]
        field_idx = cols.index(s["check_db"]["payload_field"])
        if row and payload in row[field_idx]:
            vulnerable = True
            if s["id"].startswith("A9_"):
                report_id, _, member_id = row
                reason = f"악성 신고 내용이 DB에 저장됨 (report_id: {report_id}, member_id: {member_id})"
            else:
                reason = f"DB에 악성 입력이 저장됨 ({s['check_db']['payload_field']} = {row[field_idx]})"
        else:
            reason = "DB에 악성 입력이 저장되지 않음"
    else:
        reason = "예상 결과와 일치"

    # 결과 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {s['id']}] {s['title']}")
    print(f"Status Code: {status}")
    print(f"결과: {'❌ 취약' if vulnerable else '✅ 안전'}")
    print(f"이유: {reason}")

def main():
    scenarios = load_scenarios()
    for s in scenarios:
        run_test(s)
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
