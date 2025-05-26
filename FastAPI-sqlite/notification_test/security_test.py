import yaml, requests, sqlite3, re
import os

SEP = "-" * 50


def status_in_range(status: int, rng: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", rng)
    if m:
        low, high = map(int, m.groups())
        return low <= status <= high
    return status == int(rng)


def db_row_exists(db_path: str, query: str) -> bool:
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(query)
    row = cur.fetchone()
    conn.close()
    return row is not None


def run_test(sess: requests.Session, base: str, test: dict, db: str):
    # optional login
    if test.get("login_as") is not None:
        sess.get(f"{base}/login/{test['login_as']}", allow_redirects=False)

    resp = sess.request(
        test["method"], f"{base}{test['path']}",
        data=test.get("data"), allow_redirects=False
    )

    ok = status_in_range(resp.status_code, test["expected_status"])
    reason = None

    # extra vulnerability checks
    if test.get("vuln_check"):
        exists = db_row_exists(db, test["vuln_check"]["query"])
        # 기본 규칙: row 존재 → 위험, row 없음 → 안전
        if exists:
            ok = False
            reason = "악성 데이터가 DB에 저장됨"
        elif test["id"].startswith("A7_") and not exists:
            # A7: 존재하지 않는 사용자 ID 로그인 허용
            ok = False
            reason = "비존재 ID로 로그인 허용"

    return ok, reason, resp.status_code


def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    cfg = yaml.safe_load(open(os.path.join(current_dir,"scenario.yaml"), encoding="utf-8"))
    base, db = cfg["base_url"].rstrip("/"), cfg["database"]

    for t in cfg["tests"]:
        s = requests.Session()
        success, why, actual = run_test(s, base, t, db)

        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if success else '❌ 취약'}")
        if why:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
