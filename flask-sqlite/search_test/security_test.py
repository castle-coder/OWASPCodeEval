import yaml
import requests
import pymysql

BASE_HEADERS = {'Content-Type': 'application/x-www-form-urlencoded'}

DB_CONFIG = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': 'mock_password',
    'db': 'mock_db',
    'cursorclass': pymysql.cursors.DictCursor
}

def load_scenarios():
    with open("scenario.yaml", 'r') as f:
        return yaml.safe_load(f)

def login(session, base_url, user_id):
    session.get(f"{base_url}/login/{user_id}")

def check_db_for_keyword(keyword):
    with pymysql.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM searches WHERE keyword = %s", (keyword,))
            result = cursor.fetchone()
            return result

def print_result(scenario_id, description, status_code, expect_status, safe_expected, is_safe, reason=None):
    print(f"[Test ID: {scenario_id}] {description}")
    print(f"Status Code: {status_code}")
    if is_safe == safe_expected:
        print("결과: ✅ 안전")
    else:
        print("결과: ❌ 취약")
        if reason:
            print(f"이유: {reason}")
    print("--------------------------------------------------")

def run_scenario(session, base_url, scenario):
    scenario_id = scenario['id']
    description = scenario.get('description', '설명 없음')
    url = base_url + scenario['endpoint']
    method = scenario['method'].upper()

    # 로그인
    if 'login_user' in scenario:
        login(session, base_url, scenario['login_user'])

    # 요청 수행
    data = scenario.get('data')
    if method == 'POST':
        response = session.post(url, data=data, headers=BASE_HEADERS)
    else:
        response = session.get(url)

    # 검증
    is_status_match = response.status_code == scenario['expect_status']
    db_match = True
    reason = None

    if 'check_db_keyword' in scenario:
        result = check_db_for_keyword(scenario['check_db_keyword'])
        db_match = result is not None
        if not db_match:
            reason = f"DB에 '{scenario['check_db_keyword']}' 이(가) 저장되지 않음"
        else:
            reason = f"DB에 악성 데이터가 삽입됨 (search_id: {result['search_id']}, user_id: {result['user_id']})"

    is_redirect_ok = True
    if 'expect_redirect' in scenario:
        is_redirect_ok = scenario['expect_redirect'] in response.url

    is_safe = is_status_match and db_match and is_redirect_ok
    print_result(scenario_id, description, response.status_code, scenario['expect_status'], scenario['expect_safe'], is_safe, reason if not is_safe else None)

def main():
    scenarios = load_scenarios()
    base_url = scenarios['base_url']
    session = requests.Session()

    for scenario in scenarios['scenarios']:
        run_scenario(session, base_url, scenario)

if __name__ == "__main__":
    main()
