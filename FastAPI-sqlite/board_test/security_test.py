import requests
import yaml
import sqlite3
import os


def run_test(scenario, base_url, db_file):
    test_id = scenario['id']
    name = scenario['name']
    session = requests.Session()

    # HTTP Basic Auth 설정
    auth = scenario.get('auth')
    if auth:
        session.auth = (auth['username'], auth['password'])

    url = base_url + scenario['endpoint']
    method = scenario['method'].upper()
    data = scenario.get('data', {})
    resp = session.request(method, url, data=data, allow_redirects=False)

    status_code = resp.status_code
    expected = scenario.get('expected_status')
    result = '✅ 안전' if status_code == expected else '❌ 취약'
    reason = f"예상 상태 코드 {expected}이(가) 아님 (실제: {status_code})" if status_code != expected else "상태 코드가 예상과 일치함"

    # DB 검사
    if 'check_db' in scenario and status_code == expected:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        tbl = scenario['check_db']['table']
        col = scenario['check_db']['column']
        payload = scenario['check_db'].get('payload')

        cur.execute(f"SELECT {col} FROM {tbl} ORDER BY report_id DESC LIMIT 1")
        row = cur.fetchone()
        if row and payload and row[0] == payload:
            reason = f"{name}이(가) DB에 삽입됨 ({col}: {row[0]})"
            result = '❌ 취약'
        else:
            reason = f"{name}이(가) DB에 삽입되지 않음"
        conn.close()

    # Header 검사
    elif 'check_headers' in scenario and status_code == expected:
        header = scenario['check_headers']['header']
        must = scenario['check_headers']['must_contain']
        hdr_val = resp.headers.get(header, '')
        if must in hdr_val:
            reason = f"{header}에 '{must}' 존재"
        else:
            reason = f"{header}에 '{must}' 없음"
            result = '❌ 취약'

    # 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {test_id}] {name}")
    print(f"Status Code: {status_code}")
    print(f"결과: {result}")
    print(f"이유: {reason}")
    print("--------------------------------------------------\n")


if __name__ == "__main__":
    # 현재 스크립트의 절대 경로 가져오기
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # YAML 로드
    yaml_path = os.path.join(current_dir, "scenario.yaml")
    with open(yaml_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    base_url = config['base_url']
    db_file = os.path.join(current_dir, config['db_file'])

    for scenario in config['scenarios']:
        if scenario.get('skip'):
            continue
        run_test(scenario, base_url, db_file)
