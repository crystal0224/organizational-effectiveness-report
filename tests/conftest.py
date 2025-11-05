"""
Test configuration and fixtures
"""
import pytest
import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By


@pytest.fixture(scope="session")
def streamlit_url():
    """Streamlit app URL for testing"""
    return "http://localhost:8501"


@pytest.fixture(scope="session")
def chrome_driver():
    """Chrome WebDriver instance for UI testing"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 백그라운드 실행
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")

    # ChromeDriver 경로 설정 (시스템에 설치된 경우)
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.implicitly_wait(10)
        yield driver
        driver.quit()
    except Exception as e:
        pytest.skip(f"Chrome driver not available: {e}")


@pytest.fixture
def wait_for_element(chrome_driver):
    """Element를 기다리는 헬퍼 함수"""
    def _wait(locator, timeout=10):
        return WebDriverWait(chrome_driver, timeout).until(
            EC.presence_of_element_located(locator)
        )
    return _wait


@pytest.fixture
def sample_excel_file():
    """테스트용 샘플 Excel 파일 생성"""
    # 실제 조직효과성 데이터 구조 모방
    data = {
        'Q1': [4, 3, 5, 4, 3] * 20,  # 100개 응답
        'Q2': [3, 4, 4, 5, 3] * 20,
        'Q3': [5, 4, 3, 4, 5] * 20,
        'NO40': ['혁신적인 조직', '협력적 문화', '성장 지향', '안정적 환경', '도전적 분위기'] * 20,
        'NO41': ['팀워크 좋음', '소통 원활', '업무 효율성', '리더십 우수', '학습 문화'] * 20,
        'NO42': ['의사소통 개선', '프로세스 정비', '인력 충원', '교육 강화', '시스템 개선'] * 20,
        'NO43': ['시간 부족', '자원 제약', '절차 복잡', '정보 부족', '권한 제한'] * 20,
        'TEAM': ['A팀', 'B팀', 'C팀', 'D팀', 'E팀'] * 20
    }

    df = pd.DataFrame(data)

    # 임시 파일 생성
    temp_file = "/tmp/test_organizational_data.xlsx"
    df.to_excel(temp_file, index=False)

    yield temp_file

    # 정리
    if os.path.exists(temp_file):
        os.remove(temp_file)


@pytest.fixture
def streamlit_app_running(streamlit_url):
    """Streamlit 앱이 실행 중인지 확인"""
    import requests
    try:
        response = requests.get(streamlit_url, timeout=5)
        if response.status_code == 200:
            return True
    except:
        pass
    pytest.skip("Streamlit app is not running. Please start it with: streamlit run streamlit_app.py")


@pytest.fixture
def clean_session_state():
    """각 테스트 전후로 세션 상태 정리"""
    # 테스트 전 설정
    yield
    # 테스트 후 정리 (필요한 경우)


class TestHelper:
    """테스트 헬퍼 클래스"""

    @staticmethod
    def wait_for_streamlit_load(driver, timeout=30):
        """Streamlit 앱이 완전히 로드될 때까지 대기"""
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(2)  # 추가 안정화 시간

    @staticmethod
    def find_element_by_text(driver, text, tag="*"):
        """텍스트로 요소 찾기"""
        return driver.find_element(By.XPATH, f"//{tag}[contains(text(), '{text}')]")

    @staticmethod
    def upload_file(driver, file_input_element, file_path):
        """파일 업로드 헬퍼"""
        file_input_element.send_keys(file_path)
        time.sleep(2)  # 업로드 처리 대기


@pytest.fixture
def test_helper():
    """테스트 헬퍼 클래스 인스턴스"""
    return TestHelper()