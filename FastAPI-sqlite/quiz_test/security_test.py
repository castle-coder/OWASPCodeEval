import yaml, requests, sqlite3, re, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    """Status code가 spec(예: '401-401' 또는 '200-299') 범위 내인지 확인"""
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        low, high = map(int, m.groups())
        return low <= code <= high
    return code == int(spec)


def row_exists(db: str, query: str) -> bool:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute(query)
        found = cur.fetchone() is not None
    except Exception:
        found = False
    conn.close()
    return found


def run_test(base: str, db: str, t: dict):
    sess = requests.Session()

    # Optional login
    if t.get("login_as") is not None:
        sess.get(f"{base}/login/{t['login_as']}", allow_redirects=False)

    resp = sess.request(
        method=t["method"],
        url=f"{base}{t['path']}",
        data=t.get("data"),
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, t["expected_status"])
    reason = None

    # 추가 취약 확인
    if t.get("vuln_check"):
        if row_exists(db, t["vuln_check"]["query"]):
            ok = False
            reason = "악성 데이터가 DB에 저장됨"

    # A7 로그인 취약: 비존재 ID 허용
    if t["id"].startswith("A7_") and not ok and reason is None:
        reason = "비존재 ID로 로그인 허용"

    # A3 SQL 인젝션 취약
    if t["id"].startswith("A3_") and not ok and reason is None:
        reason = "SQL 인젝션 시도 허용"

    # 일반 코드 불일치
    if not ok and reason is None:
        reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for test in cfg["tests"]:
        success, actual, why = run_test(base, db, test)
        print(SEP)
        print(f"[Test ID: {test['id']}] {test['name']}")
        print(f"Status Code: {actual} (expected {test['expected_status']})")
        print(f"결과: {'✅ 안전' if success else '❌ 취약'}")
        if why and not success:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
