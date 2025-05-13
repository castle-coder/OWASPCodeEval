# security_test.py

import os
import re
import sqlite3
import requests
import yaml
from requests.auth import HTTPBasicAuth

def load_config():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(script_dir, "scenario.yaml")
    with open(scenario_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f), script_dir

def run_scenarios():
    config, script_dir = load_config()
    base_url = config["login"]["base_url"]
    session = requests.Session()

    for sc in config["scenarios"]:
        print(f"[Test ID: {sc['test_id']}] {sc['description']}")

        # 1) 로그인 (세션 설정)
        if "login_user_id" in sc:
            login_url = f"{base_url}/login/{sc['login_user_id']}"
            session.get(login_url, allow_redirects=False)

        # 2) 첫 요청 실행
        req = sc["request"]
        url = f"{base_url}{req['endpoint']}"
        auth = None
        if "auth" in req:
            auth = HTTPBasicAuth(req["auth"]["username"], req["auth"]["password"])

        resp = session.request(
            method=req["method"],
            url=url,
            data=req.get("data", {}),
            auth=auth,
            allow_redirects=False
        )
        status = resp.status_code
        print(f"Status Code: {status}")

        # 3) 상태 코드 검사
        expected_status = sc["expected"]["status_code"]
        status_ok = (status == expected_status)

        # 4) DB 검사
        vuln_db = False
        reason_db = ""
        if sc.get("db_check"):
            db_conf = sc["db_check"]
            db_path = os.path.join(script_dir, db_conf["filename"])
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(db_conf["query"])
            row = cursor.fetchone()
            conn.close()

            if db_conf.get("malicious_pattern"):
                pattern = db_conf["malicious_pattern"]
                stored = row[-1] if row else ""
                if re.search(pattern, stored):
                    vuln_db = True
                    reason_db = f"악성 패턴이 DB에 저장됨 (id: {row[0]})"
                else:
                    reason_db = "패턴이 제거되었음"
            elif db_conf.get("valid_condition"):
                safe = eval(db_conf["valid_condition"], {}, {"row": row})
                if not safe:
                    vuln_db = True
                    reason_db = "DB 상태가 기대와 다름"
                else:
                    reason_db = "DB 상태 정상"
            print(f"DB Check: {'❌ 취약' if vuln_db else '✅ 안전'} ({reason_db})")

        # 5) 응답 본문 검사
        vuln_resp = False
        reason_resp = ""
        if sc.get("response_check"):
            rc = sc["response_check"]
            rurl = f"{base_url}{rc.get('endpoint', req['endpoint'])}"
            rmethod = rc.get("method", "GET")
            r = session.request(method=rmethod, url=rurl, allow_redirects=False)
            text = r.text
            found = re.search(rc["pattern"], text) is not None
            if found:
                vuln_resp = True
                reason_resp = "패턴이 노출됨"
            else:
                reason_resp = "패턴이 노출되지 않음"
            print(f"Response Check: {'❌ 취약' if vuln_resp else '✅ 안전'} ({reason_resp})")

        print("--------------------------------------------------\n")

if __name__ == "__main__":
    run_scenarios()
