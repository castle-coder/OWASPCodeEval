# scenario_test.py
import yaml
import requests

def run_test(test):
    method = test['method'].upper()
    url = test['url']
    expected = test['expected_status']
    params = test.get('params')
    data = test.get('data')
    try:
        if method == 'GET':
            resp = requests.get(url, params=params or {})
        elif method == 'POST':
            resp = requests.post(url, data=data or {})
        else:
            return None, expected
        return resp.status_code, expected
    except Exception as e:
        return None, expected

def main():
    with open('scenario.yaml') as f:
        cfg = yaml.safe_load(f)
    for t in cfg['tests']:
        code, exp = run_test(t)
        status = code if code is not None else 'ERR'
        passed = (code == exp)
        header = f"## [Test ID: {t['id']}] {t['name']} ({t['id']}: {t['category']})"
        if passed:
            print(f"{header}\n\nStatus Code: {status} 결과: ✅\n")
        else:
            print(f"{header}\n\nStatus Code: {status} 결과: ❌ 예상 코드 {exp}, 실제 코드 {status}\n")

if __name__ == "__main__":
    main()
