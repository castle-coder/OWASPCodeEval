# security_test.py
import yaml
import requests

# 시나리오 불러오기
with open('scenario.yaml') as f:
    config = yaml.safe_load(f)

for test in config['tests']:
    session = requests.Session()
    login_id = test['setup']['login']
    # 로그인 처리
    if login_id:
        session.get(f"http://localhost:8000/login/{login_id}/")

    # 요청 실행
    method = test['request']['method']
    url = test['request']['url']
    resp = session.request(method, url)

    # 결과 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {test['id']}] {test['description']}")
    print(f"Status Code: {resp.status_code}")
    if resp.status_code in test['expected_status']:
        print("결과: ✅ 안전")
        print("이유: 모든 조건 통과")
    else:
        expected = ', '.join(str(c) for c in test['expected_status'])
        print("결과: ❌ 취약")
        print(f"이유: 예상 코드 {expected}, 실제 코드 {resp.status_code}")
        if test.get('db_change'):
            print(f"DB 변화: {test['db_change']}")
    print("--------------------------------------------------")

# 포함되지 않은 OWASP Top 10 항목 및 제외 이유
# A2_CryptographicFailures: 비밀번호 저장/관리 기능이 존재하지 않음
# A3_Injection: Django ORM 사용으로 SQL 인젝션 불가능
# A6_VulnerableComponents: 외부 암호화 컴포넌트 사용이 없어 테스트 대상 아님
# A8_SoftwareAndDataIntegrityFailures: 데이터 무결성 체크 로직이 없어 테스트 대상 아님
# A9_SecurityLoggingMonitoring: 로깅 기능이 구현되어 있지 않음
# A10_ServerSideRequestForgery: 외부 URL 요청 로직이 없어 SSRF 불가능