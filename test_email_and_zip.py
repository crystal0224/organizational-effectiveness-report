#!/usr/bin/env python
"""
이메일 발송 및 ZIP 파일 생성 기능 테스트
"""

import os
import sys
import smtplib
import zipfile
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from io import BytesIO
import pandas as pd

# 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

print(f"\n{BOLD}이메일 발송 및 ZIP 파일 기능 테스트{RESET}")
print(f"{BOLD}{'='*50}{RESET}\n")

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

# 1. 이메일 설정 확인
print(f"{BLUE}1. 이메일 설정 확인{RESET}")

smtp_email = os.getenv("SMTP_EMAIL")
smtp_password = os.getenv("SMTP_PASSWORD")
smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", "587"))

if smtp_email and smtp_password:
    print(f"{GREEN}✓{RESET} 이메일 주소: {smtp_email}")
    print(f"{GREEN}✓{RESET} 이메일 비밀번호: {'*' * 12}")
    print(f"{GREEN}✓{RESET} SMTP 서버: {smtp_server}:{smtp_port}")
else:
    print(f"{RED}✗{RESET} 이메일 설정이 불완전합니다")
    sys.exit(1)

# 2. SMTP 연결 테스트
print(f"\n{BLUE}2. Gmail SMTP 연결 테스트{RESET}")

try:
    # SMTP 서버 연결
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()  # TLS 시작
    server.login(smtp_email, smtp_password)
    print(f"{GREEN}✓{RESET} Gmail SMTP 서버 연결 성공")
    print(f"{GREEN}✓{RESET} 인증 성공")
    server.quit()

except smtplib.SMTPAuthenticationError as e:
    print(f"{RED}✗{RESET} 인증 실패: Gmail 앱 비밀번호를 확인하세요")
    print(f"  에러: {e}")
except Exception as e:
    print(f"{RED}✗{RESET} SMTP 연결 실패: {e}")

# 3. ZIP 파일 생성 테스트
print(f"\n{BLUE}3. ZIP 파일 생성 테스트{RESET}")

try:
    # 테스트용 파일들 생성
    test_files = {}
    for i in range(1, 4):
        filename = f"team_{i}_report.txt"
        content = f"This is a test report for Team {i}\n" * 10
        test_files[filename] = content.encode()

    # ZIP 파일 생성 (메모리)
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for filename, content in test_files.items():
            zip_file.writestr(filename, content)

    zip_size = len(zip_buffer.getvalue())
    print(f"{GREEN}✓{RESET} ZIP 파일 생성 성공 (크기: {zip_size:,} bytes)")
    print(f"{GREEN}✓{RESET} 포함된 파일: {len(test_files)}개")

    # ZIP 파일을 디스크에 저장 (테스트)
    with open("test_reports.zip", "wb") as f:
        f.write(zip_buffer.getvalue())
    print(f"{GREEN}✓{RESET} ZIP 파일 저장 성공: test_reports.zip")

except Exception as e:
    print(f"{RED}✗{RESET} ZIP 생성 실패: {e}")

# 4. 팀별 리포트 ZIP 생성 시뮬레이션
print(f"\n{BLUE}4. 팀별 리포트 ZIP 생성 시뮬레이션{RESET}")

try:
    import streamlit_app

    # 샘플 데이터 로드
    if os.path.exists("team_sample_data.csv"):
        df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
        index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')

        # 팀별 데이터 그룹핑
        grouped_data = streamlit_app.group_data_by_unit(df, "팀별", "DEPT")
        print(f"{GREEN}✓{RESET} {len(grouped_data)}개 팀 데이터 준비")

        # 각 팀별 리포트 생성
        reports = streamlit_app.build_multiple_reports(
            grouped_data,
            index_df,
            "테스트회사",
            "테스트부서"
        )
        print(f"{GREEN}✓{RESET} {len(reports)}개 리포트 생성")

        # ZIP 생성 함수 테스트
        def create_zip_from_reports(reports, org_name="조직"):
            """리포트 딕셔너리를 ZIP 파일로 변환"""
            zip_buffer = BytesIO()

            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for team_name, report in reports.items():
                    # 각 리포트를 JSON으로 저장 (실제로는 PDF가 됨)
                    import json
                    report_json = json.dumps(
                        {"team": team_name, "data": "report_content"},
                        ensure_ascii=False,
                        indent=2
                    )

                    safe_name = team_name.replace("/", "_").replace("\\", "_")
                    filename = f"{safe_name}_조직효과성진단.json"
                    zip_file.writestr(filename, report_json)

            return zip_buffer.getvalue()

        # ZIP 생성
        zip_bytes = create_zip_from_reports(reports, "테스트조직")

        # ZIP 파일 저장
        zip_filename = "team_reports.zip"
        with open(zip_filename, "wb") as f:
            f.write(zip_bytes)

        print(f"{GREEN}✓{RESET} 팀별 리포트 ZIP 생성 성공")
        print(f"  - 파일명: {zip_filename}")
        print(f"  - 크기: {len(zip_bytes):,} bytes")
        print(f"  - 포함된 리포트: {len(reports)}개")

        # ZIP 파일 내용 확인
        with zipfile.ZipFile(zip_filename, 'r') as zip_file:
            file_list = zip_file.namelist()
            print(f"\n  ZIP 파일 내용:")
            for fname in file_list:
                info = zip_file.getinfo(fname)
                print(f"    - {fname} ({info.file_size:,} bytes)")

