import requests
import yaml
import pymysql
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"

def db_check(title=None, reason=None):
    conn = pymysql.connect(
        host='localhost', user='mock_user', password='mock_password', db='mock_db',
        charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
    )
    with conn.cursor() as cursor:
        if title:
            cursor.execute("SELECT * FROM calendars WHERE title = %s", (title,))
            return cursor.fetchone()
        if reason:
            cursor.execute("SELECT * FROM reports WHERE reason = %s", (reason,))
            return cursor.fetchone()
    conn.close()
    return None

def run_test(test):
    s = requests.Session()
    if not test.get('unauthenticated', False):
        s.get(f"{BASE_URL}/login/1")  # 로그인 세션 유지

    url = urljoin(BASE_URL, test['endpoint'])
    method = test['method'].upper()
    payload = test.get('payload', {})
    expected = test['expected_status']
    resp = s.post(url, data=payload, allow_redirects=False) if method == "POST" else s.get(url, allow_redirects=False)
    vulnerable = False
    db_reason = ""

    # 응답 코드 확인
    if resp.status_code != expected:
        vulnerable = True
        db_reason += f"예상 코드: {expected}, 실제 코드: {resp.status_code}\n"

    # DB 확인
    if test.get("check_db"):
        if test.get("check_title"):
            db_entry = db_check(title=test["check_title"])
            if db_entry:
                vulnerable = True
                db_reason += f"DB에 악성 데이터가 삽입됨 (post_id: {db_entry.get('id')}, user_id: {db_entry.get('user_id')})\n"
        elif test.get("check_report_reason"):
            db_entry = db_check(reason=test["check_report_reason"])
            if db_entry:
                vulnerable = True
                db_reason += f"악성 신고 내용이 DB에 저장됨 (report_id: {db_entry.get('report_id')}, user_id: {db_entry.get('user_id')})\n"

    # 출력
    print("--------------------------------------------------")
    print(f"[Test ID: {test['id']}] {test['description']}")
    print(f"Status Code: {resp.status_code}")
    if vulnerable:
        print("결과: ❌ 취약")
        if db_reason:
            print(f"이유: {db_reason.strip()}")
    else:
        print("결과: ✅ 안전")

def main():
    with open("scenario.yaml", 'r', encoding='utf-8') as f:
        scenarios = yaml.safe_load(f)
    for test in scenarios['tests']:
        run_test(test)

if __name__ == '__main__':
    main()
