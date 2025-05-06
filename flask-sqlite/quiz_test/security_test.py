import yaml
import requests
import sqlite3
import time

BASE_URL = "http://127.0.0.1:5000"
DB_PATH = "mock_db.sqlite3"

def run_scenarios():
    with open("scenario.yaml", 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    for s in data.get("scenarios", []):
        scenario_id = s["id"]
        description = s.get("description", "")
        method = s.get("method", "GET").upper()
        endpoint = s.get("endpoint", "")
        full_url = BASE_URL + endpoint if endpoint else ""
        payload = s.get("payload", {})
        expected_status = s.get("expected_status", 200)
        expected_vuln = s.get("expected_vulnerable", False)

        session = requests.Session()

        # 로그인 처리
        login_user = s.get("login_user")
        if login_user:
            session.get(f"{BASE_URL}/login/{login_user}")

        # 요청 실행
        try:
            if method == "POST":
                response = session.post(full_url, data=payload)
            elif method == "GET":
                response = session.get(full_url)
            else:
                response = None
            status_code = response.status_code if response else 0
        except Exception:
            status_code = 0

        vulnerable = False
        reason_output = ""

        # DB 확인
        check = s.get("check")
        if check:
            time.sleep(0.1)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute(f"SELECT COUNT(*) FROM {check['table']} WHERE {check['column']} = ?", (check['value'],))
            count = c.fetchone()[0]
            conn.close()
            if count > 0:
                vulnerable = True
                reason_output = f"DB에 악성 데이터가 삽입됨 ({check['column']}: {check['value']})"
        else:
            if expected_vuln:
                vulnerable = status_code != expected_status
                reason_output = f"예상 코드: {expected_status}, 실제 코드: {status_code}" if vulnerable else ""
            else:
                vulnerable = False if status_code == expected_status else True
                reason_output = f"예상 코드: {expected_status}, 실제 코드: {status_code}" if vulnerable else ""

        result_mark = "❌ 취약" if vulnerable else "✅ 안전"

        print("--------------------------------------------------")
        print(f"[Test ID: {scenario_id}] {description}")
        print(f"Status Code: {status_code}")
        print(f"결과: {result_mark}")
        if reason_output:
            print(f"이유: {reason_output}")
        print("--------------------------------------------------\n")

if __name__ == "__main__":
    run_scenarios()
