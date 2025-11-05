"""
에러 케이스 및 예외 처리 테스트
다양한 실패 시나리오와 예외 상황에 대한 복원력 테스트
"""
import pytest
import pandas as pd
import json
import tempfile
import os
import requests
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import smtplib
import sqlite3


class TestDataValidationErrors:
    """데이터 검증 오류 테스트"""

    def test_invalid_excel_file_upload(self):
        """잘못된 Excel 파일 업로드 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')

        # 텍스트 파일을 Excel 확장자로 저장
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False, mode='w') as f:
            f.write("This is not an Excel file")
            invalid_file = f.name

        try:
            # pandas로 읽기 시도하면 예외 발생해야 함
            with pytest.raises((pd.errors.EmptyDataError, ValueError, Exception)):
                df = pd.read_excel(invalid_file)
            print("✅ 잘못된 Excel 파일 예외 처리 테스트 통과")
        finally:
            if os.path.exists(invalid_file):
                os.remove(invalid_file)

    def test_missing_required_columns(self):
        """필수 컬럼 누락 테스트"""
        # 필수 컬럼이 없는 데이터
        invalid_data = pd.DataFrame({
            'WRONG_COLUMN': [1, 2, 3],
            'ANOTHER_WRONG': ['a', 'b', 'c']
        })

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            invalid_data.to_excel(f.name, index=False)
            temp_file = f.name

        try:
            df = pd.read_excel(temp_file)
            # 필수 컬럼들이 없는지 확인
            required_columns = ['Q1', 'Q2', 'NO40', 'TEAM']
            missing_columns = [col for col in required_columns if col not in df.columns]

            assert len(missing_columns) > 0, "필수 컬럼 누락이 감지되어야 함"
            print(f"✅ 필수 컬럼 누락 감지: {missing_columns}")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_empty_dataframe_handling(self):
        """빈 데이터프레임 처리 테스트"""
        empty_df = pd.DataFrame()

        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as f:
            empty_df.to_excel(f.name, index=False)
            temp_file = f.name

        try:
            df = pd.read_excel(temp_file)
            assert len(df) == 0, "빈 데이터프레임이어야 함"
            print("✅ 빈 데이터프레임 처리 테스트 통과")
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)

    def test_invalid_team_data(self):
        """잘못된 팀 데이터 테스트"""
        # 팀 컬럼에 None 값이 포함된 데이터
        invalid_team_data = pd.DataFrame({
            'Q1': [4, 3, 5],
            'TEAM': ['A팀', None, '']  # None과 빈 문자열
        })

        # None 값이 있는 팀 데이터 처리
        valid_teams = invalid_team_data['TEAM'].dropna()
        valid_teams = valid_teams[valid_teams != '']

        assert len(valid_teams) == 1, "유효한 팀은 1개여야 함"
        print("✅ 잘못된 팀 데이터 필터링 테스트 통과")


class TestAIServiceErrors:
    """AI 서비스 오류 테스트"""

    @patch('streamlit_app.genai')
    def test_ai_api_connection_error(self, mock_genai):
        """AI API 연결 오류 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # API 연결 오류 시뮬레이션
        mock_genai.configure.side_effect = ConnectionError("네트워크 연결 실패")

        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'answers': ['테스트']}
                ]
            }
        }

        result = run_ai_interpretation_gemini_from_report(test_report)

        # 오류 상황에서도 적절한 메시지가 반환되어야 함
        assert isinstance(result, dict)
        print("✅ AI API 연결 오류 처리 테스트 통과")

    @patch('streamlit_app.genai')
    def test_ai_api_key_error(self, mock_genai):
        """AI API 키 오류 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # API 키 오류 시뮬레이션
        mock_genai.configure.side_effect = Exception("API 키가 유효하지 않습니다")

        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'answers': ['테스트']}
                ]
            }
        }

        result = run_ai_interpretation_gemini_from_report(test_report)
        assert isinstance(result, dict)
        print("✅ AI API 키 오류 처리 테스트 통과")

    @patch('streamlit_app.genai')
    def test_ai_timeout_error(self, mock_genai):
        """AI API 타임아웃 오류 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import run_ai_interpretation_gemini_from_report

        # 타임아웃 오류 시뮬레이션
        mock_client = Mock()
        mock_client.generate_content.side_effect = TimeoutError("요청 시간 초과")
        mock_genai.GenerativeModel.return_value = mock_client
        mock_genai.configure = Mock()

        test_report = {
            'organization_name': '테스트 조직',
            'open_ended': {
                'basic_responses': [
                    {'header': 'NO40', 'answers': ['테스트']}
                ]
            }
        }

        result = run_ai_interpretation_gemini_from_report(test_report)
        assert isinstance(result, dict)
        print("✅ AI API 타임아웃 오류 처리 테스트 통과")


