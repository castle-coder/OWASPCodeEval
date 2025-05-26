import yaml, requests, sqlite3, re, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(actual: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
        return lo <= actual <= hi
    return actual == int(spec)


def db_row_exists(db: str, query: str) -> bool:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute(query)
        row = cur.fetchone()
    except sqlite3.Error:
        row = None
    finally:
        conn.close()
    return row is not None


def run_test(base: str, db: str, t: dict):
    sess = requests.Session()

    # optional login
    if t.get("login_as") is not None:
        sess.get(f"{base}/login/{t['login_as']}", allow_redirects=False)

    resp = sess.request(
        method=t["method"],
        url=f"{base}{t['path']}",
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, t["expected_status"])
    reason = None

    if t.get("vuln_check") and db_row_exists(db, t["vuln_check"]["query"]):
        # for destructive SQLi test we flip logic:
        if t["id"].startswith("A3_SQLi_SearchParam"):
            if not db_row_exists(db, "SELECT * FROM users LIMIT 1"):
                ok = False
                reason = "users 테이블이 손상되었거나 삭제됨"
        else:
            ok = False
            reason = "악성 데이터가 DB에 저장됨"

    if not ok and reason is None:
        if t["id"].startswith("A1_"):
            reason = "권한 우회 허용"
        elif t["id"].startswith("A3_"):
            reason = "SQL/FTS 인젝션 허용"
        elif t["id"].startswith("A7_"):
            reason = "인증 우회 허용"
        else:
            reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for t in cfg["tests"]:
        safe, actual, why = run_test(base, db, t)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
