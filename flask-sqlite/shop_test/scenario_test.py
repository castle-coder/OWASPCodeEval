# scenario_test.py
#!/usr/bin/env python3

import yaml
import requests


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
    scenarios = load_scenarios("scenario.yaml")
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
    main()
