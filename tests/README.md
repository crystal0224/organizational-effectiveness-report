# 🧪 조직 효과성 리포트 시스템 테스트 스위트

조직 효과성 리포트 생성 시스템의 종합적인 자동화 테스트 스위트입니다.

## 📋 테스트 구성

### 1. UI 자동화 테스트 (`test_ui_automation.py`)
- **목적**: Streamlit 인터페이스의 기능적 동작 검증
- **기술**: Selenium WebDriver + Chrome 헤드리스 모드
- **테스트 시나리오**:
  - 앱 로딩 및 기본 요소 확인
  - 사이드바 네비게이션 동작
  - 파일 업로드 인터페이스
  - 리포트 미리보기 기능
  - AI 분석 버튼 활성화
  - PDF 생성 인터페이스
  - 이메일 발송 인터페이스
  - 관리자 모드 접근
  - 반응형 디자인 (데스크탑/태블릿/모바일)
  - UI 에러 처리

### 2. 백엔드 단위 테스트 (`test_backend_units.py`)
- **목적**: 개별 함수와 모듈의 정확성 검증
- **기술**: pytest + Mock 패턴
- **테스트 영역**:
  - 데이터 처리 함수 (NO40 텍스트 추출, 파싱, 그룹핑)
  - AI 해석 생성 (성공/실패 케이스)
  - 이메일 발송 (SMTP 성공/실패, 검증)
  - PDF 생성 (Playwright 통합)
  - 데이터베이스 조작 (모델 임포트, 로그 생성)
  - 유틸리티 함수 (딕셔너리 접근, 파일 검증, 데이터 정제)

### 3. 통합 워크플로우 테스트 (`test_integration_workflows.py`)
- **목적**: 전체 사용자 시나리오의 종단간 검증
- **기술**: pytest + 실제 데이터 시뮬레이션
- **워크플로우**:
  - 완전한 리포트 생성 파이프라인
  - 팀별 PDF 생성 프로세스
  - 이메일 발송 워크플로우
  - 관리자 인증 및 권한 관리
  - 대용량 데이터 처리
  - AI 분석 통합 프로세스
  - 오류 복구 시나리오

### 4. 성능 및 안정성 테스트 (`test_performance_stability.py`)
- **목적**: 시스템의 성능 특성과 안정성 검증
- **기술**: psutil + 메모리/CPU 모니터링 + 동시성 테스트
- **측정 항목**:
  - 메모리 사용량 (대용량 데이터 처리)
  - CPU 사용률 (AI 분석 중)
  - 응답 시간 (리포트 생성)
  - 동시 사용자 처리 능력
  - 장시간 실행 안정성
  - 리소스 누수 검사
  - 확장성 테스트

### 5. 에러 처리 및 예외 상황 테스트 (`test_error_handling.py`)
- **목적**: 다양한 실패 시나리오에서의 복원력 검증
- **기술**: pytest + Mock + 예외 시뮬레이션
- **테스트 시나리오**:
  - 데이터 검증 오류 (잘못된 파일, 누락된 컬럼)
  - AI 서비스 오류 (API 연결/키/타임아웃)
  - 이메일 서비스 오류 (SMTP 연결/인증 실패)
  - PDF 생성 오류 (Playwright 실패, 템플릿 누락)
  - 데이터베이스 오류 (연결 실패, 트랜잭션 롤백)
  - 파일 시스템 오류 (권한 거부, 디스크 공간)
  - 네트워크 오류 (타임아웃, 연결 거부)
  - 메모리 오류 (대용량 데이터, 메모리 부족)
  - 동시성 오류 (파일 접근, 경쟁 상태)

## 🚀 실행 방법

### 전체 테스트 실행
```bash
cd /Users/crystal/flask-report/tests
python run_all_tests.py
```

### 개별 테스트 실행
```bash
# UI 자동화 테스트
pytest test_ui_automation.py -v

# 백엔드 단위 테스트
pytest test_backend_units.py -v

# 통합 워크플로우 테스트
pytest test_integration_workflows.py -v

# 성능 및 안정성 테스트
pytest test_performance_stability.py -v

# 에러 처리 테스트
pytest test_error_handling.py -v
```

## 📦 필수 의존성

### Python 패키지
```bash
pip install pytest pandas selenium requests psutil jinja2 playwright
```

### 시스템 요구사항
- **Chrome 브라우저**: UI 자동화 테스트용
- **ChromeDriver**: Selenium WebDriver용 (자동 설치 가능)
- **Playwright**: PDF 생성 테스트용
  ```bash
  playwright install chromium
  ```

## ⚙️ 설정 및 환경

### 환경 변수 (.env 파일)
```
GEMINI_API_KEY=your_gemini_api_key
ADMIN_PASSWORD=admin123
```

### Streamlit 앱 실행 (UI 테스트 전 필수)
```bash
# 메인 Streamlit 앱 실행
streamlit run streamlit_app.py

# Flask 앱도 함께 실행 (필요시)
python app.py
```

## 📊 테스트 결과 해석

### 성공 기준
- ✅ **PASSED**: 모든 검증 통과
- ❌ **FAILED**: 검증 실패, 버그 또는 환경 문제
- ⏭️ **SKIPPED**: 환경 의존성 부족으로 건너뛴 테스트

### 성능 벤치마크
- **메모리 사용량**: 대용량 데이터 처리 시 < 500MB
- **리포트 생성 시간**: 100명 응답 기준 < 30초
- **AI 분석 시간**: 평균 < 15초
- **PDF 생성 시간**: 팀당 < 10초

## 🔧 트러블슈팅

### 일반적인 문제

1. **Chrome WebDriver 오류**
   ```bash
   # ChromeDriver 자동 설치
   pip install webdriver-manager
   ```

2. **Streamlit 앱 연결 실패**
   - Streamlit 앱이 http://localhost:8501에서 실행 중인지 확인
   - 포트 충돌 시 다른 포트 사용

3. **AI API 오류**
   - GEMINI_API_KEY 환경 변수 설정 확인
   - API 할당량 및 키 유효성 검사

4. **메모리 부족 오류**
   - 대용량 테스트 시 시스템 메모리 확인
   - Docker 환경에서 메모리 제한 증가

## 📈 CI/CD 통합

### GitHub Actions 예시
```yaml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    - name: Install dependencies
      run: pip install -r requirements.txt
    - name: Run tests
      run: python tests/run_all_tests.py
```

## 🎯 테스트 철학

이 테스트 스위트는 **테스트 피라미드** 원칙을 따릅니다:

1. **단위 테스트 (70%)**: 빠르고 격리된 개별 기능 검증
2. **통합 테스트 (20%)**: 컴포넌트 간 상호작용 검증
3. **UI 테스트 (10%)**: 사용자 관점의 종단간 시나리오

### 품질 목표
- **테스트 커버리지**: 90% 이상
- **실행 시간**: 전체 스위트 5분 이내
- **안정성**: Flaky 테스트 0%
- **유지보수성**: 명확한 테스트 구조와 문서화

---

**🔄 마지막 업데이트**: 2024년 11월
**📧 문의**: 시스템 관리자에게 연락