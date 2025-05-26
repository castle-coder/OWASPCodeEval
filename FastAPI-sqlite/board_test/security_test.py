import yaml, requests, sqlite3, re, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        low, high = map(int, m.groups())
        return low <= code <= high
    return code == int(spec)


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


def run(test: dict, base: str, db: str):
    s = requests.Session()

    # 세션 로그인 필요 시
    if test.get("login_as") is not None:
        s.get(f"{base}/login/{test['login_as']}", allow_redirects=False)

    resp = s.request(
        method=test["method"],
        url=f"{base}{test['path']}",
        data=test.get("data"),
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, test["expected_status"])
    reason = None

    # DB 기반 추가 검증
    if test.get("vuln_check"):
        if db_row_exists(db, test["vuln_check"]["query"]):
            ok = False
            reason = "악성 데이터가 DB에 저장됨"

    # 분류별 일반 메시지
    if not ok and reason is None:
        if test["id"].startswith("A7_"):
            reason = "인증 실패 취약"
        elif test["id"].startswith("A3_"):
            reason = "SQL 인젝션 허용"
        elif test["id"].startswith("A1_"):
            reason = "권한 우회 허용"
        else:
            reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for t in cfg["tests"]:
        safe, actual_code, why = run(t, base, db)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual_code} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
