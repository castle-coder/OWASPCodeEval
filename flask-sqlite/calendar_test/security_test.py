# security_test.py
import yaml
import requests
import sqlite3

def load_config(path='scenario.yaml'):
    with open(path, 'r', encoding='utf-8') as f:
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

def run_scenario(base_url, scenario, db_path='mock_calendar_db.sqlite3'):
    session = requests.Session()
    last_resp = None

    for step in scenario['steps']:
        url = base_url + step['path']
        method = step['method'].upper()
        # 절대 리다이렉트를 따라가지 않도록 설정
        if method == 'GET':
            last_resp = session.get(url, allow_redirects=False)
        elif method == 'POST':
            last_resp = session.post(url, data=step.get('data', {}), allow_redirects=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

    actual = last_resp.status_code
    expected = scenario['expected']['status_code']
    status_ok = (actual == expected)
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
    cfg = load_config()
    for scen in cfg['scenarios']:
        run_scenario(cfg['base_url'], scen)
