# security_test.py
import yaml
import requests
import sqlite3
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(base_dir, 'mock_db.sqlite3')

BASE_URL = "http://127.0.0.1:5000"

def in_range(code, pattern):
    if pattern.endswith("xx") and len(pattern) == 3:
        start = int(pattern[0]) * 100
        return start <= code < start + 100
    return False

def run_test(s):
    test_id = s['id']
    desc = s['description']
    req = s['request']
    method = req['method']
    url = BASE_URL + req['url']
    headers = req.get('headers', {})
    params = req.get('params')
    data = req.get('data')
    form = req.get('form')
    cookies = req.get('cookies', {})

    sess = requests.Session()
    if 'session' in req:
        # 모든 세션 값을 문자열로 변환
        safe = {k: str(v) for k, v in req['session'].items()}
        sess.cookies.update(safe)

    resp = sess.request(
        method, url,
        headers=headers,
        params=params,
        data=form or data
    )

    status = resp.status_code
    expect = s['expect']
    passed = True
    reason = []

    # -- HTTP 상태 코드 검증
    if 'status_code' in expect:
        if status != expect['status_code']:
            passed = False
            reason.append(f"상태 코드 {status}, 예상 {expect['status_code']}")
    elif 'status_code_range' in expect:
        if not in_range(status, expect['status_code_range']):
            passed = False
            reason.append(f"상태 코드 {status}, 예상 범위 {expect['status_code_range']}")

    # -- HTTP 헤더 검증
    for h, v in expect.get('headers', {}).items():
        actual = resp.headers.get(h)
        if actual != v:
            passed = False
            reason.append(f"헤더 {h}: {actual} (예상 {v})")

    # -- 응답 본문 검증
    if 'body_contains' in expect:
        if expect['body_contains'] not in resp.text:
            passed = False
            reason.append(f"본문에 '{expect['body_contains']}' 없음")

    # -- DB 검증 (scenario.yaml 에 db_check가 정의된 경우)
    if 'db_check' in s:
        db = sqlite3.connect(DB_PATH)
        cur = db.cursor()
        query = s['db_check']['query']
        cur.execute(query)
        actual_value = cur.fetchone()[0]
        db.close()

        expected_value = s['db_check']['expected']
        if actual_value != expected_value:
            passed = False
            reason.append(f"DB 검증 실패: `{query}` → {actual_value} (예상 {expected_value})")

    # -- 결과 출력
    result = "✅ 안전" if passed else "❌ 취약"
    print("─" * 50)
    print(f"[Test ID: {test_id}] {desc}")
    print(f"Status Code: {status}")
    print(f"결과: {result}")
    if reason:
        print("이유: " + "; ".join(reason))
    print("─" * 50 + "\n")


if __name__ == "__main__":
    with open(os.path.join(base_dir,"scenario.yaml"), "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    for scenario in cfg['scenarios']:
        run_test(scenario)
