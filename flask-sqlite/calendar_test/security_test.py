import yaml
import requests
import sqlite3
import os

def load_config(path='scenario.yaml'):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(base_dir, path)
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def check_db_record(db_path, table, criteria):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cols = list(criteria.keys())
    vals = [criteria[c] for c in cols]
    where = ' AND '.join(f"{c} = ?" for c in cols)
    query = f"SELECT COUNT(*) FROM {table} WHERE {where}"
    cursor.execute(query, vals)
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0

def run_scenario(base_url, scenario, db_path='mock_db.sqlite3'):
    dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(dir, db_path)

    session = requests.Session()
    last_resp = None

    for step in scenario['steps']:
        url = base_url + step['path']
        method = step['method'].upper()
        if method == 'GET':
            last_resp = session.get(url, allow_redirects=False)
        elif method == 'POST':
            last_resp = session.post(url, data=step.get('data', {}), allow_redirects=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

    actual = last_resp.status_code
    expected_range = scenario['expected'].get('status_code_range')
    expected_single = scenario['expected'].get('status_code')

    # 상태코드 검사: 범위 우선, 없으면 단일 코드 비교
    if expected_range:
        status_ok = expected_range[0] <= actual <= expected_range[1]
    elif expected_single:
        status_ok = (actual == expected_single)
    else:
        status_ok = True  # 명시된 검증 없으면 통과로 처리

    db_vuln = False
    if 'no_db_record' in scenario['expected']:
        tbl = scenario['expected']['no_db_record']['table']
        crit = scenario['expected']['no_db_record']['criteria']
        if check_db_record(db_path, tbl, crit):
            db_vuln = True

    print(f"[Test ID: {scenario['id']}] {scenario['description']}")
    print(f"Status Code: {actual}")
    if 'no_db_record' in scenario['expected']:
        print("결과:", "✅ 안전" if status_ok and not db_vuln else "❌ 취약")
    else:
        print("결과:", "✅ 안전" if status_ok else "❌ 취약")

    # 상세 사유 출력
    if not status_ok:
        if expected_range:
            print(f"이유: 예상 코드 범위 {expected_range}, 실제 코드 {actual}")
        else:
            print(f"이유: 예상 코드 {expected_single}, 실제 코드 {actual}")
    elif db_vuln:
        print("이유: DB에 악성 데이터가 삽입됨")
    print("-" * 50)

if __name__ == '__main__':
    print("flask-sqlite : calendar_test 보안 테스트 시작")
    cfg = load_config()
    for scen in cfg['scenarios']:
        run_scenario(cfg['base_url'], scen)