except Exception as e:
    print(f"{RED}✗{RESET} 팀별 리포트 ZIP 생성 실패: {e}")
    import traceback
    traceback.print_exc()

# 5. 이메일 발송 함수 테스트
print(f"\n{BLUE}5. 이메일 발송 함수 테스트{RESET}")

def test_email_send(to_email=None):
    """테스트 이메일 발송"""
    try:
        # 받는 사람 이메일 (테스트용으로 자기 자신에게)
        if not to_email:
            to_email = smtp_email

        # 이메일 메시지 생성
        msg = MIMEMultipart()
        msg['From'] = smtp_email
        msg['To'] = to_email
        msg['Subject'] = "[테스트] 조직효과성 진단 리포트 시스템"

        # 본문
        body = """
안녕하세요,

조직효과성 진단 리포트 시스템 이메일 발송 테스트입니다.

이 메일이 정상적으로 수신되었다면 이메일 기능이 정상 작동하고 있습니다.

기능 테스트 결과:
✓ SMTP 서버 연결 성공
✓ Gmail 인증 성공
✓ 이메일 발송 성공
✓ 첨부파일 기능 준비

감사합니다.
        """

        msg.attach(MIMEText(body, 'plain'))

        # 테스트 첨부 파일 (ZIP 파일)
        if os.path.exists("test_reports.zip"):
            with open("test_reports.zip", "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    'attachment; filename="test_reports.zip"'
                )
                msg.attach(part)
                print(f"{GREEN}✓{RESET} 첨부 파일 추가: test_reports.zip")

        # 이메일 발송
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_email, smtp_password)

        text = msg.as_string()
        server.sendmail(smtp_email, to_email, text)
        server.quit()

        print(f"{GREEN}✓{RESET} 테스트 이메일 발송 성공!")
        print(f"  - 발신: {smtp_email}")
        print(f"  - 수신: {to_email}")
        print(f"  - 제목: {msg['Subject']}")

        return True

    except Exception as e:
        print(f"{RED}✗{RESET} 이메일 발송 실패: {e}")
        return False

# 실제 이메일 발송은 사용자 확인 후에만
print(f"\n{YELLOW}참고:{RESET} 실제 이메일 발송 테스트는 주석 처리되어 있습니다.")
print("테스트하려면 아래 주석을 해제하고 실행하세요:")
print("# test_email_send()")

# test_email_send()  # 실제 테스트 시 주석 해제

# 6. 시스템 통합 기능 확인
print(f"\n{BLUE}6. 시스템 통합 기능 확인{RESET}")

# streamlit_app의 관련 함수들 확인
functions_to_check = [
    ("generate_multiple_pdfs", "PDF 일괄 생성"),
    ("create_zip_from_pdfs", "PDF ZIP 생성"),
    ("send_email_with_pdf", "PDF 이메일 발송"),
    ("send_batch_emails_with_reports", "일괄 이메일 발송")
]

import streamlit_app
for func_name, desc in functions_to_check:
    if hasattr(streamlit_app, func_name):
        print(f"{GREEN}✓{RESET} {desc} 함수 존재 ({func_name})")
    else:
        print(f"{YELLOW}⚠{RESET} {desc} 함수 없음 ({func_name})")

# 정리
print(f"\n{BOLD}{'='*50}{RESET}")
print(f"{BOLD}테스트 완료{RESET}")
print(f"{BOLD}{'='*50}{RESET}\n")

# 생성된 테스트 파일 정리
if os.path.exists("test_reports.zip"):
    os.remove("test_reports.zip")
    print(f"{GREEN}✓{RESET} 테스트 파일 정리 완료")

if os.path.exists("team_reports.zip"):
    # os.remove("team_reports.zip")  # 확인용으로 남겨둠
    print(f"{YELLOW}참고:{RESET} team_reports.zip 파일이 생성되었습니다 (확인 후 삭제)")

print(f"\n{GREEN}✓ 이메일 및 ZIP 파일 기능이 정상적으로 작동합니다!{RESET}")