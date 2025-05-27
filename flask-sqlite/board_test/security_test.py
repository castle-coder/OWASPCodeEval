"""
security_test.py – Flask Board API security checker (Python 3.9 compatible)
"""
import re
import io
import yaml
import sqlite3
import requests
from typing import Optional, Dict, Any

SEP = "-" * 50


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


def make_files(spec: Optional[Dict[str, Any]]):
    if not spec:
        return None
    return {
        "file": (
            spec["filename"],
            io.BytesIO(spec["content"].encode()),
            spec.get("mime_type", "text/plain"),
        )
    }


def run_test(base: str, db: str, t: dict):
    sess = requests.Session()

    # (옵션) 로그인
    if t.get("login_as"):
        sess.get(f"{base}/login/{t['login_as']}", allow_redirects=False)

    resp = sess.request(
        t["method"],
        f"{base}{t['path']}",
        data=t.get("data"),
        files=make_files(t.get("file_upload")),
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, t["expected_status"])
    reason = None

    if t.get("vuln_check") and db_has_row(db, t["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    if not ok and reason is None:
        cat = t["id"].split("_", 1)[0]
        reason_map = {
            "A1": "권한 우회 허용",
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
        }
        reason = reason_map.get(cat, "예상치 못한 응답 코드")

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open("scenario.yaml", encoding="utf-8"))
    base, db = cfg["base_url"].rstrip("/"), cfg["database"]

    for t in cfg["tests"]:
        safe, actual, why = run_test(base, db, t)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual}  (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
