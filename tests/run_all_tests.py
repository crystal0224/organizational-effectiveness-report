#!/usr/bin/env python3
"""
종합 테스트 실행기
모든 테스트 스위트를 순차적으로 실행하고 결과를 취합
"""
import os
import sys
import subprocess
import time
from datetime import datetime


class TestRunner:
    """테스트 실행 관리 클래스"""

    def __init__(self):
        self.test_results = {}
        self.start_time = None
        self.end_time = None

    def print_header(self, title):
        """테스트 섹션 헤더 출력"""
        print("\n" + "=" * 60)
        print(f"🧪 {title}")
        print("=" * 60)

    def print_summary(self):
        """최종 테스트 결과 요약 출력"""
        print("\n" + "🎯 테스트 실행 결과 요약" + "=" * 40)
        print(f"📅 실행 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        total_duration = (self.end_time - self.start_time).total_seconds()
        print(f"⏱️  총 소요 시간: {total_duration:.2f}초")

        passed_count = sum(1 for result in self.test_results.values() if result['status'] == 'PASSED')
        failed_count = sum(1 for result in self.test_results.values() if result['status'] == 'FAILED')
        skipped_count = sum(1 for result in self.test_results.values() if result['status'] == 'SKIPPED')

        print(f"\n📊 테스트 결과:")
        print(f"   ✅ 성공: {passed_count}개")
        print(f"   ❌ 실패: {failed_count}개")
        print(f"   ⏭️  건너뛴 테스트: {skipped_count}개")

        print(f"\n📝 상세 결과:")
        for test_name, result in self.test_results.items():
            status_icon = {"PASSED": "✅", "FAILED": "❌", "SKIPPED": "⏭️"}[result['status']]
            print(f"   {status_icon} {test_name}: {result['status']} ({result['duration']:.2f}초)")
            if result['status'] == 'FAILED' and result.get('error'):
                print(f"      오류: {result['error']}")

        # 전체 성공률 계산
        total_tests = passed_count + failed_count
        if total_tests > 0:
            success_rate = (passed_count / total_tests) * 100
            print(f"\n📈 전체 성공률: {success_rate:.1f}%")

        print("=" * 60)

    def run_test_suite(self, test_file, description):
        """개별 테스트 스위트 실행"""
        self.print_header(description)

        test_start_time = time.time()

        try:
            # 테스트 파일이 존재하는지 확인
            if not os.path.exists(test_file):
                print(f"⚠️ 테스트 파일을 찾을 수 없음: {test_file}")
                self.test_results[description] = {
                    'status': 'SKIPPED',
                    'duration': 0,
                    'error': 'File not found'
                }
                return

            # pytest 실행
            result = subprocess.run([
                sys.executable, '-m', 'pytest',
                test_file,
                '-v',
                '--tb=short',
                '--no-header',
                '--disable-warnings'
            ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))

            test_duration = time.time() - test_start_time

            # 결과 분석
            if result.returncode == 0:
                status = 'PASSED'
                print(f"✅ {description} 완료")
            else:
                status = 'FAILED'
                print(f"❌ {description} 실패")
                print(f"오류 출력:\n{result.stderr}")

            # 테스트 출력 표시
            if result.stdout:
                print(f"테스트 출력:\n{result.stdout}")

            self.test_results[description] = {
                'status': status,
                'duration': test_duration,
                'error': result.stderr if result.returncode != 0 else None
            }

        except Exception as e:
            test_duration = time.time() - test_start_time
            print(f"❌ {description} 실행 중 오류 발생: {e}")
            self.test_results[description] = {
                'status': 'FAILED',
                'duration': test_duration,
                'error': str(e)
            }

    def check_dependencies(self):
        """테스트 실행 전 의존성 확인"""
        print("🔍 테스트 실행 전 환경 확인")
        print("-" * 40)

        # Python 버전 확인
        python_version = sys.version.split()[0]
        print(f"🐍 Python 버전: {python_version}")

        # 필수 패키지 확인
        required_packages = [
            'pytest', 'pandas', 'selenium', 'requests',
            'psutil', 'jinja2', 'playwright'
        ]

        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
                print(f"✅ {package}: 설치됨")
            except ImportError:
                print(f"❌ {package}: 누락")
                missing_packages.append(package)

        if missing_packages:
            print(f"\n⚠️ 누락된 패키지를 설치해주세요:")
            print(f"pip install {' '.join(missing_packages)}")
            return False

        # 테스트 디렉토리 확인
        test_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 테스트 디렉토리: {test_dir}")

        # Chrome 드라이버 확인 (UI 테스트용)
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            driver = webdriver.Chrome(options=chrome_options)
            driver.quit()
            print("✅ Chrome WebDriver: 사용 가능")
        except Exception as e:
            print(f"⚠️ Chrome WebDriver: 사용 불가 ({e})")
            print("  UI 자동화 테스트는 건너뛸 수 있습니다.")

        print("-" * 40)
        return True

    def run_all_tests(self):
        """모든 테스트 실행"""
        self.start_time = datetime.now()

        print("🚀 조직 효과성 리포트 시스템 종합 테스트 시작")
        print(f"📅 시작 시간: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # 환경 확인
        if not self.check_dependencies():
            print("❌ 환경 확인 실패. 테스트를 중단합니다.")
            return

        # 테스트 스위트 정의
        test_suites = [
            {
                'file': 'test_backend_units.py',
                'description': '백엔드 로직 단위 테스트'
            },
            {
                'file': 'test_ui_automation.py',
                'description': 'Streamlit UI 자동화 테스트'
            },
            {
                'file': 'test_integration_workflows.py',
                'description': '통합 워크플로우 테스트'
            },
            {
                'file': 'test_performance_stability.py',
                'description': '성능 및 안정성 테스트'
            },
            {
                'file': 'test_error_handling.py',
                'description': '에러 처리 및 예외 상황 테스트'
            }
        ]

        # 각 테스트 스위트 실행
        for suite in test_suites:
            test_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), suite['file'])
            self.run_test_suite(test_file, suite['description'])

            # 각 테스트 간 잠시 대기
            time.sleep(1)

        self.end_time = datetime.now()

        # 최종 결과 요약
        self.print_summary()


def main():
    """메인 실행 함수"""
    runner = TestRunner()

    # 명령줄 인수 처리
    if len(sys.argv) > 1:
        if sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("📚 테스트 실행기 사용법:")
            print("python run_all_tests.py           # 모든 테스트 실행")
            print("python run_all_tests.py --help    # 도움말 표시")
            return

    try:
        runner.run_all_tests()
    except KeyboardInterrupt:
        print("\n\n⏹️ 사용자에 의해 테스트가 중단되었습니다.")
    except Exception as e:
        print(f"\n\n❌ 예상치 못한 오류가 발생했습니다: {e}")


if __name__ == "__main__":
    main()