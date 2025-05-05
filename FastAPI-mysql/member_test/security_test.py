# security_test.py
import yaml
import requests

BASE_URL = "http://127.0.0.1:5000"

def load_scenarios(path="scenario.yaml"):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['scenarios']

def run_test(sc, session):
    login = sc.get('login')
    if login:
        session.get(f"{BASE_URL}/login/{login['user_id']}")

    method = sc['method'].upper()
    url = BASE_URL + sc['endpoint']
    data = sc.get('data', {})

    if method == 'GET':
        resp = session.get(url)
    else:
        resp = session.post(url, data=data)

    actual = resp.status_code
    expected = sc['expected_status']
    result = '✅ 안전' if actual == expected else '❌ 취약'

    print(f"[Test ID: {sc['id']}] {sc['description']}")
    print(f"Status Code: {actual}")
    print(f"결과: {result}")
    print(f"이유: 예상 코드: {expected}, 실제 코드: {actual}")
    print("--------------------------------------------------\n")

def main():
    scenarios = load_scenarios()
    session = requests.Session()
    for sc in scenarios:
        run_test(sc, session)

if __name__ == "__main__":
    main()
