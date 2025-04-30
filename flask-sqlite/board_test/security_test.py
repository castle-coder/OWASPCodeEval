import yaml
import requests
import sqlite3
import time
from urllib.parse import urljoin

BASE_URL = "http://127.0.0.1:5000"
DB_PATH = 'mock_db.sqlite3'

def load_scenarios(path="scenario.yaml"):
    with open(path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def login(session, user_id):
    if user_id is not None:
        session.get(f"{BASE_URL}/login/{user_id}")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_boards(title, user_id=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM boards WHERE title=? AND user_id=?", (title, user_id))
        else:
            cursor.execute("SELECT * FROM boards WHERE title=?", (title,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (boards): {e}")
        return None

def check_board_state(post_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT title, content, is_blocked, updated_at FROM boards WHERE id=?", (post_id,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (board state): {e}")
        return None

def check_reports(reason, user_id=None):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        if user_id:
            cursor.execute("SELECT * FROM reports WHERE reason=? AND user_id=?", (reason, user_id))
        else:
            cursor.execute("SELECT * FROM reports WHERE reason=?", (reason,))
        result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (reports): {e}")
        return None

def run_scenario(scenario):
    session = requests.Session()
    login(session, scenario.get('login_user'))

    url = urljoin(BASE_URL, scenario['endpoint'])
    method = "POST"
    payload = scenario.get('data', {})
    expected = scenario['expected_status']

    resp = session.post(url, data=payload, allow_redirects=False)

    print(f"--------------------------------------------------")
    print(f"[Test ID: {scenario['id']}] {scenario['description']}")
    print(f"Status Code: {resp.status_code}")

    is_safe = True
    db_reason = ""

    if resp.status_code != expected:
        is_safe = False
        db_reason += f"예상 코드: {expected}, 실제 코드: {resp.status_code}\n"

    if scenario.get("check_db_title"):
        result = check_boards(scenario["check_db_title"], scenario.get("login_user"))
        if result:
            is_safe = False
            db_reason += f"DB에 악성 데이터가 삽입됨 (post_id: {result['id']}, user_id: {result['user_id']})\n"

    if scenario.get("check_report_reason"):
        result = check_reports(scenario["check_report_reason"], scenario.get("login_user"))
        if result:
            is_safe = False
            db_reason += f"악성 신고 내용이 DB에 저장됨 (report_id: {result['report_id']}, user_id: {result['user_id']})\n"

    if scenario.get("expect_db_unchanged"):
        pre_state = check_board_state(post_id=scenario['endpoint'].split('/')[-1])
        time.sleep(0.5)
        post_state = check_board_state(post_id=scenario['endpoint'].split('/')[-1])

        if pre_state != post_state:
            is_safe = False
            db_reason += f"게시글 내용이 변경됨 또는 차단 상태 변경됨: {pre_state} -> {post_state}\n"

    if is_safe:
        print("결과: ✅ 안전")
    else:
        print("결과: ❌ 취약")
        if db_reason:
            print("이유:", db_reason.strip())
    print("-" * 50)

def main():
    scenarios = load_scenarios()
    for s in scenarios['tests']:
        run_scenario(s)

if __name__ == '__main__':
    main()
