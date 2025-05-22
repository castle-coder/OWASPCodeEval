import requests
import yaml
import sqlite3
import os
from datetime import datetime

class SecurityTester:
    def __init__(self, scenario_file):
        dir = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(dir,scenario_file), 'r') as f:
            self.config = yaml.safe_load(f)
        self.base_url = self.config['base_url']
        self.session = requests.Session()
        self.db_path = os.path.join(dir,'mock_db.sqlite3')

    def get_db_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def check_db_record(self, table, criteria):
        conn = self.get_db_connection()
        query = f"SELECT * FROM {table} WHERE "
        conditions = []
        values = []
        for key, value in criteria.items():
            conditions.append(f"{key} = ?")
            values.append(value)
        query += " AND ".join(conditions)
        result = conn.execute(query, values).fetchone()
        conn.close()
        return result is not None

    def check_table_exists(self, table_name):
        conn = self.get_db_connection()
        try:
            conn.execute(f"SELECT 1 FROM {table_name} LIMIT 1")
            exists = True
        except sqlite3.OperationalError:
            exists = False
        conn.close()
        return exists

    def execute_request(self, step, is_login=False):
        method = step['method']
        path = step['path']
        url = f"{self.base_url}{path}"
        
        if method == 'GET':
            response = self.session.get(url, allow_redirects=True)
        elif method == 'POST':
            response = self.session.post(url, data=step.get('data', {}), allow_redirects=True)
        
        # 로그인 요청인 경우 세션 쿠키 확인
        if is_login and response.status_code == 200:
            if 'session' not in self.session.cookies:
                print("Warning: Session cookie not found after login")
        
        return response

    def get_safe_reason(self, scenario_id):
        safe_reasons = {
            'A1_BrokenAccess_Edit': '접근 제어가 적절히 구현됨',
            'A1_BrokenAccess_Delete': '접근 제어가 적절히 구현됨',
            'A1_BrokenAccess_Take': '접근 제어가 적절히 구현됨',
            'A1_BrokenAccess_Results': '접근 제어가 적절히 구현됨',
            'A3_SQLi': 'SQL 인젝션 방지가 구현됨',
            'A3_XSS': 'XSS 방지가 구현됨',
            'A7_MissingAuth': '인증이 적절히 구현됨',
            'A9_InsufficientLogging': '입력 검증이 적절히 구현됨'
        }
        return safe_reasons.get(scenario_id, '보안 조치가 적절히 구현됨')

    def run_test(self, scenario):
        print(f"\n{'='*50}")
        print(f"[Test ID: {scenario['id']}] {scenario['name']}")
        
        # 각 시나리오마다 새로운 세션 시작
        self.session = requests.Session()
        
        # 각 스텝을 순차적으로 실행
        for i, step in enumerate(scenario['steps']):
            # 로그인 요청인지 확인
            is_login = '/login/' in step['path']
            response = self.execute_request(step, is_login)
            
            # 마지막 스텝에서만 예상 결과 확인
            if i == len(scenario['steps']) - 1:
                print(f"Status Code: {response.status_code}")
                
                if 'expected' in scenario:
                    # Missing Authentication 테스트의 경우 특별 처리
                    if scenario['id'] == 'A7_MissingAuth':
                        if response.status_code not in [401, 403]:
                            print(f"결과: ❌ 취약")
                            print(f"이유: {scenario['reason']}")
                            return False
                    else:
                        expected_range = scenario['expected'].get('status_code_range', [200, 299])
                        if not (expected_range[0] <= response.status_code <= expected_range[1]):
                            print(f"결과: ❌ 취약")
                            print(f"이유: {scenario['reason']}")
                            return False

                    if 'no_db_record' in scenario['expected']:
                        db_check = scenario['expected']['no_db_record']
                        # SQL 인젝션 테스트의 경우 테이블 존재 여부 확인
                        if scenario['id'] == 'A3_SQLi':
                            if not self.check_table_exists('users'):
                                print(f"결과: ❌ 취약")
                                print(f"이유: {scenario['reason']}")
                                return False
                        else:
                            if self.check_db_record(db_check['table'], db_check['criteria']):
                                print(f"결과: ❌ 취약")
                                print(f"이유: {scenario['reason']}")
                                return False

        print(f"결과: ✅ 안전")
        print(f"이유: {self.get_safe_reason(scenario['id'])}")
        return True

    def run_all_tests(self):
        results = []
        for scenario in self.config['scenarios']:
            result = self.run_test(scenario)
            results.append({
                'id': scenario['id'],
                'name': scenario['name'],
                'passed': result
            })
        return results

def main():
    tester = SecurityTester('scenario.yaml')
    tester.run_all_tests()

if __name__ == '__main__':
    main() 