# scenario_test.py
import yaml
import requests
import os

BASE_URL = "http://localhost:8000"

def run_tests():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(current_dir, "scenario.yaml")
    with open(scenario_path, "r", encoding="utf-8") as f:
        suite = yaml.safe_load(f)

    for test in suite['tests']:
        tid = test['id']
        name = test['name']
        method = test['method'].upper()
        url = BASE_URL + test['endpoint']
        headers = test.get('headers', {})
        body = test.get('body', None)

        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            # choose data vs raw body
            if headers.get("Content-Type", "").startswith("application/xml") or headers.get("Content-Type", "").startswith("application/octet-stream"):
                resp = requests.post(url, headers=headers, data=body)
            else:
                resp = requests.post(url, headers=headers, data=body or {})
        else:
            continue

        status = resp.status_code
        expected = test['expected_status']

        print(f"## [Test ID: {tid}] {name} ({tid}: {name})\n")
        if status == expected:
            print(f"Status Code: {status} 결과: ✅\n")
        else:
            print(f"Status Code: {status} 결과: ❌ 예상 코드 {expected}, 실제 코드 {status}\n")

if __name__ == "__main__":
    run_tests()
