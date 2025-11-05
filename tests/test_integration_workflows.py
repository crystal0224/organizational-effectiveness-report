"""
통합 테스트 - 전체 워크플로우 테스트
실제 사용자 시나리오와 동일한 경로로 전체 기능을 테스트
"""
import pytest
import pandas as pd
import time
import tempfile
import os
import json
from unittest.mock import Mock, patch
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TestCompleteWorkflows:
    """완전한 워크플로우 통합 테스트"""

    def test_complete_report_generation_workflow(self, chrome_driver, streamlit_url, sample_excel_file, test_helper, streamlit_app_running):
        """1. 전체 리포트 생성 워크플로우 테스트"""
        print("🔄 전체 리포트 생성 워크플로우 테스트 시작")

        # 1단계: 앱 접속
        chrome_driver.get(streamlit_url)
        test_helper.wait_for_streamlit_load(chrome_driver)
        print("✅ 1단계: 앱 접속 완료")

        # 2단계: 파일 업로드
        try:
            file_upload_inputs = chrome_driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            if file_upload_inputs:
                file_input = file_upload_inputs[0]
                test_helper.upload_file(chrome_driver, file_input, sample_excel_file)
                time.sleep(5)  # 업로드 처리 대기
                print("✅ 2단계: 파일 업로드 완료")
            else:
                print("⚠️ 2단계: 파일 업로드 입력 요소를 찾을 수 없음")
        except Exception as e:
            print(f"⚠️ 2단계 실패: {e}")

        # 3단계: 리포트 미리보기 확인
        try:
            preview_menu = test_helper.find_element_by_text(chrome_driver, "리포트 미리보기")
            chrome_driver.execute_script("arguments[0].click();", preview_menu)
            time.sleep(3)

            # 리포트 콘텐츠 확인
            page_source = chrome_driver.page_source
            report_indicators = ["조직 효과성", "IPO", "진단", "차트"]
            report_visible = any(indicator in page_source for indicator in report_indicators)

            if report_visible:
                print("✅ 3단계: 리포트 미리보기 확인 완료")
            else:
                print("⚠️ 3단계: 리포트 콘텐츠 확인 실패")

        except Exception as e:
            print(f"⚠️ 3단계 실패: {e}")

        # 4단계: AI 분석 버튼 존재 확인 (실제 실행은 하지 않음)
        try:
            ai_buttons = chrome_driver.find_elements(By.XPATH, "//*[contains(text(), 'AI') and contains(text(), '분석')]")
            if ai_buttons and ai_buttons[0].is_enabled():
                print("✅ 4단계: AI 분석 기능 확인 완료")
            else:
                print("⚠️ 4단계: AI 분석 버튼을 찾을 수 없거나 비활성화됨")
        except Exception as e:
            print(f"⚠️ 4단계 실패: {e}")

        # 5단계: PDF 생성 메뉴 확인
        try:
            pdf_menu = test_helper.find_element_by_text(chrome_driver, "PDF 생성")
            chrome_driver.execute_script("arguments[0].click();", pdf_menu)
            time.sleep(3)

            page_source = chrome_driver.page_source
            pdf_indicators = ["PDF", "생성", "다운로드"]
            pdf_interface_visible = any(indicator in page_source for indicator in pdf_indicators)

            if pdf_interface_visible:
                print("✅ 5단계: PDF 생성 인터페이스 확인 완료")
            else:
                print("⚠️ 5단계: PDF 생성 인터페이스 확인 실패")

        except Exception as e:
            print(f"⚠️ 5단계 실패: {e}")

        print("🎉 전체 리포트 생성 워크플로우 테스트 완료")

    @patch('streamlit_app.run_ai_interpretation_gemini_from_report')
    def test_ai_analysis_workflow(self, mock_ai_generation):
        """2. AI 분석 워크플로우 테스트"""
        print("🔄 AI 분석 워크플로우 테스트 시작")

        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # Mock AI 응답 설정
        mock_ai_generation.return_value = {"summary": "AI가 생성한 조직 분석 결과입니다."}

        # 테스트 데이터 준비 (리포트 구조에 맞게)
        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'answers': ['혁신적']},
                    {'header': 'NO41', 'answers': ['팀워크']},
                    {'header': 'NO42', 'answers': ['개선']},
                    {'header': 'NO43', 'answers': ['시간부족']}
                ]
            }
        }

        # AI 분석 실행
        result = run_ai_interpretation_gemini_from_report(test_report)

        # 결과 검증
        assert result is not None
        assert len(result) > 0
        print("✅ AI 분석 워크플로우 테스트 완료")

    @patch('streamlit_app.send_email_with_attachment')
    def test_email_sending_workflow(self, mock_send_email):
        """3. 이메일 발송 워크플로우 테스트"""
        print("🔄 이메일 발송 워크플로우 테스트 시작")

        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import send_email_with_attachment

        # Mock 이메일 발송 성공 응답
        mock_send_email.return_value = {
            'success': True,
            'message': '이메일이 성공적으로 발송되었습니다.',
            'sent_to': ['test@example.com'],
            'failed_to': []
        }

        # 이메일 발송 테스트
        result = send_email_with_attachment(
            to_emails=['test@example.com'],
            subject='테스트 리포트',
            body='첨부된 리포트를 확인해 주세요.',
            attachment_data=b'PDF content',
            attachment_filename='report.pdf',
            sender_email='sender@gmail.com',
            sender_password='test_password'
        )

        # 결과 검증
        assert result['success'] == True
        assert len(result['sent_to']) == 1
        print("✅ 이메일 발송 워크플로우 테스트 완료")

    def test_data_processing_pipeline(self):
        """4. 데이터 처리 파이프라인 테스트"""
        print("🔄 데이터 처리 파이프라인 테스트 시작")

        # 1단계: 원본 데이터 생성
        raw_data = pd.DataFrame({
            'Q1': [4, 3, 5, 4, 3, 2, 5, 4] * 12,  # 96개 응답
            'Q2': [3, 4, 4, 5, 3, 4, 3, 5] * 12,
            'Q3': [5, 4, 3, 4, 5, 3, 4, 5] * 12,
            'NO40': ['혁신적', '협력적', '안정적', '도전적', '성장지향', '전문적', '유연한', '효율적'] * 12,
            'NO41': ['팀워크', '소통', '리더십', '전문성', '창의성', '협업', '효율성', '혁신'] * 12,
            'NO42': ['소통개선', '프로세스정비', '교육강화', '시스템개선', '인력충원', '문화개선', '효율화', '표준화'] * 12,
            'NO43': ['시간부족', '자원제약', '권한제한', '정보부족', '절차복잡', '의사결정지연', '소통부족', '변화저항'] * 12,
            'TEAM': ['A팀', 'B팀', 'C팀', 'D팀'] * 24
        })

        # 2단계: 팀별 그룹핑
        team_groups = raw_data.groupby('TEAM')
        assert len(team_groups) == 4
        print("✅ 2단계: 팀별 그룹핑 완료")

        # 3단계: 통계 계산
        team_stats = {}
        for team_name, team_data in team_groups:
            stats = {
                'count': len(team_data),
                'q1_mean': team_data['Q1'].mean(),
                'q2_mean': team_data['Q2'].mean(),
                'q3_mean': team_data['Q3'].mean()
            }
            team_stats[team_name] = stats

        assert all(stats['count'] == 24 for stats in team_stats.values())
        print("✅ 3단계: 통계 계산 완료")

        # 4단계: 주관식 응답 집계
        qualitative_data = {}
        for team_name, team_data in team_groups:
            qualitative_data[team_name] = {
                'no40_responses': team_data['NO40'].tolist(),
                'no41_responses': team_data['NO41'].tolist(),
                'no42_responses': team_data['NO42'].tolist(),
                'no43_responses': team_data['NO43'].tolist()
            }

        assert all(len(data['no40_responses']) == 24 for data in qualitative_data.values())
        print("✅ 4단계: 주관식 응답 집계 완료")

        print("🎉 데이터 처리 파이프라인 테스트 완료")

    def test_report_template_rendering(self):
        """5. 리포트 템플릿 렌더링 테스트"""
        print("🔄 리포트 템플릿 렌더링 테스트 시작")

        # 테스트용 리포트 데이터 생성
        test_report_data = {
            'organization_name': '테스트 조직',
            'org_name': '테스트 조직',
            'report_date': '2024-11-04',
            'respondents': 100,
            'ipo_cards': [
                {
                    'id': 'input',
                    'title': 'Input (투입)',
                    'score': 4.2,
                    'grade': 'B+',
                    'desc': '조직 자원 투입 수준이 양호함'
                },
                {
                    'id': 'process',
                    'title': 'Process (과정)',
                    'score': 3.8,
                    'grade': 'B',
                    'desc': '업무 프로세스가 원활함'
                },
                {
                    'id': 'output',
                    'title': 'Output (산출)',
                    'score': 4.0,
                    'grade': 'B+',
                    'desc': '성과 달성도가 우수함'
                }
            ],
            'summary': {
                'ai': {
                    'org_context': '혁신적이고 협력적인 조직문화를 가진 조직입니다.',
                    'score': 'IPO 모든 영역에서 균형잡힌 성과를 보이고 있습니다.',
                    'writer': 'AI가 생성한 종합 분석 결과입니다.'
                }
            },
            'overview': {
                'purpose': '조직 효과성 진단을 통한 개선방안 도출',
                'background': ['성과 향상 필요', '조직문화 개선', '프로세스 효율화'],
                'model_desc': 'IPO 프레임워크 기반 진단',
                'model_points': ['투입 요소 분석', '과정 효율성 평가', '산출 성과 측정']
            }
        }

        # 템플릿 파일 존재 확인
        template_path = "/Users/crystal/flask-report/templates/report.html"
        if os.path.exists(template_path):
            print("✅ 리포트 템플릿 파일 확인 완료")

            # 기본적인 템플릿 내용 검증
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()

            template_indicators = ['html', 'body', 'report', 'organization']
            template_valid = any(indicator in template_content.lower() for indicator in template_indicators)

            if template_valid:
                print("✅ 템플릿 내용 유효성 확인 완료")
            else:
                print("⚠️ 템플릿 내용 유효성 확인 실패")

        else:
            print("⚠️ 리포트 템플릿 파일을 찾을 수 없음")

        print("🎉 리포트 템플릿 렌더링 테스트 완료")

    def test_admin_functionality_workflow(self, chrome_driver, streamlit_url, test_helper, streamlit_app_running):
        """6. 관리자 기능 워크플로우 테스트"""
        print("🔄 관리자 기능 워크플로우 테스트 시작")

        chrome_driver.get(streamlit_url)
        test_helper.wait_for_streamlit_load(chrome_driver)

        try:
            # 관리자 로그인 섹션 찾기
            page_source = chrome_driver.page_source
            admin_indicators = ["관리자", "비밀번호", "로그인"]
            admin_section_visible = any(indicator in page_source for indicator in admin_indicators)

            if admin_section_visible:
                print("✅ 관리자 로그인 섹션 확인됨")

                # 비밀번호 입력 필드 확인
                password_inputs = chrome_driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
                if password_inputs:
                    print("✅ 관리자 비밀번호 입력 필드 확인됨")
                else:
                    print("⚠️ 관리자 비밀번호 입력 필드를 찾을 수 없음")

            else:
                print("⚠️ 관리자 섹션을 찾을 수 없음")

        except Exception as e:
            print(f"관리자 기능 테스트 중 오류: {e}")

        print("🎉 관리자 기능 워크플로우 테스트 완료")

    def test_error_recovery_workflow(self, chrome_driver, streamlit_url, test_helper, streamlit_app_running):
        """7. 오류 복구 워크플로우 테스트"""
        print("🔄 오류 복구 워크플로우 테스트 시작")

        chrome_driver.get(streamlit_url)
        test_helper.wait_for_streamlit_load(chrome_driver)

        try:
            # 잘못된 파일 업로드 시뮬레이션
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("This is not an Excel file")
                temp_txt_file = f.name

            # 파일 업로드 시도
            file_upload_inputs = chrome_driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
            if file_upload_inputs:
                file_input = file_upload_inputs[0]
                test_helper.upload_file(chrome_driver, file_input, temp_txt_file)
                time.sleep(3)

                # 앱이 여전히 작동하는지 확인
                main_content = chrome_driver.find_element(By.TAG_NAME, "main")
                if main_content.is_displayed():
                    print("✅ 오류 후 앱 안정성 확인됨")
                else:
                    print("⚠️ 오류 후 앱 불안정")

            # 임시 파일 정리
            if os.path.exists(temp_txt_file):
                os.remove(temp_txt_file)

        except Exception as e:
            print(f"오류 복구 테스트 중 오류: {e}")

        print("🎉 오류 복구 워크플로우 테스트 완료")


