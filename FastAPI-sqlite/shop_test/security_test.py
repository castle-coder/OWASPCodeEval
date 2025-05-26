"""
security_test.py – Python 3.9.6 호환 버전
"""
import re
import yaml
import json
import sqlite3
import requests
import os
from typing import Optional

SEP = "-" * 50

dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(dir, 'mock_db.sqlite3')
SCENARIO_PATH = os.path.join(dir, 'scenario.yaml')


def status_ok(code: int, spec: str) -> bool:
    """`spec`이 '401-401' 또는 '200-299' 형식이면 범위, 단일 값이면 정확 매칭."""
    m = re.match(r"(\d+)-(\d+)$", spec)
    if m:
        lo, hi = map(int, m.groups())
        return lo <= code <= hi
    return code == int(spec)


def db_has_row(db: str, query: str) -> bool:
    """쿼리 결과가 존재하면 True."""
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


def extract_order_id(html_text: str) -> Optional[str]:
    """HTML 중 `/orders/<id>` 패턴에서 id 추출."""
    m = re.search(r"/orders/(\d+)", html_text)
    return m.group(1) if m else None


def run_single(base: str, db: str, test: dict):
    sess = requests.Session()
    ctx = {}

    # ── 사전 단계(pre) 실행 ────────────────────────────────────────
    for step in test.get("pre", []):
        resp = sess.request(
            step["method"], f"{base}{step['path']}", data=step.get("data"), allow_redirects=False
        )
        if test.get("dynamic_order"):
            oid = extract_order_id(resp.text)
            if oid:
                ctx["order_id"] = oid

    # ── (재)로그인 ────────────────────────────────────────────────
    if test.get("login_as") is not None:
        sess.get(f"{base}/login/{test['login_as']}", allow_redirects=False)

    # ── 경로 & 데이터 준비 ────────────────────────────────────────
    path = test.get("path_template", test.get("path", ""))
    path = path.replace("{{order_id}}", ctx.get("order_id", ""))
    data = test.get("data", {})

    resp = sess.request(
        method=test["method"],
        url=f"{base}{path}",
        data=data,
        allow_redirects=False,
    )

    ok = status_ok(resp.status_code, test["expected_status"])
    reason = None

    # ── DB 확인 (vuln_check) ─────────────────────────────────────
    if test.get("vuln_check") and db_has_row(db, test["vuln_check"]["query"]):
        ok = False
        reason = "악성 데이터가 DB에 저장됨"

    # ── 기본 에러 메시지 매핑 ────────────────────────────────────
    if not ok and reason is None:
        category = test["id"].split("_", 1)[0]
        reason_map = {
            "A1": "권한 우회 허용",
            "A2": "평문 비밀번호 저장",
            "A3": "SQL 인젝션 허용",
            "A5": "보안 헤더 미설정",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
            "A10": "비즈니스 로직 / SSRF 취약"
        }
        reason = reason_map.get(category, "예상치 못한 응답 코드")

    return ok, resp.status_code, reason


def main():
    cfg = yaml.safe_load(open(SCENARIO_PATH, encoding="utf-8"))
    base = cfg["base_url"].rstrip("/")
    db = DB_PATH  # 절대 경로 사용

    for t in cfg["tests"]:
        safe, actual, why = run_single(base, db, t)
        print(SEP)
        print(f"[Test ID: {t['id']}] {t['name']}")
        print(f"Status Code: {actual} (expected {t['expected_status']})")
        print(f"결과: {'✅ 안전' if safe else '❌ 취약'}")
        if why and not safe:
            print(f"이유: {why}")
    print(SEP)


if __name__ == "__main__":
    main()
