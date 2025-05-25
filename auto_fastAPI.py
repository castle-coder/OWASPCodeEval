import os
import subprocess
import time
import re
from collections import defaultdict

def run_auto_script(subfolder):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(base_dir, "FastAPI-mysql", subfolder, "auto.py")

    if not os.path.exists(target_script):
        print(f"실행할 파일이 존재하지 않습니다: {target_script}")
        exit(1)

    print(f"\n auto.py 실행 중...\n→ {target_script}\n")

    overall_safe = 0
    overall_vuln = 0
    result_by_category = defaultdict(lambda: {"safe": 0, "vuln": 0})

    current_test_id = None

    process = subprocess.Popen(
        ["python3", target_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        print(line, end='')

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

    process.wait()
    return overall_safe, overall_vuln, result_by_category

# 전체 결과 집계
total_safe = 0
total_vuln = 0
total_result_by_category = defaultdict(lambda: {"safe": 0, "vuln": 0})

# folders = ["board_test", "calendar_test", "chat_test", "comment_test", "EmailAuth_test", "file_test", "member_test", "notification_test", "quiz_test", "search_test", "shop_test"]

folders = ["calendar_test"]

for folder in folders:
    safe, vuln, result_by_cat = run_auto_script(folder)
    total_safe += safe
    total_vuln += vuln
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