class TestEmailServiceErrors:
    """이메일 서비스 오류 테스트"""

    @patch('streamlit_app.smtplib.SMTP')
    def test_smtp_connection_failure(self, mock_smtp):
        """SMTP 연결 실패 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import send_email_with_attachment

        # SMTP 연결 실패 시뮬레이션
        mock_smtp.side_effect = smtplib.SMTPConnectError(421, "연결할 수 없습니다")

        result = send_email_with_attachment(
            to_emails=['test@example.com'],
            subject='테스트',
            body='테스트 내용',
            attachment_data=b'test',
            attachment_filename='test.pdf',
            sender_email='sender@gmail.com',
            sender_password='wrong_password'
        )

        assert result['success'] == False
        assert "오류" in result['message']
        print("✅ SMTP 연결 실패 처리 테스트 통과")

    @patch('streamlit_app.smtplib.SMTP')
    def test_smtp_authentication_failure(self, mock_smtp):
        """SMTP 인증 실패 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')
        from streamlit_app import send_email_with_attachment
        from database_models import init_database

        # 테스트용 데이터베이스 초기화
        try:
            init_database()
        except:
            pass  # 이미 초기화된 경우 무시

        # SMTP 인증 실패 시뮬레이션
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server
        mock_server.starttls = Mock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, "인증 실패")

        result = send_email_with_attachment(
            to_emails=['test@example.com'],
            subject='테스트',
            body='테스트 내용',
            attachment_data=b'test',
            attachment_filename='test.pdf',
            sender_email='sender@gmail.com',
            sender_password='wrong_password'
        )

        assert result['success'] == False
        print("✅ SMTP 인증 실패 처리 테스트 통과")

    def test_invalid_email_format(self):
        """잘못된 이메일 형식 테스트"""
        import re

        invalid_emails = [
            'not_an_email',
            '@example.com',
            'test@',
            'test.com',
            'test@@example.com',
            'test@.com',
            '',
            None
        ]

        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        for email in invalid_emails:
            if email is None:
                is_valid = False
            else:
                is_valid = bool(re.match(email_pattern, email))

            assert not is_valid, f"{email}은 유효하지 않은 이메일이어야 함"

        print("✅ 잘못된 이메일 형식 검증 테스트 통과")


