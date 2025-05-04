# scenario_test.py
import yaml
import requests

def load_scenarios(path="scenario.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)["tests"]

def run_test(test):
    method = test["method"].upper()
    params = test.get("params", {})
    endpoint = test["endpoint"].format(**params)
    url = f"http://localhost:8000{endpoint}"

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
    scenarios = load_scenarios()
    for test in scenarios:
        actual_status = run_test(test)
        print_result(test, actual_status)
