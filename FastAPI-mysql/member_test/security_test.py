import yaml
import requests

def load_scenarios(path="scenario.yaml"):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def login_as_user(base_url, user_id):
    return requests.get(f"{base_url}/login/{user_id}")

def run_test(test, base_url):
    url = base_url + test["endpoint"]
    method = test["method"].lower()
    session = requests.Session()

    if "session_login" in test:
        resp = login_as_user(base_url, test["session_login"])
        if resp.status_code != 200:
            return test["id"], "❌ 실패", f"로그인 실패 (user_id: {test['session_login']})"

    resp = getattr(session, method)(url, data=test.get("data", {}), allow_redirects=False)

    # 상태 코드 검증
    expected = test.get("expected_status", 200)
    if resp.status_code != expected:
        return test["id"], "❌ 취약", f"이유: 예상 코드 {expected}, 실제 코드 {resp.status_code}"

    # 콘텐츠 검증
    if "validate" in test:
        if "not_contains" in test["validate"]:
            if test["validate"]["not_contains"] in resp.text:
                return test["id"], "❌ 취약", f"이유: 악성 내용이 포함됨 ({test['validate']['not_contains']})"

    return test["id"], "✅ 안전", "이유: 모든 조건 통과"

def main():
    scenarios = load_scenarios()
    base_url = scenarios["base_url"]
    print("-" * 50)
    for test in scenarios["tests"]:
        test_id, result, reason = run_test(test, base_url)
        print(f"[Test ID: {test_id}] {test['name']}")
        print(f"Status Code: {test.get('expected_status', 200)}")
        print(f"결과: {result}")
        print(f"{reason}")
        print("-" * 50)

if __name__ == "__main__":
    main()