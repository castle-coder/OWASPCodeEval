import yaml
import requests
import sqlite3
import os
import shutil

# uploads 디렉토리와 dummy.txt 생성
os.makedirs('uploads', exist_ok=True)
with open('uploads/dummy.txt', 'w') as f:
    f.write('sample file')

def load_scenarios(path='scenario.yaml'):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)

def run_test(base_url, test):
    sess = requests.Session()
    if test.get('login'):
        sess.get(f"{base_url}/login/{test['login']}")

    url = base_url + test['endpoint']
    method = test.get('method', 'GET').upper()

    if method == 'POST':
        files = {}
        for key, val in test.get('files', {}).items():
            files[key] = (val[0], val[1].encode(), val[2])
        resp = sess.post(url, files=files, data=test.get('form', {}))
    else:
        resp = sess.get(url)

    status = resp.status_code
    vuln = False
    reason = ''
    chk = test['check']

    conn = sqlite3.connect('mock_db.sqlite3')
    cursor = conn.cursor()

    if chk['type'] == 'status_code':
        expect = chk.get('expect')
        if status != expect:
            vuln = True
            reason = chk['reason']

    elif chk['type'] == 'status_code_in':
        expected = chk.get('expect', [])
        if status not in expected:
            vuln = True
            reason = chk['reason']

    elif chk['type'] == 'db_entry':
        try:
            cursor.execute(chk['query'])
            row = cursor.fetchone()
            if row:
                vuln = True
                reason = chk['reason'].format(*row)
        except Exception as e:
            vuln = True
            reason = f"쿼리 실행 실패 또는 예외 발생: {e}"

    elif chk['type'] == 'content':
        content = resp.text
        if chk.get('should_not_contain') in content:
            vuln = True
            reason = chk['reason']

    conn.close()
    return status, vuln, reason

def main():
    cfg = load_scenarios()
    base_url = cfg['base_url']
    for t in cfg['tests']:
        status, vuln, reason = run_test(base_url, t)
        result = '❌ 취약' if vuln else '✅ 안전'
        print('--------------------------------------------------')
        print(f"[Test ID: {t['id']}] {t['title']}")
        print(f"Status Code: {status}")
        print(f"결과: {result}")
        if vuln:
            print(f"이유: {reason}")
        print('--------------------------------------------------')
    # 테스트 끝난 후 uploads 폴더 삭제
    if os.path.exists('uploads'):
        shutil.rmtree('uploads')


if __name__ == '__main__':
    main()