#!/usr/bin/env python
"""
Django Quiz API 시나리오 실행기
사용:  python security_test.py
"""
import re, yaml, requests, sqlite3, os
from pathlib import Path
from typing import Dict, Any, Optional

SEP  = "-" * 50
VARS: Dict[str, Any] = {}

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)

##############################################################################
# DB helpers
##############################################################################
def db_fetchone(db: str, query: str):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(query)
        return cur.fetchone()

##############################################################################
# 기타 유틸
##############################################################################
def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    return (code == int(spec)) if not m else int(m[1]) <= code <= int(m[2])

def substitute(val):
    if isinstance(val, str):
        for k, v in VARS.items():
            val = val.replace(f"{{{k}}}", str(v))
    elif isinstance(val, dict):
        val = {k: substitute(v) for k, v in val.items()}
    return val

def login(sess: requests.Session, base: str, user_id: int):
    sess.get(f"{base}/login/{user_id}/", allow_redirects=False, timeout=5)

##############################################################################
# 테스트 실행
##############################################################################
def run_test(base: str, db: str, t: Dict[str, Any]):
    # PRE 단계 – 변수 설정만 하고 종료
    if t["id"].startswith("_PRE_"):
        if "set_var_from_db" in t:
            for var, q in t["set_var_from_db"].items():
                VARS[var] = db_fetchone(db, q)[0]
        print(f"[PRE] {t['name']} – 완료")
        return

    sess = requests.Session()
    if t.get("login_as") is not None:
        login(sess, base, t["login_as"])

    method = t["method"]
    url    = f"{base}{substitute(t['path'])}"
    data   = substitute(t.get("data"))
    resp   = sess.request(method, url, data=data, allow_redirects=False, timeout=10)

    ok = status_ok(resp.status_code, t["expected_status"])
    reason: Optional[str] = None

    # DB 취약 여부
    if ok and t.get("vuln_check"):
        q = substitute(t["vuln_check"]["query"])
        if db_fetchone(db, q):
            ok, reason = False, "악성 데이터가 DB에 저장됨"

    # 헤더 검사
    if ok and t.get("header_required"):
        for h in t["header_required"]:
            if h.lower() not in (k.lower() for k in resp.headers):
                ok, reason = False, "보안 헤더 미설정"
                break

    # 기본 사유
    if not ok and reason is None:
        reason = {
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증/입력 검증 실패",
            "A9": "XSS 입력 저장",
        }.get(t["id"].split("_")[0], "예상치 못한 응답")

    # 결과 출력
    print(SEP)
    print(f"[Test ID: {t['id']}] {t['name']}")
    print(f"Status Code: {resp.status_code}  (expected {t['expected_status']})")
    print(f"결과: {'✅ 안전' if ok else '❌ 취약'}")
    if reason and not ok:
        print(f"이유: {reason}")

##############################################################################
# main
##############################################################################
def main():
    cfg = yaml.safe_load(Path(SCENARIO_PATH).read_text(encoding="utf-8"))
    base_url = cfg["base_url"].rstrip("/")
    db_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )
    for test in cfg["tests"]:
        run_test(base_url, db_path, test)
    print(SEP)

if __name__ == "__main__":
    main()
