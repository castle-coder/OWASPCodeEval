import yaml, requests, sqlite3, re, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    """코드가 spec 범위(예: '401-401' 또는 '200-299') 안에 있으면 True"""
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
        return lo <= code <= hi
    return code == int(spec)


def row_exists(db: str, query: str) -> bool:
    """쿼리 결과가 존재하면 True (취약)"""
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute(query)
        found = cur.fetchone() is not None
    except sqlite3.Error:
        found = False
    finally:
        conn.close()
    return found


def run_test(base: str, db: str, t: dict):
    sess = requests.Session()

    # 로그인 필요 시
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

    # DB 취약 여부
    if t.get("vuln_check") and row_exists(db, t["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    # 범주별 기본 메시지
    if not ok and reason is None:
        if t["id"].startswith("A1_"):
            reason = "권한 우회 허용"
        elif t["id"].startswith("A3_"):
            reason = "SQL 인젝션 허용"
        elif t["id"].startswith("A7_"):
            reason = "비존재 ID 로그인 허용"
        else:
            reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for test in cfg["tests"]:
        safe, actual, why = run_test(base, db, test)
        print(SEP)
        print(f"[Test ID: {test['id']}] {test['name']}")
        print(f"Status Code: {actual} (expected {test['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
