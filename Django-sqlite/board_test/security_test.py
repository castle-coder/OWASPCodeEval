"""
security_test.py – Django Board API security tester (Python 3.9 compatible)
"""
import re
import yaml
import requests
import sqlite3
import os
from typing import Optional, Dict, Any

SEP = "-" * 50

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)


def status_ok(code: int, spec: str) -> bool:
    rng = re.match(r"(\d+)-(\d+)$", spec)
    if rng:
        lo, hi = map(int, rng.groups())
        return lo <= code <= hi
    return code == int(spec)


def db_has_row(db: str, query: str) -> bool:
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    try:
        cur.execute(query)
        return cur.fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def run_test(base: str, db: str, t: Dict[str, Any]):
    sess = requests.Session()

    # optional login
    if t.get("login_as") is not None:
        sess.get(f"{base}/login/{t['login_as']}/", allow_redirects=False)

    resp = sess.request(
        method=t["method"],
        url=f"{base}{t['path']}",
        data=t.get("data"),
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, t["expected_status"])
    reason: Optional[str] = None

    # DB vulnerability check
    if t.get("vuln_check") and db_has_row(db, t["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    # Header presence check
    if t.get("header_required"):
        for h in t["header_required"]:
            if h.lower() not in (k.lower() for k in resp.headers):
                ok = False
                reason = "보안 헤더 미설정"

    # Default reason mapping
    if not ok and reason is None:
        category = t["id"].split("_", 1)[0]
        reason_map = {
            "A1": "권한 우회 허용",
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
        }
        reason = reason_map.get(category, "예상치 못한 응답 코드")

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db   = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )

    for test in cfg["tests"]:
        safe, actual, why = run_test(base, db, test)
        print(SEP)
        print(f"[Test ID: {test['id']}] {test['name']}")
        print(f"Status Code: {actual}  (expected {test['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
