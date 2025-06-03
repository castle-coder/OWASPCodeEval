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
import shutil
import logging
import traceback
from datetime import datetime

# requests 라이브러리의 로깅 레벨 설정
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

# 로깅 설정
def setup_logging():
    # 로그 디렉토리 생성
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # 현재 시간을 파일명에 포함
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"auto_flask_{timestamp}.log")
    
    # 로깅 설정
    logging.basicConfig(
        level=logging.DEBUG,  # DEBUG 레벨로 변경하여 모든 로그 기록
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()  # 콘솔 출력도 유지
        ]
    )
    
    return log_file

# RunPod API 설정
RUN_URL = "https://api.runpod.ai/v2/sggrcbr26xtyx4/run"
STATUS_URL_BASE = "https://api.runpod.ai/v2/sggrcbr26xtyx4/status/"
API_KEY = "rpa_JXPAS3TMYRYAT0H0ZVXSGENZ3BIET1EMOBKUCJMP0yngu7"

# 최대 재시도 횟수 설정
MAX_RETRIES = 5

# prompt.txt 파일 읽기
def run_llm(target, retry_count=0):
    try:
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
                    "temperature": 0.4,
                    "max_tokens": 8192
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
        uploads_path = os.path.join(save_dir, "uploads")

        # 기존 파일 제거
        try:
            os.makedirs(save_dir, exist_ok=True)
            if os.path.exists(app_path):
                os.remove(app_path)
            if os.path.exists(db_path):
                os.remove(db_path)
            if os.path.exists(uploads_path):
                shutil.rmtree(uploads_path)
        except Exception as e:
            logging.error(f"파일 제거 중 오류 발생: {str(e)}")
            logging.error(traceback.format_exc())

        # 1단계: Run 요청 보내기
        try:
            run_response = requests.post(RUN_URL, headers=headers, json=payload)
            run_response.raise_for_status()  # HTTP 에러 체크
        except requests.exceptions.RequestException as e:
            logging.error(f"API 요청 실패: {str(e)}")
            logging.error(f"응답 내용: {run_response.text if 'run_response' in locals() else 'No response'}")
            return "", defaultdict(int), set()

        job_id = run_response.json().get("id")
        if not job_id:
            logging.error("Job ID를 받지 못했습니다.")
            logging.error(f"응답 내용: {run_response.text}")
            return "", defaultdict(int), set()

        # 2단계: 상태 확인 (비동기 완료 대기)
        while True:
            try:
                status_response = requests.get(f"{STATUS_URL_BASE}{job_id}", headers=headers)
                status_response.raise_for_status()
                status_data = status_response.json()
                status = status_data.get("status")

                if status == "COMPLETED":
                    try:
                        # 마크다운 텍스트 추출 및 출력
                        tokens = status_data["output"][0]["choices"][0]["tokens"]
                        markdown_output = tokens[0] if tokens else ""
                        
                        if not markdown_output:
                            logging.error("빈 응답을 받았습니다.")
                            return "", defaultdict(int), set()
                        
                        # 코드 추출
                        parsed_code = markdown_output[10:-3].strip()

                        # app.py 저장
                        try:
                            with open(app_path, "w", encoding="utf-8") as f:
                                f.write(parsed_code)
                        except Exception as e:
                            logging.error(f"app.py 저장 중 오류 발생: {str(e)}")
                            logging.error(traceback.format_exc())
                            return "", defaultdict(int), set()
                            
                        ######################################################## bandit 검사
                        try:
                            with open(app_path, "r") as f:
                                original_code = f.read()

                            # 2. Bandit 검사
                            bandit_result = check_python_code_with_bandit(original_code)

                            # 결과 출력
                            logging.info(f"✅ 코드 컴파일 가능 여부: {bandit_result['compile_ok']}")
                            if not bandit_result["compile_ok"]:
                                logging.error(f"❌ 컴파일 에러: {bandit_result['compile_err']}")

                            logging.info("\n🔍 Bandit 보안 분석 결과:")
                            bandit_totals = defaultdict(int)
                            bandit_issues = set()
                            
                            if bandit_result["bandit_ok"] is not None:
                                try:
                                    bandit_json = json.loads(bandit_result["bandit_output"])
                                    logging.info("\n📊 _totals:")
                                    totals = bandit_json["metrics"]["_totals"]
                                    logging.info(json.dumps(totals, indent=2, ensure_ascii=False))
                                    
                                    # totals 값 저장
                                    for key, value in totals.items():
                                        bandit_totals[key] = value
                                    
                                    logging.info("\n⚠️ 발견된 이슈:")
                                    for result in bandit_json["results"]:
                                        issue_text = result['issue_text']
                                        logging.info(f"- {issue_text}")
                                        bandit_issues.add(issue_text)
                                except json.JSONDecodeError as e:
                                    logging.error(f"JSON 파싱 오류: {str(e)}")
                                    logging.error(f"원본 데이터: {bandit_result['bandit_output']}")
                        except Exception as e:
                            logging.error(f"Bandit 검사 중 오류 발생: {str(e)}")
                            logging.error(traceback.format_exc())
                        ######################################################################
                        
                        try:
                            # app.py 실행 및 오류 체크
                            app_process = subprocess.Popen(["python3", "app.py"], 
                                                        cwd=save_dir, 
                                                        stdin=subprocess.DEVNULL,
                                                        stdout=subprocess.PIPE,
                                                        stderr=subprocess.PIPE)
                            
                            time.sleep(3)  # 서버 시작 대기
                            
                            # 프로세스 상태 확인
                            if app_process.poll() is not None:
                                # 프로세스가 종료된 경우 (오류 발생)
                                _, stderr = app_process.communicate()
                                error_message = stderr.decode('utf-8')
                                logging.error(f"app.py 실행 중 오류 발생:\n{error_message}")
                                
                                # 재시도 횟수 확인
                                if retry_count < MAX_RETRIES:
                                    logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                                    app_process.terminate()
                                    app_process.wait()
                                    return run_llm(target, retry_count + 1)
                                else:
                                    logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                                    return "", defaultdict(int), set()
                            
                            # security_test.py가 존재하면 실행하고 결과 캡처
                            test_output = ""
                            if os.path.exists(test_path):
                                result = subprocess.run(["python3", test_path], 
                                                     cwd=save_dir, 
                                                     capture_output=True, 
                                                     text=True)
                                test_output = result.stdout
                                if result.stderr:
                                    logging.error(f"테스트 실행 중 에러 발생:\n{result.stderr}")
                                
                                # 테스트가 정상적으로 종료되지 않은 경우 (returncode가 0이 아닌 경우)
                                if result.returncode != 0:
                                    logging.error(f"테스트가 비정상 종료되었습니다. (returncode: {result.returncode})")
                                    if retry_count < MAX_RETRIES:
                                        logging.info(f"테스트 비정상 종료로 인한 LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                                        app_process.terminate()
                                        app_process.wait()
                                        return run_llm(target, retry_count + 1)
                                    else:
                                        logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                                        return "", defaultdict(int), set()
                            else:
                                logging.warning("⚠️ security_test.py 파일이 존재하지 않습니다.")
                            
                            app_process.terminate()
                            app_process.wait()
                            
                            return test_output, bandit_totals, bandit_issues
                        except subprocess.SubprocessError as e:
                            logging.error(f"프로세스 실행 중 오류 발생: {str(e)}")
                            logging.error(traceback.format_exc())
                            
                            # 재시도 횟수 확인
                            if retry_count < MAX_RETRIES:
                                logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                                return run_llm(target, retry_count + 1)
                            else:
                                logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                                return "", defaultdict(int), set()
                            
                    except Exception as e:
                        logging.error(f"처리 중 오류 발생: {str(e)}")
                        logging.error(traceback.format_exc())
                        
                        # 재시도 횟수 확인
                        if retry_count < MAX_RETRIES:
                            logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                            return run_llm(target, retry_count + 1)
                        else:
                            logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                            return "", defaultdict(int), set()
                    break
                elif status == "FAILED":
                    logging.error(f"❌ 작업 실패: {status_data}")
                    
                    # 재시도 횟수 확인
                    if retry_count < MAX_RETRIES:
                        logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                        return run_llm(target, retry_count + 1)
                    else:
                        logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                        return "", defaultdict(int), set()
                else:
                    time.sleep(1.5)
            except requests.exceptions.RequestException as e:
                logging.error(f"상태 확인 중 오류 발생: {str(e)}")
                logging.error(traceback.format_exc())
                
                # 재시도 횟수 확인
                if retry_count < MAX_RETRIES:
                    logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
                    return run_llm(target, retry_count + 1)
                else:
                    logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
                    return "", defaultdict(int), set()
    except Exception as e:
        logging.error(f"예상치 못한 오류 발생: {str(e)}")
        logging.error(traceback.format_exc())
        
        # 재시도 횟수 확인
        if retry_count < MAX_RETRIES:
            logging.info(f"LLM 재실행 시도 ({retry_count + 1}/{MAX_RETRIES})")
            return run_llm(target, retry_count + 1)
        else:
            logging.error(f"최대 재시도 횟수({MAX_RETRIES})를 초과했습니다.")
            return "", defaultdict(int), set()

def check_python_code_with_bandit(code: str):
    try:
        with tempfile.NamedTemporaryFile('w', suffix='.py', delete=False) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name

        try:
            compile(code, temp_file_path, 'exec')
            compile_ok = True
        except Exception as e:
            compile_ok = False
            compile_err = str(e)
            logging.error(f"코드 컴파일 실패: {compile_err}")
        else:
            compile_err = None

        bandit_ok = None
        bandit_output = ""
        if compile_ok:
            try:
                result = subprocess.run(
                    ['bandit', '-r', temp_file_path, '-f', 'json'],
                    capture_output=True, 
                    text=True
                ) 
                bandit_output = result.stdout
                bandit_ok = (result.returncode == 0)
                if result.stderr:
                    logging.error(f"Bandit 실행 중 에러 발생:\n{result.stderr}")
            except Exception as e:
                bandit_ok = False
                bandit_output = str(e)
                logging.error(f"Bandit 실행 실패: {str(e)}")
                logging.error(traceback.format_exc())

        os.remove(temp_file_path)

        return {
            "compile_ok": compile_ok,
            "compile_err": compile_err,
            "bandit_ok": bandit_ok,
            "bandit_output": bandit_output
        }
    except Exception as e:
        logging.error(f"Bandit 검사 중 예상치 못한 오류 발생: {str(e)}")
        logging.error(traceback.format_exc())
        return {
            "compile_ok": False,
            "compile_err": str(e),
            "bandit_ok": False,
            "bandit_output": str(e)
        }

def run_auto_script(subfolder):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    logging.info(f"\n LLM 실행 중...\n→ {subfolder}\n")

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
            logging.info(line)  # 원본 출력도 보여주기

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
        logging.error(f"실행 중 오류 발생: {e}")
        exit(1)

# 메인 실행 부분
if __name__ == "__main__":
    # 로깅 설정
    log_file = setup_logging()
    logging.info(f"로그 파일이 생성되었습니다: {log_file}")
    
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
    logging.info("\n최종 테스트 결과 요약:")
    logging.info(f"✅ 전체 안전한 테스트 수: {total_safe}")
    logging.info(f"❌ 전체 취약한 테스트 수: {total_vuln}")

    logging.info("\n📊 A1 ~ A10 항목별 결과:")
    for i in range(1, 11):
        key = f"A{i}"
        counts = total_result_by_category.get(key, {"safe": 0, "vuln": 0})
        logging.info(f"  {key} - 안전: {counts['safe']}건 / 취약: {counts['vuln']}건")

    logging.info("\n🔍 Bandit 보안 분석 결과:")
    logging.info("\n📊 누적 _totals:")
    logging.info(json.dumps(dict(total_bandit_totals), indent=2, ensure_ascii=False))

    logging.info("\n⚠️ 발견된 모든 이슈:")
    for issue in total_bandit_issues:
        logging.info(f"- {issue}")
        
    logging.info(f"\n로그 파일이 저장되었습니다: {log_file}")
