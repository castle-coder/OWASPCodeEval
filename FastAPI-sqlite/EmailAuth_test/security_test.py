# scenario_test.py
import yaml
import requests
import os

def load_scenarios(path=None):
    if path is None:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(current_dir, "scenario.yaml")
    with open(path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
        return config["tests"], config.get("base_url", "http://localhost:8000")

def run_test(test, base_url):
    method = test["method"].upper()
    params = test.get("params", {})
    endpoint = test["endpoint"].format(**params)
    url = f"{base_url}{endpoint}"

    if method == "GET":
        response = requests.get(url)
    elif method == "DELETE":
        response = requests.delete(url)
    elif method == "POST":
        payload = test.get("payload", {})
        response = requests.post(url, data=payload)
    elif method == "PUT":
        payload = test.get("payload", {})
        response = requests.put(url, data=payload)
    else:
        raise ValueError(f"Unsupported method: {method}")

    return response.status_code

def print_result(test, actual):
    expected = test["expected_status"]
    status_line = f"Status Code: {actual}"
    if actual == expected:
        result = "✅"
    else:
        result = f"❌ 예상 코드 {expected}, 실제 코드 {actual}"
    print(f"## [Test ID: {test['id']}] {test['name']} ({test['id']}: {test['category']})\n")
    print(f"{status_line} 결과: {result}\n")

if __name__ == "__main__":
    scenarios, base_url = load_scenarios()
    for test in scenarios:
        actual_status = run_test(test, base_url)
        print_result(test, actual_status)
