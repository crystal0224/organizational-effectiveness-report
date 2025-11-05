#!/usr/bin/env python
"""
조직 효과성 리포트 시스템 - 포괄적 테스트 스위트
Senior Engineer Testing Framework
"""

import os
import sys
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import traceback
from typing import Dict, List, Tuple, Any

# 테스트 결과 색상 코드
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class TestResult:
    """테스트 결과 관리 클래스"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.errors = []
        self.warnings_list = []
        self.test_details = []

    def add_pass(self, test_name: str, details: str = ""):
        self.passed += 1
        self.test_details.append({
            'status': 'PASS',
            'test': test_name,
            'details': details
        })
        print(f"{GREEN}✓{RESET} {test_name}")

    def add_fail(self, test_name: str, error: str):
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
        self.test_details.append({
            'status': 'FAIL',
            'test': test_name,
            'error': error
        })
        print(f"{RED}✗{RESET} {test_name}")
        print(f"  {RED}Error: {error}{RESET}")

    def add_warning(self, test_name: str, warning: str):
        self.warnings += 1
        self.warnings_list.append(f"{test_name}: {warning}")
        self.test_details.append({
            'status': 'WARN',
            'test': test_name,
            'warning': warning
        })
        print(f"{YELLOW}⚠{RESET} {test_name}")
        print(f"  {YELLOW}Warning: {warning}{RESET}")


class ComprehensiveTestSuite:
    """포괄적 테스트 스위트"""

    def __init__(self):
        self.results = TestResult()
        self.test_data_path = Path("test_data")
        self.test_data_path.mkdir(exist_ok=True)

    def run_all_tests(self):
        """모든 테스트 실행"""
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}조직 효과성 리포트 시스템 - 포괄적 테스트{RESET}")
        print(f"{BOLD}{'='*60}{RESET}\n")

        test_categories = [
            ("1. 환경 설정 및 의존성", self.test_environment),
            ("2. 데이터 검증", self.test_data_validation),
            ("3. 리포트 생성 기능", self.test_report_generation),
            ("4. 팀별 분석 기능", self.test_team_analysis),
            ("5. AI 분석 기능", self.test_ai_features),
            ("6. PDF 생성 및 내보내기", self.test_pdf_generation),
            ("7. 이메일 기능", self.test_email_functionality),
            ("8. 관리자 기능", self.test_admin_features),
            ("9. 성능 테스트", self.test_performance),
            ("10. 엣지 케이스 및 오류 처리", self.test_edge_cases)
        ]

        for category_name, test_func in test_categories:
            print(f"\n{BLUE}{BOLD}{category_name}{RESET}")
            print("-" * 40)
            try:
                test_func()
            except Exception as e:
                self.results.add_fail(category_name, f"카테고리 실행 실패: {str(e)}")
                traceback.print_exc()

        self.print_summary()
        self.generate_test_report()

    def test_environment(self):
        """환경 설정 및 의존성 테스트"""

        # .env 파일 존재 확인
        if os.path.exists(".env"):
            self.results.add_pass(".env 파일 존재")

            # 필수 환경 변수 확인
            from dotenv import load_dotenv
            load_dotenv()

            required_vars = [
                ("GOOGLE_API_KEY", "Gemini API 키"),
                ("ADMIN_PASSWORD", "관리자 비밀번호"),
                ("SMTP_EMAIL", "이메일 주소"),
                ("SMTP_PASSWORD", "이메일 비밀번호")
            ]

            for var, desc in required_vars:
                if os.getenv(var):
                    self.results.add_pass(f"{desc} 설정됨")
                else:
                    self.results.add_warning(f"{desc} 미설정", f"{var} 환경변수가 설정되지 않음")
        else:
            self.results.add_fail(".env 파일", "파일이 존재하지 않음")

        # 필수 파일 확인
        required_files = [
            "streamlit_app.py",
            "app.py",
            "index_v2.csv",
            "templates/base.html"
        ]

        for file in required_files:
            if os.path.exists(file):
                self.results.add_pass(f"{file} 파일 존재")
            else:
                self.results.add_fail(f"{file} 파일", "파일이 존재하지 않음")

        # Python 패키지 확인
        try:
            import streamlit
            self.results.add_pass("Streamlit 설치됨")
        except ImportError:
            self.results.add_fail("Streamlit", "패키지가 설치되지 않음")

        try:
            import flask
            self.results.add_pass("Flask 설치됨")
        except ImportError:
            self.results.add_fail("Flask", "패키지가 설치되지 않음")

        try:
            import google.generativeai
            self.results.add_pass("Google Generative AI 설치됨")
        except ImportError:
            self.results.add_warning("Google Generative AI", "패키지가 설치되지 않음 (AI 기능 제한)")

    def test_data_validation(self):
        """데이터 검증 테스트"""

        # 인덱스 파일 검증
        try:
            index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')
            self.results.add_pass("인덱스 파일 로드", f"{len(index_df)}개 항목")

            # 필수 컬럼 확인
            required_cols = ['code', 'text', 'dimension', 'category']
            missing_cols = [col for col in required_cols if col not in index_df.columns]

            if not missing_cols:
                self.results.add_pass("인덱스 필수 컬럼 확인")
            else:
                self.results.add_fail("인덱스 필수 컬럼", f"누락: {missing_cols}")

        except Exception as e:
            self.results.add_fail("인덱스 파일 로드", str(e))

        # 샘플 데이터 생성 및 검증
        try:
            # 샘플 데이터가 있는지 확인
            if os.path.exists("team_sample_data.csv"):
                sample_df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
                self.results.add_pass("샘플 데이터 로드", f"{len(sample_df)}개 응답")

                # 데이터 품질 검증
                null_count = sample_df.isnull().sum().sum()
                if null_count == 0:
                    self.results.add_pass("데이터 완전성 검증")
                else:
                    self.results.add_warning("데이터 완전성", f"{null_count}개 null 값 발견")

            else:
                # 샘플 데이터 생성
                os.system("python test_team_data.py")
                if os.path.exists("team_sample_data.csv"):
                    self.results.add_pass("샘플 데이터 생성")
                else:
                    self.results.add_fail("샘플 데이터 생성", "생성 실패")

        except Exception as e:
            self.results.add_fail("샘플 데이터 처리", str(e))

    def test_report_generation(self):
        """리포트 생성 기능 테스트"""

        try:
            # streamlit_app 모듈 임포트
            import streamlit_app

            # 샘플 데이터로 리포트 생성 테스트
            if os.path.exists("team_sample_data.csv"):
                df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
                index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')

                # 전체 조직 리포트 생성
                try:
                    report = streamlit_app.build_report(df, index_df)
                    if report and 'ipo_scores' in report:
                        self.results.add_pass("전체 조직 리포트 생성")
                    else:
                        self.results.add_fail("전체 조직 리포트", "리포트 구조 불완전")
                except Exception as e:
                    self.results.add_fail("전체 조직 리포트 생성", str(e))

            else:
                self.results.add_warning("리포트 생성 테스트", "샘플 데이터 없음")

        except ImportError as e:
            self.results.add_fail("streamlit_app 모듈", f"임포트 실패: {e}")

    def test_team_analysis(self):
        """팀별 분석 기능 테스트"""

        try:
            import streamlit_app

            if os.path.exists("team_sample_data.csv"):
                df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')

                # 팀별 그룹핑 테스트
                grouped_data = streamlit_app.group_data_by_unit(df, "팀별", "DEPT")

                if len(grouped_data) > 1:
                    self.results.add_pass("팀별 데이터 그룹핑", f"{len(grouped_data)}개 팀")

                    # 각 팀별 최소 인원 확인
                    for team_name, team_df in grouped_data.items():
                        if len(team_df) >= 3:
                            self.results.add_pass(f"{team_name} 팀 데이터", f"{len(team_df)}명")
                        else:
                            self.results.add_warning(f"{team_name} 팀", f"응답자 {len(team_df)}명 (최소 3명 미달)")
                else:
                    self.results.add_fail("팀별 그룹핑", f"단일 그룹만 생성됨: {list(grouped_data.keys())}")

                # 다중 리포트 생성 테스트
                index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')
                reports = streamlit_app.build_multiple_reports(grouped_data, index_df, "테스트회사", "테스트부서")

                if len(reports) == len(grouped_data):
                    self.results.add_pass("다중 리포트 생성", f"{len(reports)}개 리포트")
                else:
                    self.results.add_fail("다중 리포트 생성", f"예상: {len(grouped_data)}, 실제: {len(reports)}")

        except Exception as e:
            self.results.add_fail("팀별 분석", f"오류: {e}")

    def test_ai_features(self):
        """AI 분석 기능 테스트"""

        # API 키 확인
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            self.results.add_warning("AI 기능", "API 키가 설정되지 않음")
            return

        try:
            import google.generativeai as genai

            # API 연결 테스트
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')

            # 간단한 테스트 프롬프트
            response = model.generate_content("테스트: 1+1은?")
            if response.text:
                self.results.add_pass("Gemini API 연결")
            else:
                self.results.add_fail("Gemini API", "응답 없음")

        except Exception as e:
            self.results.add_fail("AI API 테스트", str(e))

    def test_pdf_generation(self):
        """PDF 생성 테스트"""

        try:
            # weasyprint 확인
            try:
                import weasyprint
                self.results.add_pass("WeasyPrint 설치됨")
            except ImportError:
                self.results.add_warning("WeasyPrint", "PDF 생성 라이브러리 미설치")
                return

            # HTML to PDF 변환 테스트
            test_html = """
            <html>
                <head><title>Test PDF</title></head>
                <body><h1>테스트 PDF</h1></body>
            </html>
            """

            test_pdf_path = self.test_data_path / "test.pdf"

            try:
                from weasyprint import HTML
                HTML(string=test_html).write_pdf(test_pdf_path)

                if test_pdf_path.exists():
                    self.results.add_pass("PDF 생성 테스트")
                    test_pdf_path.unlink()  # 테스트 파일 삭제
                else:
                    self.results.add_fail("PDF 생성", "파일이 생성되지 않음")
            except Exception as e:
                self.results.add_fail("PDF 생성", str(e))

        except Exception as e:
            self.results.add_fail("PDF 테스트", str(e))

    def test_email_functionality(self):
        """이메일 기능 테스트"""

        # SMTP 설정 확인
        smtp_email = os.getenv("SMTP_EMAIL")
        smtp_password = os.getenv("SMTP_PASSWORD")

        if not smtp_email or not smtp_password:
            self.results.add_warning("이메일 설정", "SMTP 인증 정보 미설정")
            return

        # 이메일 형식 검증
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        if re.match(email_pattern, smtp_email):
            self.results.add_pass("이메일 주소 형식")
        else:
            self.results.add_fail("이메일 주소 형식", f"잘못된 형식: {smtp_email}")

        # Gmail 앱 비밀번호 형식 확인 (16자)
        if len(smtp_password) == 16:
            self.results.add_pass("Gmail 앱 비밀번호 형식")
        else:
            self.results.add_warning("Gmail 앱 비밀번호", f"길이가 16자가 아님: {len(smtp_password)}자")

    def test_admin_features(self):
        """관리자 기능 테스트"""

        # 관리자 비밀번호 확인
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_password:
            self.results.add_pass("관리자 비밀번호 설정됨")

            # 비밀번호 강도 검사
            if admin_password == "admin123":
                self.results.add_warning("관리자 비밀번호", "기본 비밀번호 사용 중 (보안 위험)")
            elif len(admin_password) < 8:
                self.results.add_warning("관리자 비밀번호", f"비밀번호가 너무 짧음: {len(admin_password)}자")
            else:
                self.results.add_pass("관리자 비밀번호 강도")
        else:
            self.results.add_fail("관리자 비밀번호", "설정되지 않음")

        # 데이터베이스 파일 확인
        if os.path.exists("report_system.db"):
            self.results.add_pass("데이터베이스 파일 존재")
        else:
            self.results.add_warning("데이터베이스", "파일이 아직 생성되지 않음")

    def test_performance(self):
        """성능 테스트"""

        try:
            import streamlit_app
            import time

            if os.path.exists("team_sample_data.csv"):
                df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')
                index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')

                # 리포트 생성 시간 측정
                start_time = time.time()
                report = streamlit_app.build_report(df, index_df)
                elapsed = time.time() - start_time

                if elapsed < 2.0:
                    self.results.add_pass(f"리포트 생성 성능", f"{elapsed:.2f}초")
                elif elapsed < 5.0:
                    self.results.add_warning("리포트 생성 성능", f"{elapsed:.2f}초 (느림)")
                else:
                    self.results.add_fail("리포트 생성 성능", f"{elapsed:.2f}초 (매우 느림)")

                # 메모리 사용량 확인
                try:
                    import psutil
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024

                    if memory_mb < 500:
                        self.results.add_pass(f"메모리 사용량", f"{memory_mb:.1f} MB")
                    else:
                        self.results.add_warning("메모리 사용량", f"{memory_mb:.1f} MB (높음)")
                except ImportError:
                    self.results.add_warning("메모리 모니터링", "psutil 미설치")

        except Exception as e:
            self.results.add_fail("성능 테스트", str(e))

    def test_edge_cases(self):
        """엣지 케이스 및 오류 처리 테스트"""

        try:
            import streamlit_app

            # 빈 데이터프레임 처리
            empty_df = pd.DataFrame()
            index_df = pd.read_csv("index_v2.csv", encoding='utf-8-sig')

            try:
                result = streamlit_app.group_data_by_unit(empty_df, "전체", None)
                if result:
                    self.results.add_pass("빈 데이터 처리")
                else:
                    self.results.add_fail("빈 데이터", "결과가 None")
            except Exception as e:
                self.results.add_fail("빈 데이터 처리", str(e))

            # 잘못된 컬럼명 처리
            if os.path.exists("team_sample_data.csv"):
                df = pd.read_csv("team_sample_data.csv", encoding='utf-8-sig')

                try:
                    result = streamlit_app.group_data_by_unit(df, "팀별", "존재하지않는컬럼")
                    if "전체 조직" in result:
                        self.results.add_pass("잘못된 컬럼명 처리")
                    else:
                        self.results.add_fail("잘못된 컬럼명", "폴백 처리 실패")
                except Exception as e:
                    self.results.add_warning("잘못된 컬럼명 처리", f"예외 발생: {e}")

            # 특수문자 처리 테스트
            test_team_names = ["팀/이름", "팀\\이름", "팀&이름", "팀 이름"]
            for team_name in test_team_names:
                safe_name = team_name.replace("/", "_").replace("\\", "_")
                if "/" not in safe_name and "\\" not in safe_name:
                    self.results.add_pass(f"특수문자 처리: {team_name}")
                else:
                    self.results.add_fail(f"특수문자 처리", f"{team_name} 변환 실패")

        except Exception as e:
            self.results.add_fail("엣지 케이스 테스트", str(e))

    def print_summary(self):
        """테스트 요약 출력"""
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}테스트 요약{RESET}")
        print(f"{BOLD}{'='*60}{RESET}")

        total = self.results.passed + self.results.failed + self.results.warnings

        print(f"\n전체 테스트: {total}")
        print(f"{GREEN}통과: {self.results.passed}{RESET}")
        print(f"{YELLOW}경고: {self.results.warnings}{RESET}")
        print(f"{RED}실패: {self.results.failed}{RESET}")

        if self.results.failed == 0:
            print(f"\n{GREEN}{BOLD}✓ 모든 필수 테스트 통과!{RESET}")
        else:
            print(f"\n{RED}{BOLD}✗ {self.results.failed}개 테스트 실패{RESET}")
            print("\n실패한 테스트:")
            for error in self.results.errors:
                print(f"  - {error}")

        if self.results.warnings > 0:
            print(f"\n{YELLOW}경고 사항:{RESET}")
            for warning in self.results.warnings_list:
                print(f"  - {warning}")

    def generate_test_report(self):
        """테스트 리포트 파일 생성"""

        report_path = "test_report.md"

        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# 조직 효과성 리포트 시스템 - 테스트 리포트\n\n")
            f.write(f"**테스트 일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            f.write("## 요약\n\n")
            total = self.results.passed + self.results.failed + self.results.warnings
            f.write(f"- **전체 테스트:** {total}\n")
            f.write(f"- **통과:** {self.results.passed}\n")
            f.write(f"- **경고:** {self.results.warnings}\n")
            f.write(f"- **실패:** {self.results.failed}\n\n")

            f.write("## 상세 결과\n\n")

            current_category = ""
            for detail in self.results.test_details:
                # 카테고리별로 구분
                test_name = detail['test']

                if detail['status'] == 'PASS':
                    f.write(f"✅ **{test_name}**")
                    if detail.get('details'):
                        f.write(f" - {detail['details']}")
                    f.write("\n")
                elif detail['status'] == 'FAIL':
                    f.write(f"❌ **{test_name}**\n")
                    f.write(f"   - 오류: {detail['error']}\n")
                elif detail['status'] == 'WARN':
                    f.write(f"⚠️ **{test_name}**\n")
                    f.write(f"   - 경고: {detail['warning']}\n")

            if self.results.failed > 0:
                f.write("\n## 조치 필요 사항\n\n")
                for error in self.results.errors:
                    f.write(f"- {error}\n")

            f.write("\n## 권장 사항\n\n")

            recommendations = []

            if "기본 비밀번호" in str(self.results.warnings_list):
                recommendations.append("관리자 비밀번호를 기본값에서 변경하세요")

            if "API 키가 설정되지 않음" in str(self.results.warnings_list):
                recommendations.append("AI 기능 사용을 위해 Google API 키를 설정하세요")

            if "SMTP" in str(self.results.warnings_list):
                recommendations.append("이메일 기능을 위해 SMTP 설정을 완료하세요")

            if not recommendations:
                recommendations.append("시스템이 정상적으로 작동하고 있습니다")

            for rec in recommendations:
                f.write(f"- {rec}\n")

        print(f"\n📄 테스트 리포트 생성 완료: {report_path}")


if __name__ == "__main__":
    tester = ComprehensiveTestSuite()
    tester.run_all_tests()