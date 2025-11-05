#!/usr/bin/env python3
"""
Google Gemini API 연동 상태 테스트
"""
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def test_gemini_connection():
    """Gemini API 연결 테스트"""

    # 환경변수 확인
    api_key = os.getenv("GOOGLE_API_KEY")
    model = os.getenv("GENAI_MODEL", "gemini-2.5-flash")

    print("🔍 Gemini API 설정 확인:")
    print(f"   API 키: {'설정됨' if api_key else '❌ 미설정'}")
    print(f"   모델: {model}")

    if not api_key:
        print("❌ GOOGLE_API_KEY가 설정되지 않았습니다.")
        return False

    # google-genai 패키지 확인
    try:
        from google import genai
        print("✅ google-genai 패키지 설치됨")
    except ImportError:
        print("❌ google-genai 패키지가 설치되지 않았습니다.")
        try:
            import google.generativeai as genai_legacy
            print("✅ google-generativeai (레거시) 패키지 설치됨")
            return test_legacy_api(api_key, model)
        except ImportError:
            print("❌ Gemini 관련 패키지가 설치되지 않았습니다.")
            return False

    # 새로운 API 테스트
    try:
        print("\n🧪 새로운 google-genai API 테스트...")
        client = genai.Client(api_key=api_key)

        test_prompt = "안녕하세요! 간단한 응답 테스트입니다. '테스트 성공'이라고 답해주세요."

        response = client.models.generate_content(
            model=model,
            contents=test_prompt
        )

        result = response.text if hasattr(response, 'text') else str(response)
        print(f"✅ API 호출 성공!")
        print(f"   응답: {result[:100]}...")

        return True

    except Exception as e:
        print(f"❌ 새로운 API 실패: {str(e)}")
        print("\n🔄 레거시 API로 재시도...")
        return test_legacy_api(api_key, model)

def test_legacy_api(api_key, model):
    """레거시 google-generativeai API 테스트"""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        # 모델명 조정 (레거시 API는 다른 모델명 사용)
        legacy_model = "gemini-pro" if "2.5" in model else model.replace("2.5", "1.5")

        client = genai.GenerativeModel(legacy_model)

        test_prompt = "안녕하세요! 간단한 응답 테스트입니다. '테스트 성공'이라고 답해주세요."

        response = client.generate_content(test_prompt)

        result = response.text if hasattr(response, 'text') else str(response)
        print(f"✅ 레거시 API 호출 성공!")
        print(f"   사용 모델: {legacy_model}")
        print(f"   응답: {result[:100]}...")

        return True

    except Exception as e:
        print(f"❌ 레거시 API도 실패: {str(e)}")
        return False

def test_current_system():
    """현재 시스템의 AI 함수 테스트"""
    try:
        # streamlit_app.py의 call_gemini 함수 임포트
        import sys
        sys.path.append('.')

        from streamlit_app import call_gemini, _HAS_GENAI, GOOGLE_API_KEY

        print(f"\n🏗️ 현재 시스템 상태:")
        print(f"   _HAS_GENAI: {_HAS_GENAI}")
        print(f"   GOOGLE_API_KEY: {'설정됨' if GOOGLE_API_KEY else '❌ 미설정'}")

        if not _HAS_GENAI or not GOOGLE_API_KEY:
            print("❌ 현재 시스템이 AI 호출을 지원하지 않습니다.")
            return False

        print("\n🧪 현재 시스템 call_gemini 함수 테스트...")

        test_prompt = "안녕하세요! 간단한 응답 테스트입니다. '시스템 테스트 성공'이라고 답해주세요."

        result = call_gemini(test_prompt)

        if "[AI]" in result and "오류" in result:
            print(f"❌ 시스템 함수 실패: {result}")
            return False
        else:
            print(f"✅ 시스템 함수 성공!")
            print(f"   응답: {result[:100]}...")
            return True

    except Exception as e:
        print(f"❌ 시스템 함수 테스트 실패: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 Google Gemini API 연동 상태 테스트")
    print("=" * 60)

    # 1. 기본 연결 테스트
    connection_ok = test_gemini_connection()

    # 2. 현재 시스템 테스트
    system_ok = test_current_system()

    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약:")
    print(f"   🔗 API 연결: {'✅ 성공' if connection_ok else '❌ 실패'}")
    print(f"   🏗️ 시스템 함수: {'✅ 성공' if system_ok else '❌ 실패'}")

    if connection_ok and system_ok:
        print("\n🎉 모든 테스트 통과! AI 해석 기능이 정상 작동합니다.")
    else:
        print("\n⚠️ 일부 테스트 실패. AI 해석 기능에 문제가 있을 수 있습니다.")
    print("=" * 60)