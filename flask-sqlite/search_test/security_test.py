import requests
import yaml

def login(session, user_id):
    return session.get(f"http://127.0.0.1:5000/login/{user_id}")

def run_test(test, session, base_url):
    url = base_url + test['path']
    method = test.get('method', 'GET').upper()
    data = test.get('data', {})

    # Optional login
    if 'login_user' in test:
        login(session, test['login_user'])

    try:
        if method == 'POST':
            response = session.post(url, data=data, allow_redirects=False)
        else:
            response = session.get(url, allow_redirects=False)

        status_code = response.status_code
        redirected = (300 <= status_code < 400)

        # Determine if expected behavior occurred
        passed = True
        reason = "Expected redirect" if test.get("expect_redirect", False) and redirected else "Executed without error"
        if test.get("expect_redirect", False) and not redirected:
            passed = False
            reason = "Did not redirect as expected"

        print("--------------------------------------------------")
        print(f"[Test ID: {test['id']}] {test['description']}")
        print(f"Status Code: {status_code}")
        print(f"결과: {'✅ 안전' if passed else '❌ 취약'}")
        print(f"이유: {reason}")
        print("--------------------------------------------------")

    except Exception as e:
        print("--------------------------------------------------")
        print(f"[Test ID: {test['id']}] {test['description']}")
        print("결과: ❌ 오류 발생")
        print(f"이유: {str(e)}")
        print("--------------------------------------------------")

def main():
    
    with open("scenario.yaml", "r", encoding='utf-8') as file:
        config = yaml.safe_load(file)

    base_url = config['base_url']
    tests = config['tests']

    for test in tests:
        session = requests.Session()
        run_test(test, session, base_url)

if __name__ == "__main__":
    main()
