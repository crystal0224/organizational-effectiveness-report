#!/usr/bin/env python3
"""
PDF 병렬 처리 성능 테스트
"""
import sys
import os
import time
import pandas as pd
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 현재 디렉토리를 path에 추가
sys.path.append('.')

def create_test_reports(num_teams=8):
    """테스트용 리포트 데이터 생성"""
    try:
        # 간단한 모의 리포트 데이터 생성
        reports = {}

        for i in range(num_teams):
            team_name = f"팀_{i+1:02d}"

            # 간단한 리포트 구조 생성
            report = {
                "org_name": "테스트 조직",
                "team_name": team_name,
                "report_date": "2025-11-03",
                "respondents": 20 + i * 5,  # 팀별로 다른 응답자 수
                "ipo_cards": [
                    {
                        "id": "input",
                        "title": "Input (투입)",
                        "score": 3.5 + (i % 3) * 0.3,
                        "grade": "양호",
                        "desc": f"{team_name} 조직 자원 투입 상태"
                    },
                    {
                        "id": "process",
                        "title": "Process (과정)",
                        "score": 3.8 + (i % 4) * 0.2,
                        "grade": "우수",
                        "desc": f"{team_name} 업무 프로세스 효율성"
                    },
                    {
                        "id": "output",
                        "title": "Output (산출)",
                        "score": 4.0 + (i % 2) * 0.3,
                        "grade": "양호",
                        "desc": f"{team_name} 성과 달성도"
                    }
                ],
                "score_distribution": {
                    "labels": ["전략", "구조", "리더십", "협업", "소통", "성과", "몰입", "문화"],
                    "series": [
                        {"name": "벤치마크", "data": [3.5, 3.6, 3.4, 3.7, 3.5, 3.6, 3.8, 3.5]},
                        {"name": f"{team_name}", "data": [3.5 + (i*0.1)] * 8}
                    ]
                },
                "qualitative_responses": [
                    f"{team_name} 긍정적 피드백 1",
                    f"{team_name} 개선사항 제안 1",
                    f"{team_name} 추가 의견 1"
                ] * 5  # 15개 응답
            }

            reports[team_name] = report
            print(f"   ✅ {team_name}: {report['respondents']}개 응답")

        print(f"📋 생성된 팀 수: {len(reports)}개")
        return reports

    except Exception as e:
        print(f"❌ 테스트 리포트 생성 실패: {e}")
        return None

def test_parallel_performance():
    """병렬 처리 성능 테스트"""
    print("==" * 40)
    print("🚀 PDF 병렬 처리 성능 테스트")
    print("==" * 40)

    # 1. 테스트 리포트 생성
    print("\n1. 테스트 리포트 생성...")
    reports = create_test_reports(num_teams=8)  # 8개 팀으로 테스트

    if not reports:
        print("❌ 테스트 중단: 리포트 생성 실패")
        return

    print(f"✅ {len(reports)}개 리포트 생성 완료")

    # 2. 순차 처리 성능 테스트
    print("\n2. 순차 처리 성능 테스트...")
    try:
        from streamlit_app import generate_multiple_pdfs

        start_time = time.time()
        sequential_results = generate_multiple_pdfs(reports)
        sequential_time = time.time() - start_time

        print(f"   ⏱️ 순차 처리 시간: {sequential_time:.2f}초")
        print(f"   📋 생성된 PDF: {len(sequential_results)}개")

    except Exception as e:
        print(f"   ❌ 순차 처리 실패: {e}")
        sequential_time = None

    # 3. 병렬 처리 성능 테스트 (기본 설정)
    print("\n3. 병렬 처리 성능 테스트 (자동 설정)...")
    try:
        from streamlit_app import generate_multiple_pdfs_parallel

        start_time = time.time()
        parallel_results_auto = generate_multiple_pdfs_parallel(reports)
        parallel_time_auto = time.time() - start_time

        print(f"   ⏱️ 병렬 처리 시간 (자동): {parallel_time_auto:.2f}초")
        print(f"   📋 생성된 PDF: {len(parallel_results_auto)}개")

    except Exception as e:
        print(f"   ❌ 병렬 처리 (자동) 실패: {e}")
        parallel_time_auto = None

    # 4. 병렬 처리 성능 테스트 (수동 설정)
    print("\n4. 병렬 처리 성능 테스트 (수동 설정: 워커 4개, 배치 6개)...")
    try:
        start_time = time.time()
        parallel_results_manual = generate_multiple_pdfs_parallel(
            reports,
            max_workers=4,
            batch_size=6
        )
        parallel_time_manual = time.time() - start_time

        print(f"   ⏱️ 병렬 처리 시간 (수동): {parallel_time_manual:.2f}초")
        print(f"   📋 생성된 PDF: {len(parallel_results_manual)}개")

    except Exception as e:
        print(f"   ❌ 병렬 처리 (수동) 실패: {e}")
        parallel_time_manual = None

    # 5. 성능 비교 분석
    print("\n" + "==" * 40)
    print("📊 성능 분석 결과")
    print("==" * 40)

    if sequential_time and parallel_time_auto:
        speedup_auto = sequential_time / parallel_time_auto
        print(f"🔄 순차 처리: {sequential_time:.2f}초")
        print(f"⚡ 병렬 처리 (자동): {parallel_time_auto:.2f}초")
        print(f"🚀 성능 향상 (자동): {speedup_auto:.2f}배 빨라짐")

    if sequential_time and parallel_time_manual:
        speedup_manual = sequential_time / parallel_time_manual
        print(f"⚡ 병렬 처리 (수동): {parallel_time_manual:.2f}초")
        print(f"🚀 성능 향상 (수동): {speedup_manual:.2f}배 빨라짐")

    # 시스템 정보
    try:
        import psutil
        cpu_count = os.cpu_count()
        memory_gb = psutil.virtual_memory().total / (1024**3)
        print(f"\n💻 시스템 정보:")
        print(f"   CPU 코어: {cpu_count}개")
        print(f"   메모리: {memory_gb:.1f}GB")
        print(f"   현재 메모리 사용률: {psutil.virtual_memory().percent:.1f}%")
    except:
        pass

    print("\n✅ 성능 테스트 완료!")

if __name__ == "__main__":
    test_parallel_performance()