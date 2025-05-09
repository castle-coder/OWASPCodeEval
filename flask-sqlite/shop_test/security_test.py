# scenario_test.py
#!/usr/bin/env python3

import yaml
import requests
import os


def load_scenarios(path):

    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("scenarios", [])


def run_scenario(session, scenario):
    last_response = None

    steps = scenario.get("steps")
    if steps:
        for step in steps:
            if "login" in step:
                user_id = step["login"]
                last_response = session.get(
                    f"http://localhost:5000/login/{user_id}", allow_redirects=False
                )
            elif "request" in step:
                req = step["request"]
                method = req.get("method", "GET").upper()
                url = req["url"]
                headers = req.get("headers") or {}
                data = req.get("data")
                last_response = session.request(
                    method, url, headers=headers, data=data, allow_redirects=False
                )
    else:
        req = scenario["request"]
        method = req.get("method", "GET").upper()
        url = req["url"]
        headers = req.get("headers") or {}
        data = req.get("data")
        last_response = requests.request(
            method, url, headers=headers, data=data, allow_redirects=False
        )

    return last_response


def main():

    # 현재 파일이 위치한 디렉토리 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 절대 경로로 scenario.yaml 접근
    yaml_path = os.path.join(base_dir, "scenario.yaml")
    scenarios = load_scenarios(yaml_path)
    session = requests.Session()

    for s in scenarios:
        resp = run_scenario(session, s)
        expected = s["expect"].get("status_code")
        actual = resp.status_code if resp is not None else None
        mark = "✅" if actual == expected else "❌"
        reason = (
            f" 예상 코드 {expected}, 실제 코드 {actual}" if actual != expected else ""
        )
        print(f"## [Test ID: {s['id']}] {s['name']}\n")
        print(f"Status Code: {actual} 결과: {mark}{reason}\n")


if __name__ == "__main__":
    print("flask-sqlite : shop_test 보안 테스트 시작")
    main()
