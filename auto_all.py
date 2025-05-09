import os
import subprocess
import time

def run_auto_script(subfolder):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    target_script = os.path.join(base_dir, "flask-sqlite", subfolder, "auto.py")

    if not os.path.exists(target_script):
        print(f"실행할 파일이 존재하지 않습니다: {target_script}")
        exit(1)

    print(f"\n auto.py 실행 중...\n→ {target_script}\n")

    safe_count = 0
    vuln_count = 0

    process = subprocess.Popen(
        ["python3", target_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # 실시간 출력
    for line in process.stdout:
        print(line, end='')  # 한 줄씩 출력
        if "안전" in line:
            safe_count += 1
        if "취약" in line:
            vuln_count += 1

    process.wait()
    return safe_count, vuln_count



# 전체 결과 집계
total_safe = 0
total_vuln = 0

for folder in [ "EmailAuth_test", "chat_test", "shop_test"]:
# for folder in ["board_test", "file_test", "member_test", "notification_test", "calendar_test"]:
    safe, vuln = run_auto_script(folder)
    total_safe += safe
    total_vuln += vuln
    time.sleep(5)  # 각 테스트 사이에 잠시 대기

print("\n최종 테스트 결과 요약:")
print(f"   안전한 테스트 수: {total_safe}")
print(f"   취약한 테스트 수: {total_vuln}")