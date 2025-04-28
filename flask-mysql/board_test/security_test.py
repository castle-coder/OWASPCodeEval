import yaml
import requests
import pymysql
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"

# DB 연결 정보
db_config = {
    'host': 'localhost',
    'user': 'mock_user',
    'password': '1234',
    'db': 'mock_db',
    'cursorclass': pymysql.cursors.DictCursor
}

def load_scenarios(path="scenario.yaml"):
    with open(path, 'r') as file:
        return yaml.safe_load(file)

def login(session, user_id):
    if user_id is not None:
        session.get(f"{BASE_URL}/login/{user_id}")

def check_boards(title, user_id=None):
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            if user_id:
                cursor.execute("SELECT * FROM boards WHERE title=%s AND user_id=%s", (title, user_id))
            else:
                cursor.execute("SELECT * FROM boards WHERE title=%s", (title,))
            result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (boards): {e}")
        return None
    
def check_board_state(post_id):
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            cursor.execute("SELECT title, content, is_blocked, updated_at FROM boards WHERE id=%s", (post_id,))
            result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (board state): {e}")
        return None


def check_reports(reason, user_id=None):
    try:
        conn = pymysql.connect(**db_config)
        with conn.cursor() as cursor:
            if user_id:
                cursor.execute("SELECT * FROM reports WHERE reason=%s AND user_id=%s", (reason, user_id))
            else:
                cursor.execute("SELECT * FROM reports WHERE reason=%s", (reason,))
            result = cursor.fetchone()
        conn.close()
        return result
    except Exception as e:
        print(f"DB 검사 중 오류 발생 (reports): {e}")
        return None

def run_scenario(scenario):
    session = requests.Session()
    login(session, scenario.get('login_user'))

    response = session.post(f"{BASE_URL}{scenario['endpoint']}", data=scenario['data'])
    print(f"[Test ID: {scenario['id']}] {scenario['description']}")
    print(f"Status Code: {response.status_code}")

    # 결과 판단
    is_safe = True
    reason = ""

    if response.status_code >= 500:
        is_safe = False
        reason = "서버 오류 발생"
    elif 'check_db_title' in scenario:
        result = check_boards(scenario['check_db_title'], scenario.get('login_user'))
        if result:
            is_safe = False
            reason = f"DB에 악성 데이터가 삽입됨 (post_id: {result.get('post_id')}, user_id: {result.get('user_id')})"
    elif 'check_report_reason' in scenario:
        result = check_reports(scenario['check_report_reason'], scenario.get('login_user'))
        if result:
            is_safe = False
            reason = f"악성 신고 내용이 DB에 저장됨 (report_id: {result.get('report_id')}, user_id: {result.get('user_id')})"
    elif scenario.get('expect_db_unchanged'):
        # 기본 게시물 상태 저장
        pre_state = check_board_state(post_id=scenario['endpoint'].split('/')[-1])
        
        # 일정 시간 대기 후 재조회
        import time
        time.sleep(0.5)
        post_state = check_board_state(post_id=scenario['endpoint'].split('/')[-1])

        if pre_state != post_state:
            is_safe = False
            reason = f"게시글 내용이 변경됨 또는 차단 상태 변경됨: {pre_state} -> {post_state}"


    print("결과:", "✅ 안전" if is_safe else "❌ 취약")
    if reason:
        print("이유:", reason)
    print("-" * 50)

def main():
    scenarios = load_scenarios()
    for s in scenarios['tests']:
        run_scenario(s)

if __name__ == '__main__':
    main()
