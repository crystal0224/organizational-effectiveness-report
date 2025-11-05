#!/usr/bin/env python3
"""
실제 조직 데이터로 AI 해석 기능 테스트
"""
import sys
import os
import pandas as pd
from dotenv import load_dotenv
import json

# .env 파일 로드
load_dotenv()

# 현재 디렉토리를 path에 추가
sys.path.append('.')

def load_test_data():
    """테스트용 SK하이닉스 데이터 로드"""
    try:
        df = pd.read_csv('test_sample.csv')
        print(f"✅ 테스트 데이터 로드 성공: {len(df)}개 응답")
        print(f"   조직명: {df['CMPNAME'].iloc[0] if len(df) > 0 else 'N/A'}")
        return df
    except Exception as e:
        print(f"❌ 테스트 데이터 로드 실패: {e}")
        return None

def create_mock_report(df):
    """테스트용 리포트 데이터 생성"""
    if df is None or len(df) == 0:
        return None

    # 조직 정보
    org_name = df['CMPNAME'].iloc[0] if len(df) > 0 else "테스트 조직"

    # 정량 데이터 계산 (NO1~NO39)
    numeric_cols = [f'NO{i}' for i in range(1, 40) if f'NO{i}' in df.columns]

    # IPO 점수 계산 (임시로 구간별 평균 계산)
    input_cols = numeric_cols[:13]  # NO1~NO13
    process_cols = numeric_cols[13:26]  # NO14~NO26
    output_cols = numeric_cols[26:]  # NO27~NO39

    input_score = df[input_cols].mean().mean() if input_cols else 4.0
    process_score = df[process_cols].mean().mean() if process_cols else 4.0
    output_score = df[output_cols].mean().mean() if output_cols else 4.0

    # 주관식 응답 수집
    qual_cols = ['NO40', 'NO41', 'NO42', 'NO43']  # 주관식 컬럼
    qualitative_data = []

    for col in qual_cols:
        if col in df.columns:
            responses = df[col].dropna().tolist()
            qualitative_data.extend([str(r) for r in responses if str(r) != 'nan'])

    # 리포트 구조 생성
    report = {
        "org_name": org_name,
        "report_date": "2025-11-03",
        "respondents": len(df),
        "ipo_cards": [
            {
                "id": "input",
                "title": "Input (투입)",
                "score": round(input_score, 1),
                "grade": "양호" if input_score >= 4.0 else "보통",
                "desc": f"조직 자원 투입 상태 평가 결과"
            },
            {
                "id": "process",
                "title": "Process (과정)",
                "score": round(process_score, 1),
                "grade": "우수" if process_score >= 4.0 else "보통",
                "desc": f"업무 프로세스 효율성 평가 결과"
            },
            {
                "id": "output",
                "title": "Output (산출)",
                "score": round(output_score, 1),
                "grade": "양호" if output_score >= 4.0 else "보통",
                "desc": f"성과 달성도 및 구성원 경험 평가 결과"
            }
        ],
        "score_distribution": {
            "labels": ["전략", "구조", "리더십", "협업", "소통", "성과", "몰입", "문화"],
            "series": [
                {"name": "벤치마크", "data": [3.5, 3.6, 3.4, 3.7, 3.5, 3.6, 3.8, 3.5]},
                {"name": "우리 조직", "data": [round(input_score, 1)] * 8}
            ]
        },
        "qualitative_responses": qualitative_data[:20]  # 상위 20개만
    }

    return report

def test_ai_interpretation(report):
    """AI 해석 기능 테스트"""
    try:
        from streamlit_app import run_ai_interpretation_gemini_from_report

        print("\n🤖 AI 해석 생성 시작...")
        print(f"   조직명: {report['org_name']}")
        print(f"   응답자 수: {report['respondents']}명")
        print(f"   Input 점수: {report['ipo_cards'][0]['score']}")
        print(f"   Process 점수: {report['ipo_cards'][1]['score']}")
        print(f"   Output 점수: {report['ipo_cards'][2]['score']}")

        # 진행 상황 콜백 함수
        def progress_callback(step, message):
            print(f"   📝 {step}: {message}")

        # AI 해석 실행
        ai_result = run_ai_interpretation_gemini_from_report(
            report,
            progress_update=progress_callback
        )

        if ai_result and 'writer' in ai_result:
            print("\n✅ AI 해석 생성 성공!")

            # 결과 요약 출력
            print("\n📊 AI 해석 결과 요약:")

            if 'org_context' in ai_result:
                print(f"\n🏢 조직 맥락 분석:")
                print(f"   {ai_result['org_context'][:150]}...")

            if 'score' in ai_result:
                print(f"\n📈 IPO 점수 해석:")
                print(f"   {ai_result['score'][:150]}...")

            if 'writer' in ai_result:
                print(f"\n📝 종합 분석 (임원용):")
                print(f"   {ai_result['writer'][:200]}...")

            # 전체 결과를 파일로 저장
            with open('ai_test_result.json', 'w', encoding='utf-8') as f:
                json.dump(ai_result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 전체 결과가 'ai_test_result.json'에 저장되었습니다.")

            return True
        else:
            print("❌ AI 해석 생성 실패: 결과가 비어있습니다.")
            print(f"   응답 내용: {ai_result}")
            return False

    except Exception as e:
        print(f"❌ AI 해석 테스트 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=" * 60)
    print("🧪 실제 조직 데이터로 AI 해석 기능 테스트")
    print("=" * 60)

    # 1. 테스트 데이터 로드
    print("\n1. 테스트 데이터 로드 중...")
    df = load_test_data()
    if df is None:
        print("❌ 테스트 중단: 데이터를 로드할 수 없습니다.")
        return

    # 2. 리포트 데이터 생성
    print("\n2. 리포트 데이터 생성 중...")
    report = create_mock_report(df)
    if report is None:
        print("❌ 테스트 중단: 리포트 데이터를 생성할 수 없습니다.")
        return

    # 3. AI 해석 테스트
    print("\n3. AI 해석 기능 테스트...")
    success = test_ai_interpretation(report)

    # 4. 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과:")
    print(f"   📁 데이터 로드: ✅ 성공 ({len(df)}개 응답)")
    print(f"   📋 리포트 생성: ✅ 성공")
    print(f"   🤖 AI 해석: {'✅ 성공' if success else '❌ 실패'}")

    if success:
        print("\n🎉 모든 테스트 통과! AI 해석 기능이 정상 작동합니다.")
        print("💡 'ai_test_result.json' 파일을 열어서 상세 결과를 확인해보세요.")
    else:
        print("\n⚠️ AI 해석 테스트 실패. 설정을 확인해주세요.")

    print("=" * 60)

if __name__ == "__main__":
    main()