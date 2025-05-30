import yaml
import requests
import os
import sys

# Django settings 초기화
import django
from django.conf import settings

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if not settings.configured:
    settings.configure(
        DEBUG=True,  # 이 값이 시나리오 테스트에서 참조될 항목
        SECRET_KEY='test-secret',
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
        ],
    )
    django.setup()

def load_scenarios():
    scenario_path = os.path.join(BASE_DIR, 'scenario.yaml')
    with open(scenario_path, 'r') as f:
        return yaml.safe_load(f), scenario_path

def run_tests():
    scenarios, scenario_path = load_scenarios()
    base_url = scenarios['base_url']
    tests = scenarios['tests']

    for test in tests:
        full_url = base_url + test['endpoint']
        method = test['method'].upper()
        data = test.get('data', {})
        headers = test.get('headers', {})
        response = None

        try:
            if method == 'POST':
                response = requests.post(full_url, data=data, headers=headers)
            elif method == 'GET':
                response = requests.get(full_url, headers=headers)
            else:
                continue

            status_code = response.status_code
            result = '✅ 안전'
            reason = ''
            vulnerable = test.get('vulnerable', False)

            if 'expect_in' in test:
                if test['expect_in'] in response.text:
                    if vulnerable:
                        result = '❌ 취약'
                        reason = f"응답에 악성 페이로드 포함됨: {test['expect_in']}"
                elif not vulnerable:
                    result = '❌ 취약하지 않지만 의도와 다름'

            elif 'expect_setting' in test:
                setting = test['expect_setting']
                expected = test['expected_value']
                actual = getattr(settings, setting, None)
                if actual == expected:
                    result = '✅ 안전'
                else:
                    result = '❌ 취약'
                    reason = f"{setting} 값이 {actual} (예상: {expected})"

            print(f"--------------------------------------------------")
            print(f"[Test ID: {test['id']}] {test['description']}")
            print(f"Status Code: {status_code}")
            print(f"결과: {result}")
            if reason:
                print(f"이유: {reason}")
            print(f"--------------------------------------------------\n")

        except Exception as e:
            print(f"--------------------------------------------------")
            print(f"[Test ID: {test['id']}] {test['description']}")
            print(f"오류 발생: {str(e)}")
            print(f"--------------------------------------------------\n")

if __name__ == '__main__':
    run_tests()