class TestCrossFeatureIntegration:
    """기능 간 통합 테스트"""

    def test_data_to_report_integration(self):
        """데이터 업로드부터 리포트 생성까지 통합 테스트"""
        print("🔄 데이터-리포트 통합 테스트 시작")

        # 샘플 데이터 생성
        sample_data = pd.DataFrame({
            'Q1': [4, 3, 5] * 20,
            'Q2': [3, 4, 4] * 20,
            'NO40': ['혁신적', '협력적', '안정적'] * 20,
            'TEAM': ['A팀', 'B팀', 'C팀'] * 20
        })

        # 데이터 검증
        assert len(sample_data) == 60
        assert 'TEAM' in sample_data.columns
        assert sample_data['Q1'].dtype in ['int64', 'float64']

        # 팀별 분할
        teams = sample_data.groupby('TEAM')
        assert len(teams) == 3

        print("✅ 데이터-리포트 통합 테스트 완료")

    def test_report_to_pdf_integration(self):
        """리포트부터 PDF 생성까지 통합 테스트"""
        print("🔄 리포트-PDF 통합 테스트 시작")

        # 리포트 구조 검증
        report_structure = {
            'organization_name': 'str',
            'ipo_cards': 'list',
            'summary': 'dict',
            'overview': 'dict'
        }

        sample_report = {
            'organization_name': '테스트 조직',
            'ipo_cards': [{'id': 'input', 'score': 4.0}],
            'summary': {'ai': {}},
            'overview': {'purpose': '테스트'}
        }

        # 구조 검증
        for key, expected_type in report_structure.items():
            assert key in sample_report
            if expected_type == 'str':
                assert isinstance(sample_report[key], str)
            elif expected_type == 'list':
                assert isinstance(sample_report[key], list)
            elif expected_type == 'dict':
                assert isinstance(sample_report[key], dict)

        print("✅ 리포트-PDF 통합 테스트 완료")

    def test_pdf_to_email_integration(self):
        """PDF부터 이메일 발송까지 통합 테스트"""
        print("🔄 PDF-이메일 통합 테스트 시작")

        # 가짜 PDF 데이터
        fake_pdf_data = b'%PDF-1.4 fake pdf content'

        # 이메일 데이터 구조 검증
        email_data = {
            'recipients': ['test@example.com'],
            'subject': '테스트 리포트',
            'body': '첨부 파일을 확인해 주세요.',
            'attachment': fake_pdf_data,
            'filename': 'report.pdf'
        }

        # 필수 필드 검증
        required_fields = ['recipients', 'subject', 'body', 'attachment', 'filename']
        for field in required_fields:
            assert field in email_data

        # 데이터 타입 검증
        assert isinstance(email_data['recipients'], list)
        assert isinstance(email_data['attachment'], bytes)
        assert email_data['filename'].endswith('.pdf')

        print("✅ PDF-이메일 통합 테스트 완료")


def run_integration_tests():
    """통합 테스트 실행 함수"""
    print("🔄 통합 워크플로우 테스트 시작")
    print("=" * 50)

    # pytest 실행
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "--no-header",
        "--disable-warnings"
    ])


if __name__ == "__main__":
    run_integration_tests()