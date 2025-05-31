#!/usr/bin/env python
"""
Django Member API 시나리오 러너
사용:  python security_test.py
"""
import re, yaml, requests, sqlite3, json, os
from pathlib import Path
from typing import Dict, Any, Optional

SEP  = "-" * 50
VARS: Dict[str, str] = {}          # 플레이스홀더 저장

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)

def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    return (code == int(spec)) if not m else int(m[1]) <= code <= int(m[2])

def db_fetchone(db: str, query: str):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(query)
        return cur.fetchone()

def substitute(obj):
    if isinstance(obj, str):
        for k, v in VARS.items():
            obj = obj.replace(f"{{{k}}}", str(v))
    elif isinstance(obj, dict):
        obj = {k: substitute(v) for k, v in obj.items()}
    return obj

def run_test(base: str, db: str, t: Dict[str, Any]):
    session = requests.Session()

    method = t["method"]
    url    = f"{base}{substitute(t['path'])}"
    body_json = substitute(t.get("json"))
    resp = session.request(method, url, json=body_json, allow_redirects=False, timeout=5)

    # PRE 스텝 – 변수 취득 후 종료
    if t["id"].startswith("_PRE_"):
        if "set_var_from_db" in t:
            for var, query in t["set_var_from_db"].items():
                VARS[var] = db_fetchone(db, query)[0]
        print(f"[PRE] {t['name']} → 완료 (Status {resp.status_code})")
        return

    ok = status_ok(resp.status_code, t["expected_status"])
    reason: Optional[str] = None

    # DB 취약 확인
    if ok and t.get("vuln_check"):
        if db_fetchone(db, t["vuln_check"]["query"]):
            ok, reason = False, "악성 데이터가 DB에 저장됨"

    # 헤더 체크
    if ok and t.get("header_required"):
        for h in t["header_required"]:
            if h.lower() not in (k.lower() for k in resp.headers):
                ok, reason = False, "보안 헤더 미설정"
                break

    # 기본 사유 매핑
    if not ok and reason is None:
        reason = {
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "입력 검증 실패",
            "A9": "XSS 입력 저장",
        }.get(t["id"].split("_")[0], "예상치 못한 응답")

    # 출력
    print(SEP)
    print(f"[Test ID: {t['id']}] {t['name']}")
    print(f"Status Code: {resp.status_code}  (expected {t['expected_status']})")
    print(f"결과: {'✅ 안전' if ok else '❌ 취약'}")
    if reason and not ok:
        print(f"이유: {reason}")

def main():
    cfg = yaml.safe_load(Path(SCENARIO_PATH).read_text(encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )
    for test in cfg["tests"]:
        run_test(base, db, test)
    print(SEP)

if __name__ == "__main__":
    main()
