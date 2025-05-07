# scenario_test.py
import yaml
import requests
import os

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
    
    # 현재 파일이 위치한 디렉토리 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 절대 경로로 scenario.yaml 접근
    yaml_path = os.path.join(base_dir, "scenario.yaml")
    
    with open(yaml_path) as f:
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
