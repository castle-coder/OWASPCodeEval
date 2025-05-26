import yaml, requests, sqlite3, re, json, os

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
        return lo <= code <= hi
    return code == int(spec)


def db_row_exists(db: str, query: str) -> bool:
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


def run_single(test: dict, base: str, db: str):
    sess = requests.Session()
    context = {}

    # optional login
    if test.get("login_as") is not None:
        sess.get(f"{base}/login/{test['login_as']}", allow_redirects=False)

    # optional pre-steps (e.g., dynamic user creation)
    if test.get("pre"):
        for step in test["pre"]:
            resp = sess.request(step["method"], f"{base}{step['path']}", data=step.get("data"), allow_redirects=False)
            # naive: extract last integer from body for user_id
            if test.get("dynamic_user_id"):
                m = re.search(r"code sent to .*?<\/a>", resp.text) or re.search(r"ID[^\d]*(\d+)", resp.text)
                if m:
                    context["user_id"] = re.search(r"\d+", resp.text).group()

    # prepare data (with template substitution)
    data = test.get("data", {})
    if test.get("data_template"):
        data = json.loads(json.dumps(test["data_template"]).replace("{{user_id}}", context.get("user_id", "")))

    resp = sess.request(test["method"], f"{base}{test['path']}", data=data, allow_redirects=False)

    ok = status_ok(resp.status_code, test["expected_status"])
    reason = None

    # DB check
    if test.get("vuln_check") and db_row_exists(db, test["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    if not ok and reason is None:
        if test["id"].startswith("A1_"):
            reason = "권한 우회 허용"
        elif test["id"].startswith("A3_"):
            reason = "SQL 인젝션 허용"
        elif test["id"].startswith("A7_"):
            reason = "인증 우회 허용"
        else:
            reason = "예상치 못한 응답 코드"

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for t in cfg["tests"]:
        safe, actual_code, why = run_single(t, base, db)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual_code} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
