# security_test.py
import yaml
import requests

def load_scenarios(path="scenario.yaml"):
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def main():
    config = load_scenarios()
    base = config['base_url'].rstrip('/')
    session = requests.Session()

    for s in config['scenarios']:
        # 1) 로그인
        if s.get('login_user_id') is not None:
            login_url = f"{base}/login/{s['login_user_id']}/"
            session.get(login_url)

        url = f"{base}{s['endpoint']}"
        method = s['method'].upper()
        payload = s.get('payload', {})

        if method == "GET":
            resp = session.get(url)
        elif method == "POST":
            resp = session.post(url, data=payload)
        else:
            print(f"[{s['id']}] 지원되지 않는 메서드: {method}")
            continue

        actual = resp.status_code
        expected = s['expected_safe_status_codes']
        safe = actual in expected

        result = "✅ 안전" if safe else "❌ 취약"
        if safe:
            reason = "모든 조건 통과"
        else:
            reason = f"예상 코드 {', '.join(map(str, expected))}, 실제 코드 {actual}"

        print(f"[Test ID: {s['id']}] {s['name']}\n")
        print(f"Status Code: {actual}\n")
        print(f"결과: {result}\n")
        print(f"이유: {reason}\n")
        print(f"DB Changes: {s['db_effect']}\n")
        print("-" * 50 + "\n")

if __name__ == "__main__":
    main()


# 제외된 OWASP Top10 항목 및 이유
# A2_CryptographicFailures: 패스워드 저장·관리 기능이 구현되어 있지 않음
# A6_VulnerableComponents: bcrypt 등 외부 암호화 컴포넌트 사용이 없음
# A8_SoftwareAndDataIntegrityFailures: 데이터 업데이트 엔드포인트가 없어 해당 시나리오 적용 불가
# A10_ServerSideRequestForgery: 외부 URL fetch 기능이 없어 SSRF 테스트 불필요