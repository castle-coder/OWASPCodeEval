import os
import subprocess
import time
import re
from collections import defaultdict
import requests
import io
from contextlib import redirect_stdout
import tempfile
import json


# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# prompt.txt 파일 읽기
def run_llm(target):
    prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), target, "prompt.txt")
    with open(prompt_path, "r", encoding="utf-8") as f:
        user_prompt = f.read()

    # 요청 payload
    payload = {
        "input": {
            "messages": [
                {
                    "role": "system",
                    "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "sampling_params": {
                "temperature": 0,
                "max_tokens": 4096
            }
        }
    }

    # 요청 헤더
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }

    # 저장 경로 설정
    save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), target)
    app_path = os.path.join(save_dir, "app.py")
    db_path = os.path.join(save_dir, "mock_db.sqlite3")
    test_path = os.path.join(save_dir, "security_test.py")

    # 기존 파일 제거
    os.makedirs(save_dir, exist_ok=True)
    if os.path.exists(app_path):
        os.remove(app_path)
    if os.path.exists(db_path):
        os.remove(db_path)

    # 1단계: Run 요청 보내기
    run_response = requests.post(RUN_URL, headers=headers, json=payload)
    if run_response.status_code != 200:
        print("❌ 실행 실패:", run_response.status_code, run_response.text)
        exit()

    job_id = run_response.json().get("id")

    # 2단계: 상태 확인 (비동기 완료 대기)
    while True:
        status_response = requests.get(f"{STATUS_URL_BASE}{job_id}", headers=headers)
        status_data = status_response.json()
        status = status_data.get("status")

        if status == "COMPLETED":
            try:
                # 마크다운 텍스트 추출 및 출력
                tokens = status_data["output"][0]["choices"][0]["tokens"]
                markdown_output = tokens[0] if tokens else ""
                
                # 코드 추출
                parsed_code = markdown_output[10:-3].strip()

                # app.py 저장
                with open(app_path, "w", encoding="utf-8") as f:
                    f.write(parsed_code)
                    
                ######################################################## bandit 검사
                with open(app_path, "r") as f:
                    original_code = f.read()

                # 2. Bandit 검사
                bandit_result = check_python_code_with_bandit(original_code)

                # 결과 출력
                print("✅ 코드 컴파일 가능 여부:", bandit_result["compile_ok"])
                if not bandit_result["compile_ok"]:
                    print("❌ 컴파일 에러:", bandit_result["compile_err"])

                print("\n🔍 Bandit 보안 분석 결과:")
                bandit_totals = defaultdict(int)
                bandit_issues = set()
                
                if bandit_result["bandit_ok"] is not None:
                    try:
                        bandit_json = json.loads(bandit_result["bandit_output"])
                        print("\n📊 _totals:")
                        totals = bandit_json["metrics"]["_totals"]
                        print(json.dumps(totals, indent=2, ensure_ascii=False))
                        
                        # totals 값 저장
                        for key, value in totals.items():
                            bandit_totals[key] = value
                        
                        print("\n⚠️ 발견된 이슈:")
                        for result in bandit_json["results"]:
                            issue_text = result['issue_text']
                            print(f"- {issue_text}")
                            bandit_issues.add(issue_text)
                    except json.JSONDecodeError:
                        print("JSON 파싱 오류:", bandit_result["bandit_output"])
                ######################################################################
                
                app_process = subprocess.Popen(["python3", "app.py"], cwd=save_dir, stdin=subprocess.DEVNULL)
                
                time.sleep(3)  # 서버 시작 대기
                
                # security_test.py가 존재하면 실행하고 결과 캡처
                test_output = ""
                if os.path.exists(test_path):
                    result = subprocess.run(["python3", test_path], 
                                         cwd=save_dir, 
                                         capture_output=True, 
                                         text=True)
                    test_output = result.stdout
                else:
                    print("⚠️ security_test.py 파일이 존재하지 않습니다.")
                
                app_process.terminate()
                app_process.wait()
                
                return test_output, bandit_totals, bandit_issues
                
            except Exception as e:
                print("오류:", e)
                return "", defaultdict(int), set()
            break
        elif status == "FAILED":
            print("❌ 작업 실패:", status_data)
            return "", defaultdict(int), set()
        else:
            time.sleep(1.5)



