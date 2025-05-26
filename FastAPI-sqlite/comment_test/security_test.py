import yaml, requests, sqlite3, re, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    """
    spec 이 '401-401' 또는 '200-299' 형태이면 범위 비교,
    단일 값이면 정확히 일치 비교.
    """
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
        return lo <= code <= hi
    return code == int(spec)


def row_exists(db_path: str, query: str) -> bool:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(query)
        exists = cur.fetchone() is not None
    except sqlite3.Error:
        exists = False
    finally:
        conn.close()
    return exists


def run(test: dict, base: str, db: str):
    sess = requests.Session()

    # optional login
    if test.get("login_as") is not None:
        sess.get(f"{base}/login/{test['login_as']}", allow_redirects=False)

    resp = sess.request(
        method=test["method"],
        url=f"{base}{test['path']}",
        data=test.get("data"),
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, test["expected_status"])
    reason = None

    # DB-based vulnerability checks
    if test.get("vuln_check") and row_exists(db, test["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    if not ok and reason is None:
        if test["id"].startswith("A1_"):
            reason = "권한 우회 허용"
        elif test["id"].startswith("A3_"):
            reason = "SQL 인젝션 허용"
        elif test["id"].startswith("A7_"):
            reason = "비존재 ID 로그인 허용"
        else:
            reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for t in cfg["tests"]:
        safe, actual, why = run(t, base, db)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
