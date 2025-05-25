# security_test.py
import yaml
import requests
import sqlite3
import os

BASE_URL = "http://localhost:8000"
DB_PATH = "mock_db.sqlite3"
SEPARATOR = "--------------------------------------------------"

def get_db_state():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, DB_PATH)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM posts")
    posts_count = cur.fetchone()[0]
    conn.close()
    return {"users": users_count, "posts": posts_count}

def run_test(test):
    # Snapshot DB before
    before = get_db_state()

    req = test["request"]
    url = BASE_URL + req["endpoint"]
    method = req["method"].upper()
    try:
        if method == "GET":
            resp = requests.get(url, params=req.get("params", {}), headers=req.get("headers", {}))
        elif method == "POST":
            resp = requests.post(url, params=req.get("params", {}), json=req.get("json"))
        else:
            raise ValueError(f"Unsupported method {method}")
        status = resp.status_code
    except Exception as e:
        status = None

    # Snapshot DB after
    after = get_db_state()

    # Determine result
    expected = test["expected_status_codes"]
    safe = status in expected

    # Print result
    print(SEPARATOR)
    print(f"[Test ID: {test['id']}] {test['description']}")
    print(f"Status Code: {status}")
    print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
    if safe:
        print("이유: 모든 조건 통과")
    else:
        exp_str = ", ".join(str(c) for c in expected)
        print(f"이유: 예상 코드 {exp_str}, 실제 코드 {status}")
    # DB change info
    if before != after:
        changes = []
        for table in before:
            if before[table] != after[table]:
                changes.append(f"{table}: {before[table]}→{after[table]}")
        print("DB 변경: " + "; ".join(changes))
    else:
        print("DB 변경: 없음")
    print(SEPARATOR)

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(current_dir, "scenario.yaml")
    with open(scenario_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    for test in data.get("tests", []):
        run_test(test)

if __name__ == "__main__":
    main()


# 제외된 OWASP_TOP10:
# A2_CryptographicFailures: 비밀번호 저장/평문 저장 기능이 해당 코드에 구현되어 있지 않아 테스트 불필요
# A4_InsecureDesign: 관리자 전용 기능(/admin/*)이 해당 코드에 없음
# A6_VulnerableComponents: 외부 라이브러리 취약점 검사 대상인 bcrypt 등 암호화 컴포넌트가 없음
# A7_IdentificationAndAuthenticationFailures: 로그인 엔드포인트(/login)가 없고 인증 로직이 단순 세션 저장만으로 구현되지 않음
# A8_SoftwareAndDataIntegrityFailures: 데이터 무결성 검증 로직이 없고 외부 업데이트 API가 없어 테스트 대상 아님
# A9_SecurityLoggingMonitoring: 로깅/모니터링 기능이 전혀 구현되어 있지 않음
# A10_ServerSideRequestForgery: 외부 요청을 수행하는 로직이 전혀 없어 SSRF 테스트 불필요
