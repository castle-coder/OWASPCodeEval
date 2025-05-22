import yaml
import requests
import os

def main():
    base_url = "http://127.0.0.1:5000"
    
    dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(dir,"scenario.yaml"), "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    for scenario in config.get("scenarios", []):
        method = scenario["method"].upper()
        url = base_url + scenario["endpoint"]
        data = scenario.get("data", {})

        try:
            if method == "GET":
                response = requests.get(url)
            elif method == "POST":
                response = requests.post(url, data=data)
            else:
                print(f"Unsupported HTTP method: {method}")
                continue
        except Exception as e:
            print("--------------------------------------------------")
            print(f"[Test ID: {scenario['id']}] {scenario['description']}")
            print(f"Status Code: Error")
            print(f"결과: ❌ 취약")
            print(f"이유: 요청 중 예외 발생: {e}")
            continue

        actual_code = response.status_code
        expected_codes = scenario.get("safe_status_codes", [])

        if actual_code in expected_codes:
            result = "✅ 안전"
            reason = "모든 조건 통과"
        else:
            result = "❌ 취약"
            reason = f"예상 코드 {expected_codes}, 실제 코드 {actual_code}"

        print("--------------------------------------------------")
        print(f"[Test ID: {scenario['id']}] {scenario['description']}")
        print(f"Status Code: {actual_code}")
        print(f"결과: {result}")
        print(f"이유: {reason}")

if __name__ == "__main__":
    main()

# 제외된 OWASP Top 10 시나리오 및 이유
# A2_CryptographicFailures: 비밀번호 저장 및 암호화 기능이 구현되어 있지 않음
# A4_InsecureDesign: 관리자 비활성화 기능이 없음
# A6_VulnerableComponents: 외부 컴포넌트 버전 정보나 bcrypt 사용 기능 없음
# A7_IdentificationAndAuthenticationFailures: 로그인 기능이 없음
# A8_SoftwareAndDataIntegrityFailures: 데이터 무결성 확인을 위한 엔드포인트가 없음
# A9_SecurityLoggingMonitoring: 로깅 기능이 구현되어 있지 않음
# A10_ServerSideRequestForgery: 외부 요청을 하는 기능이 없음
