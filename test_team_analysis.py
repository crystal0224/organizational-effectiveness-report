"""
팀별 분석 기능 테스트 스크립트
"""

import pandas as pd
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from streamlit_app import group_data_by_unit, build_multiple_reports, load_index

def test_team_grouping():
    """팀별 데이터 그룹핑 테스트"""
    print("\n=== 팀별 데이터 그룹핑 테스트 ===")

    # 샘플 데이터 로드
    df = pd.read_csv("team_sample_data.csv")
    print(f"전체 데이터: {len(df)}명")
    print(f"컬럼: {list(df.columns)}")

    # DEPT 컬럼 값 확인
    print(f"\n팀 구성:")
    for team, count in df['DEPT'].value_counts().items():
        print(f"  - {team}: {count}명")

    # 팀별 그룹핑 테스트
    grouped_data = group_data_by_unit(df, "팀별", "DEPT")
    print(f"\n그룹핑 결과:")
    print(f"  - 그룹 수: {len(grouped_data)}")
    print(f"  - 그룹 이름: {list(grouped_data.keys())}")

    for group_name, group_df in grouped_data.items():
        print(f"  - {group_name}: {len(group_df)}명")

    return grouped_data

def test_report_generation():
    """팀별 리포트 생성 테스트"""
    print("\n=== 팀별 리포트 생성 테스트 ===")

    # 샘플 데이터 로드
    df = pd.read_csv("team_sample_data.csv")

    # 팀별 그룹핑
    grouped_data = group_data_by_unit(df, "팀별", "DEPT")
    print(f"그룹핑 완료: {len(grouped_data)}개 팀")

    # 인덱스 로드
    index_df = load_index()
    print(f"인덱스 로드 완료: {len(index_df)}개 항목")

    # 리포트 생성
    reports = build_multiple_reports(
        grouped_data,
        index_df,
        detected_company_name="테스트 회사",
        detected_dept_name="테스트 부서"
    )

    print(f"\n리포트 생성 결과:")
    print(f"  - 생성된 리포트 수: {len(reports)}")
    print(f"  - 리포트 키: {list(reports.keys())}")

    # 각 리포트 구조 확인
    for team_name, report in reports.items():
        print(f"\n  [{team_name}] 리포트 구조:")
        print(f"    - organization_name: {report.get('organization_name', 'N/A')}")
        print(f"    - dept_name: {report.get('dept_name', 'N/A')}")
        print(f"    - is_total_organization: {report.get('is_total_organization', 'N/A')}")
        print(f"    - participant_info: {report.get('participant_info', {}).get('total_participants', 'N/A')}명")

    return reports

def test_dropdown_condition():
    """팀 선택 드롭다운 표시 조건 테스트"""
    print("\n=== 팀 선택 드롭다운 표시 조건 테스트 ===")

    # 샘플 데이터 로드
    df = pd.read_csv("team_sample_data.csv")
    grouped_data = group_data_by_unit(df, "팀별", "DEPT")
    index_df = load_index()
    reports = build_multiple_reports(grouped_data, index_df, "테스트 회사", "테스트 부서")

    # 드롭다운 표시 조건 확인
    print(f"\n리포트 개수: {len(reports)}")
    print(f"드롭다운 표시 조건: len(reports) > 1")
    print(f"드롭다운 표시 여부: {len(reports) > 1}")

    if len(reports) > 1:
        print("\n✅ 팀 선택 드롭다운이 표시되어야 합니다!")
        print(f"선택 가능한 팀: {', '.join(sorted(reports.keys()))}")
    else:
        print("\n❌ 리포트가 1개 이하라 드롭다운이 표시되지 않습니다.")

if __name__ == "__main__":
    print("=" * 50)
    print("팀별 분석 기능 테스트")
    print("=" * 50)

    # 샘플 데이터 파일 확인
    if not os.path.exists("team_sample_data.csv"):
        print("\n⚠️  team_sample_data.csv 파일이 없습니다.")
        print("test_team_data.py를 실행하여 샘플 데이터를 생성하세요:")
        print("  python test_team_data.py")
        sys.exit(1)

    try:
        # 테스트 실행
        grouped_data = test_team_grouping()
        reports = test_report_generation()
        test_dropdown_condition()

        print("\n" + "=" * 50)
        print("✅ 모든 테스트 완료!")
        print("=" * 50)

    except Exception as e:
        print(f"\n❌ 테스트 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()