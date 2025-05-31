#!/usr/bin/env python
"""
Django Email-Verification API 보안 시나리오 실행기
사용법:  python security_test.py
필수:   pip install requests pyyaml
"""

import re
import yaml
import requests
import sqlite3
import os
from pathlib import Path
from typing import Dict, Any, Optional

SEP = "-" * 50

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)


def status_ok(code: int, spec: str) -> bool:
    """예상 범위(200-299) or 단일 값(404) 비교"""
    m = re.match(r"(\d+)-(\d+)$", spec)
    return (int(spec) == code) if not m else int(m[1]) <= code <= int(m[2])


def db_has_row(db: str, query: str) -> bool:
    """쿼리 결과 존재 여부 (SQLi·XSS 확인용)"""
    try:
        with sqlite3.connect(db) as conn:
            cur = conn.cursor()
            cur.execute(query)
            return cur.fetchone() is not None
    except sqlite3.Error:
        return False


def login_as(sess: requests.Session, base_url: str, db: str, user_id: int):
    """user_id에 맞는 이메일·코드 조회 후 /verify 로 세션 취득"""
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT email, verification_code FROM users WHERE user_id=?", (user_id,)
        )
        row = cur.fetchone()
    if row:
        email, code = row
        sess.post(
            f"{base_url}/verify/",
            data={"email": email, "code": code},
            allow_redirects=False,
            timeout=5,
        )


def run_test(base: str, db: str, t: Dict[str, Any]):
    sess = requests.Session()

    # (선택) pre 스텝 실행
    for step in t.get("pre", []):
        sess.request(
            step["method"],
            f"{base}{step['path']}",
            data=step.get("data"),
            allow_redirects=False,
            timeout=5,
        )

    # (선택) 로그인
    if t.get("login_as") is not None:
        login_as(sess, base, db, t["login_as"])

    # 메인 요청
    resp = sess.request(
        t["method"],
        f"{base}{t['path']}",
        data=t.get("data"),
        allow_redirects=False,
        timeout=5,
    )

    # ───── 결과 판정 ─────────────────────────────────────────
    if t["id"].startswith("_PRE_"):
        # 시드용 스텝은 패스/페일 판정 제외
        print(SEP)
        print(f"[PRE] {t['name']} → 완료 (Status {resp.status_code})")
        return

    ok = status_ok(resp.status_code, t["expected_status"])
    reason: Optional[str] = None

    # DB 검증
    if ok and t.get("vuln_check") and db_has_row(db, t["vuln_check"]["query"]):
        ok, reason = False, "악성 데이터가 DB에 저장됨"

    # 헤더 검증
    if ok and t.get("header_required"):
        for hdr in t["header_required"]:
            if hdr.lower() not in (k.lower() for k in resp.headers):
                ok, reason = False, "보안 헤더 미설정"
                break

    # 기본 사유 매핑
    if not ok and reason is None:
        category = t["id"].split("_", 1)[0]
        reason = {
            "A1": "권한 우회 허용",
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
        }.get(category, "예상치 못한 응답 코드")

    # ───── 출력 ────────────────────────────────────────────
    print(SEP)
    print(f"[Test ID: {t['id']}] {t['name']}")
    print(f"Status Code: {resp.status_code}  (expected {t['expected_status']})")
    print(f"결과: {'✅ 안전' if ok else '❌ 취약'}")
    if reason and not ok:
        print(f"이유: {reason}")


def main():
    cfg_path = Path(SCENARIO_PATH)
    if not cfg_path.exists():
        print("❗ scenario.yaml 파일을 찾을 수 없습니다.")
        return

    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    base_url = cfg["base_url"].rstrip("/")
    db_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )

    for test in cfg["tests"]:
        run_test(base_url, db_file, test)

    print(SEP)


if __name__ == "__main__":
    main()
