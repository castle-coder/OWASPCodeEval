"""
security_test.py – Works on Python 3.9.6
"""
import re
import io
import yaml
import sqlite3
import requests
import os
from typing import Optional, Dict, Any

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


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


def make_files(spec: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not spec:
        return None
    # StreamingUploadFile 형식
    return {
        "file": (
            spec["filename"],
            io.BytesIO(spec["content"].encode()),
            spec["mime_type"],
        )
    }


def run_one(base: str, db: str, t: dict):
    s = requests.Session()

    # 로그인
    if t.get("login_as"):
        s.get(f"{base}/login/{t['login_as']}", allow_redirects=False)

    files = make_files(t.get("file_upload"))
    data = t.get("data")

    resp = s.request(
        t["method"], f"{base}{t['path']}", data=data, files=files, allow_redirects=False
    )

    ok = status_ok(resp.status_code, t["expected_status"])
    reason = None

    if t.get("vuln_check") and db_has_row(db, t["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    if not ok and reason is None:
        prefix = t["id"].split("_", 1)[0]
        reason_map = {
            "A1": "권한 우회 허용",
            "A3": "SQL/Path Traversal 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
        }
        reason = reason_map.get(prefix, "예상치 못한 응답 코드")

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for test in cfg["tests"]:
        safe, actual, why = run_one(base, db, test)
        print(SEP)
        print(f"[Test ID: {test['id']}] {test['name']}")
        print(f"Status Code: {actual} (expected {test['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
