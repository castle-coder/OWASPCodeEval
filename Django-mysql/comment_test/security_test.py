# security_test.py
import yaml
import requests
import sqlite3

BASE_URL = 'http://localhost:8000'

def load_scenarios(path='scenario.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)['tests']

def get_db_state(db_path='mock_db.sqlite3'):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    tables = ['users', 'comments', 'comment_reports']
    state = {}
    for t in tables:
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        state[t] = cur.fetchone()[0]
    conn.close()
    return state

def diff_states(before, after):
    diffs = {}
    for k in before:
        delta = after[k] - before[k]
        if delta != 0:
            diffs[k] = delta
    return diffs

def run_test(test):
    session = requests.Session()

    # Pre-login if needed
    if 'login_user_id' in test:
        session.get(f"{BASE_URL}/login/{test['login_user_id']}/")

    pre_state = get_db_state()

    # Perform the request
    url = BASE_URL + test['url']
    method = test['method'].upper()
    if method == 'GET':
        resp = session.get(url)
    elif method == 'POST':
        resp = session.post(url, data=test.get('payload', {}))
    else:
        raise ValueError(f"Unsupported method {method}")

    status = resp.status_code
    is_safe = status in test['expected_status_codes']
    icon = '✅' if is_safe else '❌'
    result_text = '안전' if is_safe else '취약'
    reason = f"예상 코드 {test['expected_status_codes']}, 실제 코드 {status}"

    print('--------------------------------------------------')
    print(f"[Test ID: {test['id']}] {test['description']}")
    print(f"Status Code: {status}")
    print(f"결과: {icon} {result_text}")
    print(f"이유: {reason}")

    if not is_safe:
        post_state = get_db_state()
        changes = diff_states(pre_state, post_state)
        if changes:
            print("DB Changes:")
            for table, delta in changes.items():
                sign = '+' if delta > 0 else ''
                print(f"  {table}: {sign}{delta}")
    print('--------------------------------------------------\n')

if __name__ == '__main__':
    scenarios = load_scenarios()
    for scenario in scenarios:
        run_test(scenario)

"""
# Excluded OWASP Top 10 and reasons:
# A2_CryptographicFailures: 이 코드에서는 비밀번호 저장이나 해시 처리 로직이 없습니다.
# A4_InsecureDesign: 관리자 비활성화 등의 기능이 구현되어 있지 않습니다.
# A6_VulnerableComponents: 외부 취약 컴포넌트나 라이브러리를 사용하지 않습니다.
# A8_SoftwareAndDataIntegrityFailures: 파일 무결성 검증이나 업데이트 검증 로직이 없습니다.
# A9_SecurityLoggingMonitoring: 로깅/모니터링 기능이 전혀 구현되어 있지 않습니다.
# A10_ServerSideRequestForgery: 외부 서버 호출을 수행하는 엔드포인트가 없습니다.
"""
