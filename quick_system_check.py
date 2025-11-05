#!/usr/bin/env python
"""
조직 효과성 리포트 시스템 - 빠른 시스템 체크
Quick System Health Check
"""

import os
import sys
import pandas as pd
from datetime import datetime

# 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_pass(name, detail=""):
    print(f"{GREEN}✓{RESET} {name} {detail}")
    return True

def check_fail(name, error):
    print(f"{RED}✗{RESET} {name}: {error}")
    return False

def check_warn(name, warning):
    print(f"{YELLOW}⚠{RESET} {name}: {warning}")
    return True

print(f"\n{BOLD}조직 효과성 리포트 시스템 - 빠른 시스템 체크{RESET}")
print(f"{BOLD}{'='*50}{RESET}\n")

passed = 0
failed = 0
warnings = 0

# 1. 핵심 파일 확인
print(f"{BLUE}1. 핵심 파일 확인{RESET}")
core_files = {
    "streamlit_app.py": "메인 애플리케이션",
    "app.py": "Flask 서버",
    ".env": "환경 설정",
    "index_v2.csv": "인덱스 파일",
    "team_sample_data.csv": "샘플 데이터"
}

for file, desc in core_files.items():
    if os.path.exists(file):
        size = os.path.getsize(file)
        if check_pass(f"{desc} ({file})", f"[{size:,} bytes]"):
            passed += 1
    else:
        if check_fail(f"{desc} ({file})", "파일 없음"):
            failed += 1

# 2. 환경 변수 확인
print(f"\n{BLUE}2. 환경 변수 확인{RESET}")
from dotenv import load_dotenv
load_dotenv()

env_vars = {
    "GOOGLE_API_KEY": "Gemini API",
    "ADMIN_PASSWORD": "관리자 비밀번호",
    "SMTP_EMAIL": "이메일 주소",
    "SMTP_PASSWORD": "이메일 비밀번호"
}

for var, desc in env_vars.items():
    value = os.getenv(var)
    if value:
        # 민감한 정보 마스킹
        if "PASSWORD" in var or "KEY" in var:
            masked = value[:4] + "***" + value[-4:] if len(value) > 8 else "***"
            if check_pass(f"{desc}", f"[설정됨: {masked}]"):
                passed += 1
        else:
            if check_pass(f"{desc}", f"[{value}]"):
                passed += 1
    else:
        if check_warn(f"{desc}", "미설정"):
            warnings += 1

# 3. Python 패키지 확인
print(f"\n{BLUE}3. 필수 패키지 확인{RESET}")
packages = [
    ("streamlit", "Streamlit"),
    ("flask", "Flask"),
    ("pandas", "Pandas"),
    ("numpy", "NumPy"),
    ("google.generativeai", "Google AI")
]

for module, name in packages:
    try:
        __import__(module)
        if check_pass(f"{name}"):
            passed += 1
    except ImportError:
        if check_warn(f"{name}", "미설치"):
            warnings += 1

# 4. 데이터 검증
print(f"\n{BLUE}4. 데이터 검증{RESET}")
try:
    # 인덱스 파일
    index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')
    if check_pass(f"인덱스 파일", f"[{len(index_df)}개 항목]"):
        passed += 1

    # 샘플 데이터
    if os.path.exists("team_sample_data.csv"):
        sample_df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
        teams = sample_df['DEPT'].value_counts()
        if check_pass(f"샘플 데이터", f"[{len(sample_df)}명, {len(teams)}개 팀]"):
            passed += 1
except Exception as e:
    if check_fail("데이터 파일", str(e)):
        failed += 1

# 5. 기본 기능 테스트
print(f"\n{BLUE}5. 기본 기능 테스트{RESET}")
try:
    import streamlit_app

    # 데이터 그룹핑 테스트
    if os.path.exists("team_sample_data.csv"):
        df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
        grouped = streamlit_app.group_data_by_unit(df, "팀별", "DEPT")
        if len(grouped) > 1:
            if check_pass(f"팀별 그룹핑", f"[{len(grouped)}개 팀 생성]"):
                passed += 1
        else:
            if check_warn(f"팀별 그룹핑", f"단일 그룹만 생성"):
                warnings += 1

    # 리포트 생성 테스트
    try:
        report = streamlit_app.build_report(df.head(10), index_df)
        if report and 'ipo_scores' in report:
            if check_pass(f"리포트 생성", "[성공]"):
                passed += 1
        else:
            if check_fail(f"리포트 생성", "불완전한 리포트"):
                failed += 1
    except Exception as e:
        if check_fail(f"리포트 생성", str(e)[:50]):
            failed += 1

except ImportError as e:
    if check_fail("모듈 임포트", str(e)):
        failed += 1

# 6. 보안 체크
print(f"\n{BLUE}6. 보안 체크{RESET}")
admin_pw = os.getenv("ADMIN_PASSWORD", "")
if admin_pw == "admin123":
    if check_warn("관리자 비밀번호", "기본 비밀번호 사용 중"):
        warnings += 1
elif len(admin_pw) < 8:
    if check_warn("관리자 비밀번호", f"너무 짧음 ({len(admin_pw)}자)"):
        warnings += 1
else:
    if check_pass("관리자 비밀번호", "[안전]"):
        passed += 1

# 결과 요약
print(f"\n{BOLD}{'='*50}{RESET}")
print(f"{BOLD}테스트 결과 요약{RESET}")
print(f"{BOLD}{'='*50}{RESET}\n")

total = passed + failed + warnings
success_rate = (passed / total * 100) if total > 0 else 0

print(f"전체: {total} | ", end="")
print(f"{GREEN}통과: {passed}{RESET} | ", end="")
print(f"{YELLOW}경고: {warnings}{RESET} | ", end="")
print(f"{RED}실패: {failed}{RESET}")
print(f"\n성공률: {success_rate:.1f}%")

if failed == 0:
    print(f"\n{GREEN}{BOLD}✓ 시스템이 정상적으로 작동할 준비가 되었습니다!{RESET}")
    print(f"\n실행 방법:")
    print(f"  python -m streamlit run streamlit_app.py --server.port 8502")
    print(f"\n접속 주소: http://localhost:8502")
else:
    print(f"\n{RED}{BOLD}✗ {failed}개 문제를 해결해야 합니다.{RESET}")

if warnings > 0:
    print(f"\n{YELLOW}권장사항:{RESET}")
    if "기본 비밀번호" in str(locals()):
        print("  - 관리자 비밀번호를 변경하세요")
    if warnings > 2:
        print("  - 환경 변수를 설정하세요 (.env 파일)")

print(f"\n테스트 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")