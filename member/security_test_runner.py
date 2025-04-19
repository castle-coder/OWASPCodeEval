import yaml
import requests

BASE_URL = "http://127.0.0.1:5000"

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def login(session, username, password):
    return session.post(f"{BASE_URL}/login", data={
        "username": username,
        "password": password
    }, allow_redirects=False)

def run_test(test, session):
    print(f"\n[🔍 {test['id']}] {test['name']}")

    # 수동 점검 항목
    if test.get("manual_check", False):
        print("  [🟡 수동 확인] " + test.get("notes", ""))
        return

    method = test.get("method", "GET").upper()
    endpoint = test.get("endpoint")
    if not endpoint:
        print("  [⚠️ SKIPPED] endpoint 누락")
        return

    url = f"{BASE_URL}{endpoint}"
    data = test.get("data", {})
    headers = test.get("headers", {})
    cookies = test.get("cookies", {})

    # 사전 작업 (예: 로그인)
    for step in test.get("steps", []):
        if "login" in step:
            creds = step["login"]
            login(session, creds["username"], creds["password"])

    try:
        if method == "GET":
            res = session.get(url, headers=headers, cookies=cookies, allow_redirects=False)
        elif method == "POST":
            res = session.post(url, headers=headers, cookies=cookies, data=data, allow_redirects=False)
        else:
            print(f"  [⚠️ UNSUPPORTED METHOD] {method}")
            return
    except Exception as e:
        print(f"  [💥 ERROR] 요청 실패: {e}")
        return

    # 기대된 응답과 비교
    all_conditions_met = True

    if "expected_status" in test:
        if res.status_code != test["expected_status"]:
            print(f"    ✖ 기대 상태코드: {test['expected_status']}, 실제: {res.status_code}")
            all_conditions_met = False

    if "expected_redirect" in test:
        location = res.headers.get("Location", "")
        if test["expected_redirect"] not in location:
            print(f"    ✖ 기대 리디렉션 위치 없음: {location}")
            all_conditions_met = False

    if "expected_body_contains" in test:
        if test["expected_body_contains"] not in res.text:
            print(f"    ✖ 기대 문자열 없음: {test['expected_body_contains']}")
            all_conditions_met = False

    # 보안 기대값에 따른 결과 판단
    expect_vuln = test.get("expect_vulnerability", True)

    if all_conditions_met:
        if expect_vuln:
            print("  [🔴 취약] 테스트가 성공적으로 통과했습니다 → 보안상 취약함 존재")
        else:
            print("  [🟢 안전] 테스트가 정상적으로 동작했습니다 → 보안상 안전")
    else:
        if expect_vuln:
            print("  [🟢 안전] 테스트 조건이 충족되지 않았습니다 → 보안상 안전")
        else:
            print("  [🔴 취약] 기대된 안전한 동작이 일어나지 않았습니다 → 보안상 취약")

def main():
    session = requests.Session()
    tests = load_yaml("security_tests.yaml")["tests"]
    for test in tests:
        run_test(test, session)

if __name__ == "__main__":
    main()
