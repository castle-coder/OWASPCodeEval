#!/usr/bin/env python
"""
Django File-Upload API 보안 시나리오 실행기
사용:  python security_test.py
필수: pip install requests pyyaml
"""
import re, yaml, requests, sqlite3, io, os
from pathlib import Path
from typing import Dict, Any, Optional

SEP = "-" * 50
VARS: Dict[str, Any] = {}     # { PLACEHOLDER: value }

SCENARIO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "scenario.yaml")
)

##############################################################################
# 유틸
##############################################################################
def status_ok(code: int, spec: str) -> bool:
    m = re.match(r"(\d+)-(\d+)$", spec)
    return (int(spec) == code) if not m else int(m[1]) <= code <= int(m[2])


def db_fetchone(db: str, query: str):
    with sqlite3.connect(db) as conn:
        cur = conn.cursor()
        cur.execute(query)
        return cur.fetchone()


def substitute(s: str) -> str:
    for k, v in VARS.items():
        s = s.replace(f"{{{k}}}", str(v))
    return s


def login(sess: requests.Session, base: str, user_id: int):
    sess.get(f"{base}/login/{user_id}/", allow_redirects=False, timeout=5)


def build_files(field: Dict[str, str]):
    """{"name": "...", "content": "..."} → files 매핑"""
    return {"file": (field["name"], io.BytesIO(field["content"].encode()))}


##############################################################################
# 테스트 러너
##############################################################################
def run_test(cfg_base: str, db: str, t: Dict[str, Any]):
    sess = requests.Session()

    # 로그인 처리
    if t.get("login_as") is not None:
        login(sess, cfg_base, t["login_as"])

    method = t["method"]
    path   = substitute(t["path"])
    url    = f"{cfg_base}{path}"
    data   = t.get("data")
    if data:  # 플레이스홀더 치환
        data = {k: substitute(str(v)) for k, v in data.items()}
    files_param = None
    if t.get("file"):
        files_param = build_files(t["file"])

    resp = sess.request(
        method, url, data=data, files=files_param,
        allow_redirects=False, timeout=10
    )

    # PRE 스텝 ?  (seed 용)
    if t["id"].startswith("_PRE_"):
        if "set_var_from_db" in t:                # DB에서 변수 추출
            for var, query in t["set_var_from_db"].items():
                VARS[var] = db_fetchone(db, query)[0]
        print(f"[PRE] {t['name']} → 완료 (Status {resp.status_code})")
        return

    # 기본 판정
    ok = status_ok(resp.status_code, t["expected_status"])
    reason: Optional[str] = None

    # DB 취약 여부 확인
    if ok and t.get("vuln_check"):
        if db_fetchone(db, t["vuln_check"]["query"]):
            ok, reason = False, "악성 데이터가 DB에 저장됨"

    # 헤더 필수 여부
    if ok and t.get("header_required"):
        for h in t["header_required"]:
            if h.lower() not in (k.lower() for k in resp.headers):
                ok, reason = False, "보안 헤더 미설정"
                break

    # 매핑된 기본 사유
    if not ok and reason is None:
        reason = {
            "A1": "권한 우회 허용",
            "A3": "SQL 인젝션 허용",
            "A4": "차단 파일 다운로드 허용",
            "A5": "보안 헤더 미설정",
            "A6": "비표준 HTTP 메서드 허용",
            "A7": "인증 우회 허용",
            "A9": "XSS 입력 저장",
        }.get(t["id"].split("_")[0], "예상치 못한 응답")

    # 출력
    print(SEP)
    print(f"[Test ID: {t['id']}] {t['name']}")
    print(f"Status Code: {resp.status_code}  (expected {t['expected_status']})")
    print(f"결과: {'✅ 안전' if ok else '❌ 취약'}")
    if reason and not ok:
        print(f"이유: {reason}")


##############################################################################
# 메인
##############################################################################
def main():
    cfg = yaml.safe_load(Path(SCENARIO_PATH).read_text(encoding="utf-8"))
    base_url = cfg["base_url"].rstrip("/")
    db_file = os.path.abspath(
        os.path.join(os.path.dirname(__file__), cfg["database"])
    )

    for test in cfg["tests"]:
        run_test(base_url, db_file, test)

    print(SEP)


if __name__ == "__main__":
    main()