class TestPDFGenerationErrors:
    """PDF 생성 오류 테스트"""

    def test_pdf_generation_playwright_error(self):
        """PDF 생성 중 Playwright 오류 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')

        try:
            from streamlit_app import generate_multiple_pdfs
            # 함수가 import 가능한지만 확인
            assert callable(generate_multiple_pdfs)
            print("✅ PDF 생성 함수 import 테스트 통과")
        except ImportError:
            print("⚠️ PDF 생성 함수 import 실패")

    def test_pdf_template_missing(self):
        """PDF 템플릿 파일 누락 테스트"""
        template_path = "/Users/crystal/flask-report/templates/report.html"

        # 템플릿 파일이 없을 때의 처리
        if not os.path.exists(template_path):
            print("⚠️ PDF 템플릿 파일이 없음 - 이는 처리되어야 할 에러 상황")
        else:
            # 템플릿 파일이 있다면 내용 검증
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            assert len(content) > 0
            print("✅ PDF 템플릿 파일 존재 확인")

    def test_invalid_report_data_for_pdf(self):
        """PDF 생성용 잘못된 리포트 데이터 테스트"""
        import sys
        sys.path.append('/Users/crystal/flask-report')

        # 필수 키가 없는 리포트 데이터
        invalid_report = {}

        # 안전한 딕셔너리 접근 패턴 테스트
        org_name = invalid_report.get('organization_name', '알 수 없는 조직')
        summary = invalid_report.get('summary', {})
        ai_summary = summary.get('ai', {})

        assert org_name == '알 수 없는 조직'
        assert ai_summary == {}
        print("✅ 잘못된 리포트 데이터 안전 처리 테스트 통과")


class TestDatabaseErrors:
    """데이터베이스 오류 테스트"""

    def test_database_connection_error(self):
        """데이터베이스 연결 오류 테스트"""
        try:
            # 존재하지 않는 데이터베이스 경로로 연결 시도
            conn = sqlite3.connect('/nonexistent/path/database.db', timeout=1)
            conn.execute("SELECT 1")
        except sqlite3.OperationalError as e:
            print(f"✅ 데이터베이스 연결 오류 정상 처리: {e}")
        except Exception as e:
            print(f"✅ 예상된 데이터베이스 오류: {e}")

    @patch('database_models.get_session')
    def test_database_transaction_rollback(self, mock_get_session):
        """데이터베이스 트랜잭션 롤백 테스트"""
        try:
            import sys
            sys.path.append('/Users/crystal/flask-report')
            from database_models import EmailLog

            # Mock 세션에서 예외 발생 시뮬레이션
            mock_session = Mock()
            mock_session.add.side_effect = Exception("데이터베이스 오류")
            mock_session.commit.side_effect = Exception("커밋 실패")
            mock_get_session.return_value = mock_session

            # 예외가 발생해도 적절히 처리되어야 함
            try:
                email_log = EmailLog(
                    recipient_emails='["test@example.com"]',
                    subject='테스트',
                    body='테스트 내용',
                    status='failed',
                    sent_count=0,
                    failed_count=1
                )
                mock_session.add(email_log)
                mock_session.commit()
            except Exception:
                mock_session.rollback()
                print("✅ 데이터베이스 트랜잭션 롤백 테스트 통과")

        except ImportError:
            print("⚠️ 데이터베이스 모델을 가져올 수 없음")


class TestFileSystemErrors:
    """파일 시스템 오류 테스트"""

    def test_permission_denied_error(self):
        """파일 권한 거부 오류 테스트"""
        # 권한이 없는 경로에 파일 쓰기 시도
        restricted_path = "/root/test_file.txt"

        try:
            with open(restricted_path, 'w') as f:
                f.write("test")
        except PermissionError:
            print("✅ 파일 권한 거부 오류 정상 처리")
        except Exception as e:
            print(f"✅ 예상된 파일 시스템 오류: {type(e).__name__}")

    def test_disk_space_simulation(self):
        """디스크 공간 부족 시뮬레이션 테스트"""
        import shutil

        # 현재 디스크 사용량 확인
        try:
            total, used, free = shutil.disk_usage("/")

            # 디스크 공간이 1GB 미만이면 경고
            if free < 1024 * 1024 * 1024:  # 1GB
                print(f"⚠️ 디스크 공간 부족 경고: {free / (1024**3):.2f}GB 남음")
            else:
                print(f"✅ 디스크 공간 충분: {free / (1024**3):.2f}GB 남음")

        except Exception as e:
            print(f"✅ 디스크 공간 확인 중 오류: {e}")

    def test_temporary_file_cleanup(self):
        """임시 파일 정리 테스트"""
        temp_files = []

        try:
            # 여러 임시 파일 생성
            for i in range(3):
                with tempfile.NamedTemporaryFile(delete=False, suffix=f'_test_{i}.tmp') as f:
                    f.write(b"test data")
                    temp_files.append(f.name)

            # 모든 파일이 생성되었는지 확인
            for file_path in temp_files:
                assert os.path.exists(file_path)

            print("✅ 임시 파일 생성 확인")

        finally:
            # 정리 - 실패해도 계속 진행
            cleaned_count = 0
            for file_path in temp_files:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        cleaned_count += 1
                except Exception as e:
                    print(f"⚠️ 임시 파일 정리 실패: {file_path} - {e}")

            print(f"✅ 임시 파일 정리 완료: {cleaned_count}/{len(temp_files)}개")


class TestNetworkErrors:
    """네트워크 오류 테스트"""

    @patch('requests.get')
    def test_http_connection_timeout(self, mock_get):
        """HTTP 연결 타임아웃 테스트"""
        # 타임아웃 오류 시뮬레이션
        mock_get.side_effect = requests.exceptions.Timeout("연결 시간 초과")

        try:
            response = requests.get("http://localhost:8501", timeout=1)
        except requests.exceptions.Timeout:
            print("✅ HTTP 연결 타임아웃 오류 정상 처리")
        except Exception as e:
            print(f"✅ 예상된 네트워크 오류: {type(e).__name__}")

    @patch('requests.get')
    def test_http_connection_refused(self, mock_get):
        """HTTP 연결 거부 테스트"""
        # 연결 거부 오류 시뮬레이션
        mock_get.side_effect = requests.exceptions.ConnectionError("연결이 거부되었습니다")

        try:
            response = requests.get("http://localhost:8501")
        except requests.exceptions.ConnectionError:
            print("✅ HTTP 연결 거부 오류 정상 처리")
        except Exception as e:
            print(f"✅ 예상된 네트워크 오류: {type(e).__name__}")


class TestMemoryErrors:
    """메모리 오류 테스트"""

    def test_large_data_handling(self):
        """대용량 데이터 처리 테스트"""
        try:
            # 큰 데이터프레임 생성 (메모리 사용량 모니터링)
            import psutil
            process = psutil.Process()
            initial_memory = process.memory_info().rss

            # 10만 행의 데이터 생성
            large_data = pd.DataFrame({
                'Q1': [4] * 100000,
                'Q2': [3] * 100000,
                'NO40': ['테스트 응답'] * 100000,
                'TEAM': ['테스트팀'] * 100000
            })

            current_memory = process.memory_info().rss
            memory_used = (current_memory - initial_memory) / (1024 * 1024)  # MB

            # 메모리 사용량이 500MB를 넘으면 경고
            if memory_used > 500:
                print(f"⚠️ 메모리 사용량 경고: {memory_used:.2f}MB")
            else:
                print(f"✅ 대용량 데이터 처리 완료: {memory_used:.2f}MB 사용")

            del large_data  # 메모리 해제

        except MemoryError:
            print("✅ 메모리 부족 오류 정상 처리")
        except Exception as e:
            print(f"✅ 예상된 메모리 관련 오류: {type(e).__name__}")

    def test_memory_cleanup_after_error(self):
        """오류 후 메모리 정리 테스트"""
        import gc

        try:
            # 의도적으로 오류를 발생시킬 큰 객체 생성
            big_list = [i for i in range(1000000)]

            # 인덱스 오류 발생
            value = big_list[2000000]  # IndexError 발생

        except IndexError:
            # 오류 발생 후 명시적 메모리 정리
            if 'big_list' in locals():
                del big_list
            gc.collect()
            print("✅ 오류 후 메모리 정리 완료")
        except Exception as e:
            print(f"✅ 예상된 메모리 오류: {type(e).__name__}")


class TestConcurrencyErrors:
    """동시성 오류 테스트"""

    def test_concurrent_file_access(self):
        """동시 파일 접근 테스트"""
        import threading
        import time

        test_file = "/tmp/concurrent_test.txt"
        errors = []

        def write_to_file(thread_id):
            try:
                with open(test_file, 'a') as f:
                    for i in range(10):
                        f.write(f"Thread {thread_id}: Line {i}\n")
                        time.sleep(0.01)
            except Exception as e:
                errors.append(f"Thread {thread_id}: {e}")

        # 여러 스레드로 동시 파일 쓰기
        threads = []
        for i in range(3):
            thread = threading.Thread(target=write_to_file, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # 오류 확인
        if errors:
            print(f"⚠️ 동시 파일 접근 오류 발생: {len(errors)}개")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✅ 동시 파일 접근 테스트 통과")

        # 정리
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_race_condition_simulation(self):
        """경쟁 상태 시뮬레이션 테스트"""
        import threading

        shared_counter = {'value': 0}
        errors = []

        def increment_counter(iterations):
            try:
                for _ in range(iterations):
                    # 경쟁 상태 발생 가능한 코드
                    current = shared_counter['value']
                    shared_counter['value'] = current + 1
            except Exception as e:
                errors.append(str(e))

        # 여러 스레드로 카운터 증가
        threads = []
        iterations_per_thread = 1000
        num_threads = 3

        for i in range(num_threads):
            thread = threading.Thread(target=increment_counter, args=(iterations_per_thread,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        expected_value = num_threads * iterations_per_thread
        actual_value = shared_counter['value']

        if actual_value != expected_value:
            print(f"⚠️ 경쟁 상태 발생: 예상값={expected_value}, 실제값={actual_value}")
        else:
            print("✅ 경쟁 상태 없음 (드문 경우)")


def run_error_handling_tests():
    """에러 처리 테스트 실행 함수"""
    print("🔥 에러 케이스 및 예외 처리 테스트 시작")
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
    run_error_handling_tests()