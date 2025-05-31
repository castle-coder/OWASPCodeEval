"""
security_test.py – Django Comment / Report API security tester
"""
import re
import yaml
import requests
import sqlite3
import os
from typing import Dict, Any, Optional

SEP = "-" * 50

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)


def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
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


def run_test(base: str, db: str, t: Dict[str, Any]) -> None:
    sess = requests.Session()

    # optional pre-steps (for seeding data etc.)
    for step in t.get("pre", []):
        sess.request(
            method=step["method"],
            url=f"{base}{step['path']}",
            data=step.get("data"),
            allow_redirects=False,
        )

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

    # DB-level vuln check
    if t.get("vuln_check") and db_has_row(db, t["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    # header check
    if t.get("header_required"):
        for h in t["header_required"]:
            if h.lower() not in (k.lower() for k in resp.headers):
                ok = False
                reason = "보안 헤더 미설정"

    # default reason mapping
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

    # output
    print(SEP)
    print(f"[Test ID: {t['id']}] {t['name']}")
    print(f"Status Code: {resp.status_code}  (expected {t['expected_status']})")
    print(f"결과: {'✅ 안전' if ok else '❌ 취약'}")
    if reason and not ok:
        print(f"이유: {reason}")


def main() -> None:
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )

    for test in cfg["tests"]:
        # _PRE_ prefix → seed only, no pass/fail 표시
        if test["id"].startswith("_PRE_"):
            run_test(base, db, test)
            continue
        run_test(base, db, test)
    print(SEP)


if __name__ == "__main__":
    main()
