import yaml
import requests
import sqlite3

def load_config(path="scenario.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def run_scenario(base_url, db_path, sc):
    session = requests.Session()

    # (1) 로그인 필요 시
    if sc.get("login_path"):
        session.get(base_url + sc["login_path"], allow_redirects=False)

    # (2) 쿠키 변조 시나리오
    if sc.get("tamper_cookie"):
        for k, v in sc["tamper_cookie"].items():
            session.cookies.set(k, v)

    # (3) 반복 테스트(loop) 옵션
    if sc.get("loop"):
        last_status = None
        for _ in range(sc["loop"]):
            resp = session.get(base_url + sc["path"], allow_redirects=False)
            last_status = resp.status_code
        status = last_status
    else:
        # A6: SQLITE_VERSION 검사
        if sc["method"] == "SQLITE_VERSION":
            status = sqlite3.sqlite_version
        else:
            method = sc["method"].lower()
            url = base_url + sc["path"]
            headers = sc.get("headers", {})
            data = sc.get("data", {})
            resp = getattr(session, method)(
                url,
                headers=headers,
                data=data,
                allow_redirects=False
            )
            status = resp.status_code

    vulnerable = False
    reason = ""

    # (4) 상태 코드 검증
    exp = sc.get("expected_status")
    if exp is not None and status != exp:
        vulnerable = True
        reason = f"예상 코드 {exp}, 실제 코드 {status}"

    # (5) 버전 검증 (A6)
    if sc["id"] == "A6_Outdated_SQLite":
        min_ver = sc.get("expected_version_min")
        if tuple(map(int, status.split("."))) < tuple(map(int, min_ver.split("."))):
            vulnerable = True
            reason = f"SQLite 버전이 너무 낮음 ({status})"

    # (6) DB 검증
    if sc.get("check_db"):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sc["db_query"])
        row = cursor.fetchone() or []
        conn.close()

        # payload 비교
        payload = (
            sc.get("data", {}).get("content")
            or sc.get("data", {}).get("description")
            or sc.get("data", {}).get("title")
        )

        if row and payload and payload in row[-1]:
            vulnerable = True
            if sc["id"] == "A9_InsufficientLogging":
                reason = f"악성 신고 내용이 DB에 저장됨 (report_id: {row[0]}, user_id: {row[1]})"
            else:
                reason = f"악성 페이로드가 DB에 남아있음: {row[-1]}"
        else:
            if not reason:
                reason = "저장된 데이터에 이상 없음"

    # (7) 결과 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {sc['id']}] {sc['name']}")
    print(f"Status Code: {status}")
    print(f"결과: {'❌ 취약' if vulnerable else '✅ 안전'}")
    print(f"이유: {reason}")
    print("--------------------------------------------------\n")

def main():
    cfg = load_config()
    for scenario in cfg["scenarios"]:
        run_scenario(cfg["base_url"], cfg.get("db_path"), scenario)

if __name__ == "__main__":
    main()