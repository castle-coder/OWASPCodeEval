import re
import sqlite3
import sys
import yaml
import requests
import os

SEPARATOR = '-' * 50

base_dir = os.path.dirname(os.path.abspath(__file__))
def load_yaml(path='scenario.yaml'):
    with open(os.path.join(base_dir, path), encoding='utf-8') as f:
        return yaml.safe_load(f)

def run_http(session, base_url, step):
    url = base_url.rstrip('/') + step['path']
    method = step['method'].upper()
    data = step.get('data', {})
    return session.request(method, url, data=data, allow_redirects=False)

def db_value(conn, table, column, where):
    row = conn.execute(f"SELECT {column} FROM {table} WHERE {where}").fetchone()
    return None if row is None else row[column]

def evaluate_db(expect, value):
    # 평가 규칙: expect 딕셔너리에 어떤 키가 있느냐에 따라 pass/fail 판단
    if 'must_equal' in expect:
        return value == expect['must_equal'], f"값이 {value} (≠ {expect['must_equal']})"
    if 'must_match' in expect:
        matched = re.search(expect['must_match'], str(value) or '')
        return bool(matched), f"값이 '{value}' 에서 패턴 일치 여부={bool(matched)}"
    if 'must_not_match' in expect:
        matched = re.search(expect['must_not_match'], str(value) or '')
        return not matched, f"값이 '{value}' 에서 패턴 일치 여부={bool(matched)}"
    return True, "DB 조건 없음"

def print_result(test_id, name, status_code, safe, reason):
    verdict = "✅ 안전" if safe else "❌ 취약"
    print(SEPARATOR)
    print(f"[Test ID: {test_id}] {name}")
    print(f"Status Code: {status_code}")
    print(f"결과: {verdict}")
    print(f"이유: {reason}")
    print(SEPARATOR)

def main():
    cfg = load_yaml()
    base_url = cfg['base_url']
    db_path  = os.path.join(base_dir, cfg['db_path'])

    for t in cfg['tests']:
        session = requests.Session()

        # 로그인 단계
        login_user = t.get('login_user')
        if login_user:
            session.get(f"{base_url}/login/{login_user}", allow_redirects=False)

        # 실제 요청
        resp = run_http(session, base_url, t['request'])
        status_ok = (resp.status_code == t['expect']['status'])

        # DB 검사
        db_ok = True
        reason = "HTTP 응답 코드 불일치" if not status_ok else "HTTP 응답 정상"

        if 'db' in t['expect']:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                exp = t['expect']['db']
                value = db_value(conn, exp['table'], exp['column'], exp['where'])
                db_ok, db_reason = evaluate_db(exp, value)
                reason = db_reason

        safe = status_ok and db_ok
        print_result(t['id'], t['name'], resp.status_code, safe, reason)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n테스트 중단됨.")
