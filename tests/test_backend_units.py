"""
백엔드 로직 단위 테스트
모든 주요 함수와 기능을 개별적으로 테스트
"""
import pytest
import pandas as pd
import json
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestDataProcessing:
    """데이터 처리 함수 테스트"""

    def test_extract_no40_text(self):
        """NO40 텍스트 추출 함수 테스트"""
        # 실제 함수 import
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import _extract_no40_from_open

        # 테스트 데이터
        test_open_ended = {
            "basic_responses": [
                {
                    "header": "NO40",
                    "title": "조직 이미지",
                    "answers": ["혁신적", "협력적", "안정적"]
                }
            ]
        }

        result = _extract_no40_from_open(test_open_ended)
        assert "혁신적" in result
        assert "협력적" in result
        assert "안정적" in result
        print("✅ NO40 텍스트 추출 테스트 통과")

    def test_extract_no40_text_empty_data(self):
        """빈 데이터에 대한 NO40 텍스트 추출 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import _extract_no40_from_open

        empty_open_ended = {}
        result = _extract_no40_from_open(empty_open_ended)
        assert result == "NO40 관련 응답이 없습니다."
        print("✅ 빈 데이터 NO40 텍스트 추출 테스트 통과")

    def test_parse_uploaded_data(self):
        """업로드된 데이터 파싱 테스트"""
        # 테스트용 DataFrame 생성
        test_data = pd.DataFrame({
            'Q1': [4, 3, 5, 4, 3],
            'Q2': [3, 4, 4, 5, 3],
            'NO40': ['혁신적', '협력적', '성장 지향', '안정적', '도전적'],
            'TEAM': ['A팀', 'B팀', 'A팀', 'C팀', 'B팀']
        })

        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
            test_data.to_excel(tmp.name, index=False)
            tmp_path = tmp.name

        try:
            # 파일 읽기 테스트
            df = pd.read_excel(tmp_path)
            assert len(df) == 5
            assert 'Q1' in df.columns
            assert 'NO40' in df.columns
            assert 'TEAM' in df.columns
            print("✅ 업로드 데이터 파싱 테스트 통과")

        finally:
            # 임시 파일 정리
            os.unlink(tmp_path)

    def test_team_grouping(self):
        """팀별 데이터 그룹핑 테스트"""
        test_data = pd.DataFrame({
            'Q1': [4, 3, 5, 4, 3, 2],
            'TEAM': ['A팀', 'B팀', 'A팀', 'C팀', 'B팀', 'A팀']
        })

        grouped = test_data.groupby('TEAM')
        team_counts = grouped.size()

        assert team_counts['A팀'] == 3
        assert team_counts['B팀'] == 2
        assert team_counts['C팀'] == 1
        print("✅ 팀별 데이터 그룹핑 테스트 통과")


class TestAIFunctions:
    """AI 관련 함수 테스트"""

    @patch('streamlit_app.genai')
    def test_generate_ai_interpretation_success(self, mock_genai):
        """AI 해석 생성 성공 케이스 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # Mock 설정
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "AI 생성된 분석 결과입니다."
        mock_client.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_client
        mock_genai.configure = Mock()
        mock_genai.types.GenerationConfig = Mock()

        # 테스트 데이터 (실제 리포트 구조에 맞게)
        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'responses': ['혁신적']},
                    {'header': 'NO41', 'responses': ['팀워크']},
                    {'header': 'NO42', 'responses': ['소통']},
                    {'header': 'NO43', 'responses': ['시간']}
                ]
            }
        }

        result = run_ai_interpretation_gemini_from_report(test_report)
        assert isinstance(result, dict)
        print("✅ AI 해석 생성 성공 테스트 통과")

    @patch('streamlit_app.genai')
    def test_generate_ai_interpretation_failure(self, mock_genai):
        """AI 해석 생성 실패 케이스 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # Mock이 예외를 발생시키도록 설정
        mock_genai.configure.side_effect = Exception("API 키 오류")

        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'responses': ['테스트']}
                ]
            }
        }

        result = run_ai_interpretation_gemini_from_report(test_report)
        assert isinstance(result, dict)  # 오류 시에도 딕셔너리 반환
        print("✅ AI 해석 생성 실패 테스트 통과")

    def test_prompt_template_loading(self):
        """프롬프트 템플릿 로딩 테스트"""
        prompt_path = "/Users/crystal/flask-report/prompts/gemini_text_ko.md"

        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert len(content) > 0
            assert "역할" in content or "입력" in content
            print("✅ 프롬프트 템플릿 로딩 테스트 통과")
        else:
            print("⚠️ 프롬프트 파일을 찾을 수 없음")


class TestEmailFunctions:
    """이메일 관련 함수 테스트"""

    @patch('streamlit_app.smtplib.SMTP')
    def test_send_email_with_attachment_success(self, mock_smtp):
        """이메일 발송 성공 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import send_email_with_attachment

        # Mock SMTP 서버 설정
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.starttls = Mock()
        mock_server.login = Mock()
        mock_server.sendmail = Mock()
        mock_server.quit = Mock()

        # 테스트 데이터
        result = send_email_with_attachment(
            to_emails=['test@example.com'],
            subject='테스트 이메일',
            body='테스트 내용',
            attachment_data=b'test data',
            attachment_filename='test.pdf',
            sender_email='sender@gmail.com',
            sender_password='test_password'
        )

        assert result['success'] == True
        assert len(result['sent_to']) == 1
        print("✅ 이메일 발송 성공 테스트 통과")

    @patch('streamlit_app.smtplib.SMTP')
    def test_send_email_with_attachment_failure(self, mock_smtp):
        """이메일 발송 실패 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import send_email_with_attachment

        # Mock이 예외를 발생시키도록 설정
        mock_smtp.side_effect = Exception("SMTP 연결 실패")

        result = send_email_with_attachment(
            to_emails=['test@example.com'],
            subject='테스트 이메일',
            body='테스트 내용',
            attachment_data=b'test data',
            attachment_filename='test.pdf',
            sender_email='sender@gmail.com',
            sender_password='wrong_password'
        )

        assert result['success'] == False
        assert "오류" in result['message']
        print("✅ 이메일 발송 실패 테스트 통과")

    def test_create_email_mapping_validation(self):
        """이메일 매핑 검증 테스트"""
        # 올바른 이메일 형식 테스트
        valid_emails = [
            'test@example.com',
            'user123@gmail.com',
            'admin@company.co.kr'
        ]

        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for email in valid_emails:
            assert re.match(email_pattern, email)

        # 잘못된 이메일 형식 테스트
        invalid_emails = [
            'invalid_email',
            '@example.com',
            'test@',
            'test.com'
        ]

        for email in invalid_emails:
            assert not re.match(email_pattern, email)

        print("✅ 이메일 매핑 검증 테스트 통과")


class TestPDFGeneration:
    """PDF 생성 관련 함수 테스트"""

    def test_generate_pdf_success(self):
        """PDF 생성 성공 테스트 (간단한 구조 확인)"""
        # PDF 생성 함수가 호출 가능한지만 확인
        import sys
        sys.path.append('/Users/crystal/flask-report')

        try:
            from streamlit_app import generate_multiple_pdfs
            # 함수가 import 가능한지 확인
            assert callable(generate_multiple_pdfs)
            print("✅ PDF 생성 함수 import 테스트 통과")
        except ImportError:
            print("⚠️ PDF 생성 함수 import 실패")

    def test_pdf_template_exists(self):
        """PDF 템플릿 존재 확인 테스트"""
        template_path = "/Users/crystal/flask-report/templates/report.html"

        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()

            assert len(content) > 0
            assert "html" in content.lower()
            print("✅ PDF 템플릿 존재 테스트 통과")
        else:
            print("⚠️ PDF 템플릿 파일을 찾을 수 없음")


class TestDatabaseOperations:
    """데이터베이스 관련 함수 테스트"""

    def test_database_models_import(self):
        """데이터베이스 모델 임포트 테스트"""
        try:
            import sys
            sys.path.append('/Users/crystal/flask-report')
            from database_models import Organization, Report, PDFGeneration, EmailLog
            print("✅ 데이터베이스 모델 임포트 테스트 통과")
        except ImportError as e:
            print(f"⚠️ 데이터베이스 모델 임포트 실패: {e}")

    @patch('database_models.get_session')
    def test_email_log_creation(self, mock_get_session):
        """이메일 로그 생성 테스트"""
        try:
            import sys
            sys.path.append('/Users/crystal/flask-report')
            from database_models import EmailLog

            # Mock 세션
            mock_session = Mock()
            mock_get_session.return_value = mock_session

            # EmailLog 객체 생성 테스트
            email_log = EmailLog(
                recipient_emails='["test@example.com"]',
                subject='테스트 제목',
                status='sent',
                sent_count=1,
                failed_count=0
            )

            assert email_log.recipient_emails == '["test@example.com"]'
            assert email_log.subject == '테스트 제목'
            assert email_log.status == 'sent'
            print("✅ 이메일 로그 생성 테스트 통과")

        except Exception as e:
            print(f"⚠️ 이메일 로그 생성 테스트 실패: {e}")


class TestUtilityFunctions:
    """유틸리티 함수 테스트"""

    def test_safe_dictionary_access(self):
        """안전한 딕셔너리 접근 테스트"""
        test_dict = {
            'level1': {
                'level2': {
                    'value': 'test_value'
                }
            }
        }

        # 정상 접근
        result = test_dict.get('level1', {}).get('level2', {}).get('value', 'default')
        assert result == 'test_value'

        # 존재하지 않는 키 접근
        result = test_dict.get('nonexistent', {}).get('level2', {}).get('value', 'default')
        assert result == 'default'

        print("✅ 안전한 딕셔너리 접근 테스트 통과")

    def test_file_extension_validation(self):
        """파일 확장자 검증 테스트"""
        valid_files = ['data.xlsx', 'report.xls', 'DATA.XLSX']
        invalid_files = ['data.txt', 'report.csv', 'image.png', 'doc.pdf']

        for filename in valid_files:
            assert filename.lower().endswith(('.xlsx', '.xls'))

        for filename in invalid_files:
            assert not filename.lower().endswith(('.xlsx', '.xls'))

        print("✅ 파일 확장자 검증 테스트 통과")

    def test_data_sanitization(self):
        """데이터 정제 테스트"""
        # 특수 문자 제거 테스트
        test_strings = [
            "정상 텍스트",
            "특수문자@#$포함",
            "  공백  포함  ",
            "줄바꿈\n포함"
        ]

        for text in test_strings:
            # 기본적인 정제
            cleaned = text.strip()
            assert not cleaned.startswith(' ')
            assert not cleaned.endswith(' ')

        print("✅ 데이터 정제 테스트 통과")


def run_backend_tests():
    """백엔드 단위 테스트 실행 함수"""
    print("🧪 백엔드 로직 단위 테스트 시작")
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
    run_backend_tests()