# security_test.py

import os
import yaml
import requests

def login_as_user(session, base_url, user_id):
    """로그인 후 세션 쿠키만 받고 리다이렉트는 따르지 않음"""
    return session.get(f"{base_url}/login/{user_id}", allow_redirects=False)

def run_scenario(session, base_url, sc):
    login_user = sc.get("login_user_id")
    # 1) 로그인 시도 (필요한 경우) 및 로그인 라인 출력
    if login_user is not None:
        login_as_user(session, base_url, login_user)
        print(f"[+] GET /login/{login_user}")

    # 2) 실제 요청
    method = sc["method"].upper()
    endpoint = sc["endpoint"]
    print(f"[+] {method} {endpoint}")

    url = base_url + endpoint
    headers = sc.get("headers", {})
    data = sc.get("data", None)
    resp = getattr(session, sc["method"].lower())(
        url,
        headers=headers,
        data=data,
        allow_redirects=False
    )

    # 3) 결과 출력
    expected = sc["expected_status"]
    actual = resp.status_code
    print(f"[Test ID: {sc['id']}] {sc['description']}")
    print(f"Status Code: {actual}")
    if actual == expected:
        print("결과: ✅ 안전")
    else:
        print("결과: ❌ 취약")
        print(f"이유: 예상 코드 {expected}, 실제 코드 {actual}")

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base_dir, "scenario.yaml"), "r") as f:
        scenarios = yaml.safe_load(f)["scenarios"]

    base_url = "http://localhost:8000"

    for sc in scenarios:
        print("--------------------------------------------------")
        session = requests.Session()
        run_scenario(session, base_url, sc)
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()