def check_python_code_with_bandit(code: str):
    with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as temp_file:
        temp_file.write(code)
        temp_file_path = temp_file.name

    try:
        compile(code, temp_file_path, 'exec')
        compile_ok = True
    except Exception as e:
        compile_ok = False
        compile_err = str(e)
    else:
        compile_err = None

    bandit_ok = None
    bandit_output = ""
    if compile_ok:
        try:
            result = subprocess.run(
                ['bandit', '-r', temp_file_path, '-f', 'json'],
                capture_output=True, text=True
            ) 
            bandit_output = result.stdout
            bandit_ok = (result.returncode == 0)
        except Exception as e:
            bandit_ok = False
            bandit_output = str(e)

    os.remove(temp_file_path)

    return {
        "compile_ok": compile_ok,
        "compile_err": compile_err,
        "bandit_ok": bandit_ok,
        "bandit_output": bandit_output
    }

def run_auto_script(subfolder):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    print(f"\n LLM 실행 중...\n→ {subfolder}\n")

    overall_safe = 0
    overall_vuln = 0
    result_by_category = defaultdict(lambda: {"safe": 0, "vuln": 0})
    bandit_totals = defaultdict(int)
    bandit_issues = set()

    current_test_id = None

    try:
        # run_llm 실행 및 결과 받기
        test_output, bandit_totals, bandit_issues = run_llm(subfolder)
        
        # 출력 결과 분석
        for line in test_output.split('\n'):
            print(line)  # 원본 출력도 보여주기

            # 현재 테스트 ID 추출
            match = re.search(r'\[Test ID:\s*(A\d+)', line)
            if match:
                current_test_id = match.group(1)

            # 안전/취약 결과 분류
            if "결과:" in line:
                if current_test_id:
                    if "안전" in line:
                        result_by_category[current_test_id]["safe"] += 1
                        overall_safe += 1
                    elif "취약" in line:
                        result_by_category[current_test_id]["vuln"] += 1
                        overall_vuln += 1

        return overall_safe, overall_vuln, result_by_category, bandit_totals, bandit_issues

    except Exception as e:
        print(f"실행 중 오류 발생: {e}")
        exit(1)

# 전체 결과 집계
total_safe = 0
total_vuln = 0
total_result_by_category = defaultdict(lambda: {"safe": 0, "vuln": 0})
total_bandit_totals = defaultdict(int)
total_bandit_issues = set()

folders = [
    "flask-sqlite/board_test",
    "flask-sqlite/calendar_test",
    "flask-sqlite/chat_test",
    "flask-sqlite/comment_test",
    "flask-sqlite/EmailAuth_test",
    "flask-sqlite/file_test",
    "flask-sqlite/member_test",
    "flask-sqlite/notification_test",
    "flask-sqlite/quiz_test",
    "flask-sqlite/search_test",
    "flask-sqlite/shop_test"
]

for folder in folders:
    safe, vuln, result_by_cat, bandit_totals, bandit_issues = run_auto_script(folder)
    total_safe += safe
    total_vuln += vuln
    
    # Bandit 결과 누적
    for key, value in bandit_totals.items():
        total_bandit_totals[key] += value
    total_bandit_issues.update(bandit_issues)
    
    for category, counts in result_by_cat.items():
        total_result_by_category[category]["safe"] += counts["safe"]
        total_result_by_category[category]["vuln"] += counts["vuln"]
    time.sleep(3)

# 최종 출력
print("\n최종 테스트 결과 요약:")
print(f"✅ 전체 안전한 테스트 수: {total_safe}")
print(f"❌ 전체 취약한 테스트 수: {total_vuln}")

print("\n📊 A1 ~ A10 항목별 결과:")
for i in range(1, 11):
    key = f"A{i}"
    counts = total_result_by_category.get(key, {"safe": 0, "vuln": 0})
    print(f"  {key} - 안전: {counts['safe']}건 / 취약: {counts['vuln']}건")

print("\n🔍 Bandit 보안 분석 결과:")
print("\n📊 누적 _totals:")
print(json.dumps(dict(total_bandit_totals), indent=2, ensure_ascii=False))

print("\n⚠️ 발견된 모든 이슈:")
for issue in total_bandit_issues:
    print(f"- {issue}")
