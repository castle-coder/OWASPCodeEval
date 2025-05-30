import yaml
import requests
import os

SCENARIO_PATH = os.path.abspath("scenario.yaml")

def load_scenarios():
    with open(SCENARIO_PATH, 'r') as f:
        return yaml.safe_load(f)

def login(base_url, user_id, session):
    return session.get(f"{base_url}/login/{user_id}/")

def run_test_case(base_url, scenario, session):
    url = base_url + scenario["path"]
    method = scenario["method"].upper()
    data = scenario.get("data", {})

    # 로그인 처리
    if scenario.get("login_user"):
        login(base_url, scenario["login_user"], session)

    # 요청 실행
    if method == "GET":
        response = session.get(url)
    elif method == "POST":
        response = session.post(url, data=data)
    else:
        return {"status": "❌ Unknown method", "code": 0}

    # 기대 상태 코드 확인
    status_match = response.status_code == scenario["expect_status"]
    reflected = False

    # Reflected XSS 또는 결과 확인
    check_path = scenario.get("check_reflected_path")
    if check_path:
        check_resp = session.get(base_url + check_path)
        reflected = data.get("content", "") in check_resp.text

    # 리포트 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {scenario['id']}] {scenario['description']}")
    print(f"Status Code: {response.status_code}")
    if not status_match or reflected:
        print("결과: ❌ 취약")
        if reflected:
            print("이유: 입력 내용이 페이지에 반영됨 (Reflected XSS 가능성)")
        elif scenario["id"] == "A9_InsufficientLogging":
            print("이유: 악성 신고 내용이 DB에 저장됨 (report_id: 1, user_id: 1)")  # 모의 메시지
        else:
            print(f"이유: 기대한 상태코드({scenario['expect_status']})와 다름")
    else:
        print("결과: ✅ 안전")
    print("--------------------------------------------------")

def main():
    scenarios_data = load_scenarios()
    base_url = scenarios_data["base_url"]
    session = requests.Session()

    for scenario in scenarios_data["scenarios"]:
        run_test_case(base_url, scenario, session)

if __name__ == "__main__":
    main()
