import yaml
import requests
import sqlite3
import os

def status_matches(expected, actual):
    """
    '2xx' → 200~299 / '4xx' → 400~499 / 정수형은 정확히 일치
    """
    if isinstance(expected, str) and expected.endswith("xx"):
        prefix = int(expected[0])
        return prefix * 100 <= actual < (prefix + 1) * 100
    try:
        return int(expected) == actual
    except:
        return False

def load_config(path='scenario.yaml'):
    # 현재 파일이 위치한 디렉토리 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 절대 경로로 scenario.yaml 접근
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
    session = requests.Session()
    last_resp = None

    # 현재 파일이 위치한 디렉토리 경로
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # 절대 경로로 scenario.yaml 접근
    db_path = os.path.join(base_dir, db_path)
    
    for step in scenario['steps']:
        url = base_url + step['path']
        method = step['method'].upper()
        print(f"[+] {method} {step['path']}")
        if method == 'GET':
            last_resp = session.get(url, allow_redirects=False)
        elif method == 'POST':
            last_resp = session.post(url, data=step.get('data', {}), allow_redirects=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

    actual = last_resp.status_code
    expected = scenario['expected']['status_code']
    status_ok = status_matches(expected, actual)
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

    if not status_ok:
        print(f"이유: 예상 코드 {expected}, 실제 코드 {actual}")
    elif db_vuln:
        print("이유: DB에 악성 데이터가 삽입됨")
    print("-" * 50)

if __name__ == '__main__':
    print("flask-sqlite : chat_test 보안 테스트 시작")
    cfg = load_config()
    for scen in cfg['scenarios']:
        run_scenario(cfg['base_url'], scen)
