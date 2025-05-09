import yaml
import requests
import sqlite3
import time
import re
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(base_dir, 'mock_db.sqlite3')

def load_config(path='scenario.yaml'):
    # 절대 경로로 scenario.yaml 접근
    yaml_path = os.path.join(base_dir, path)
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def query_db(query, params=()):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(query, params)
    result = cur.fetchall()
    conn.commit()
    conn.close()
    return result

def create_notification_via_api(session, base_url, pre):
    data = {
        'recipient_user_id': pre['create_notification']['recipient_user_id'],
        'sender_user_id':    pre['create_notification']['sender_user_id'],
        'message':           pre['create_notification']['message']
    }
    resp = session.post(base_url + '/notifications', data=data, allow_redirects=False)
    # wait a moment for DB write
    time.sleep(0.1)
    # find the new notification id by message
    rows = query_db(
        "SELECT id FROM notifications WHERE message = ? ORDER BY created_at DESC LIMIT 1",
        (data['message'],)
    )
    return rows[0][0] if rows else None

def run_scenario(base_url, scen):
    session = requests.Session()
    placeholder = {}

    # setup
    for setup in scen.get('setup', []):
        if 'set_cookie' in setup:
            session.cookies.set(setup['set_cookie']['name'],
                                setup['set_cookie']['value'])

    # preconditions
    for pre in scen.get('preconditions', []):
        if 'login' in pre:
            session.get(f"{base_url}/login/{pre['login']}", allow_redirects=False)
        if 'create_notification' in pre:
            nid = create_notification_via_api(session, base_url, pre)
            placeholder['notification_id'] = nid

    last_resp = None
    # steps
    for step in scen.get('steps', []):
        method = step['method'].upper()
        # build path, substitute placeholders
        path = step['path']
        for key, val in placeholder.items():
            path = path.replace(f"{{{key}}}", str(val))
        url = base_url + path

        print(f"[+] {method} {path}")
        if method == 'GET':
            last_resp = session.get(url, allow_redirects=False)
        elif method in ('POST', 'PUT', 'DELETE'):
            data = step.get('body') or step.get('data') or {}
            last_resp = session.request(method, url, data=data, allow_redirects=False)
        else:
            raise ValueError(f"Unsupported method: {method}")

    # validate
    exp = scen['expected']
    actual_code = last_resp.status_code
    name = scen.get('name', scen['id'])
    print(f"[Test ID: {scen['id']}] {name}")
    print(f"Status Code: {actual_code} (expected {exp['status_code']})")
    ok = (actual_code == exp['status_code'])

    # redirect
    if 'redirect' in exp:
        loc = last_resp.headers.get('Location', '')
        print(f"Redirect: {loc} (expected {exp['redirect']})")
        ok &= (loc == exp['redirect'])

    # db integrity
    if 'db_integrity' in exp:
        tbl = exp['db_integrity']['table_should_exist']
        try:
            query_db(f"SELECT 1 FROM {tbl} LIMIT 1")
            print(f"DB Check: table '{tbl}' exists")
        except sqlite3.OperationalError:
            print(f"DB Check: table '{tbl}' missing")
            ok = False

    # body_contains / not_contains
    text = last_resp.text
    for key in ('body_contains', 'body_not_contains'):
        for item in exp.get(key, []):
            contains = item in text
            if key == 'body_contains':
                print(f"Body contains '{item}': {contains}")
                ok &= contains
            else:
                print(f"Body not contains '{item}': {not contains}")
                ok &= (not contains)

    # method not allowed
    if not ok:
        print("결과: ❌ 취약")
    else:
        print("결과: ✅ 안전")
    print("-" * 50)

if __name__ == '__main__':
    
    print("flask-sqlite : notification_test 보안 테스트 시작")
    cfg = load_config('scenario.yaml')
    for scen in cfg['scenarios']:
        run_scenario(cfg['base_url'], scen)
