#!/usr/bin/env python3
"""
리포트 생성 기능을 직접 테스트하는 스크립트
"""

import pandas as pd
import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# streamlit_app에서 필요한 함수들 import
from streamlit_app import (
    extract_organization_info,
    group_data_by_unit,
    load_index,
    build_multiple_reports
)

def create_sample_data():
    """샘플 데이터 생성"""
    data = {
        'CMPNAME': ['SK텔레콤'] * 20,
        'POS': ['영업팀', '마케팅팀', '기술팀', 'HR팀', '재무팀'] * 4,
        'NO1': [3.5, 4.0, 3.8, 4.2, 3.9] * 4,
        'NO2': [3.2, 3.8, 4.1, 3.7, 4.0] * 4,
        'NO3': [4.0, 3.5, 3.9, 4.1, 3.6] * 4,
        'NO4': [3.7, 4.2, 3.4, 3.8, 4.0] * 4,
        'NO5': [3.9, 3.6, 4.0, 3.5, 3.8] * 4,
        'NO40': ['조직이 체계적이다', '소통이 원활하다', '성과 중심이다', '혁신적이다', '안정적이다'] * 4,
        'NO41': ['팀워크가 좋다', '전문성이 높다', '책임감이 강하다', '적응력이 뛰어나다', '성과가 우수하다'] * 4,
        'NO42': ['소통 개선 필요', '프로세스 개선', '인력 보강', '시스템 개선', '교육 강화'] * 4,
        'NO43': ['업무 과중', '리소스 부족', '의사소통 문제', '시스템 한계', '인력 부족'] * 4,
    }

    return pd.DataFrame(data)

def test_report_generation():
    """리포트 생성 테스트"""
    print("=== 리포트 생성 테스트 시작 ===")

    try:
        # 1. 샘플 데이터 생성
        print("1. 샘플 데이터 생성...")
        df = create_sample_data()
        print(f"   - 데이터 형태: {df.shape}")
        print(f"   - 컬럼: {list(df.columns)}")

        # 2. 조직 정보 추출
        print("2. 조직 정보 추출...")
        org_info = extract_organization_info(df)
        print(f"   - 회사명: {org_info['company']}")
        print(f"   - 부서/팀: {org_info['department']}")

        # 3. 전체 조직 리포트 생성 테스트
        print("3. 전체 조직 리포트 생성...")
        grouped_data = group_data_by_unit(df, "전체", None)
        print(f"   - 그룹 수: {len(grouped_data)}")
        print(f"   - 그룹 키: {list(grouped_data.keys())}")

        # 4. 인덱스 로드
        print("4. 인덱스 로드...")
        index_df = load_index()
        print(f"   - 인덱스 행 수: {len(index_df)}")

        # 5. 리포트 생성
        print("5. 리포트 생성...")
        reports = build_multiple_reports(
            grouped_data,
            index_df,
            org_info["company"],
            org_info["department"]
        )
        print(f"   - 생성된 리포트 수: {len(reports)}")
        print(f"   - 리포트 키: {list(reports.keys())}")

        # 6. 리포트 구조 확인
        if reports:
            first_report_key = list(reports.keys())[0]
            first_report = reports[first_report_key]
            print(f"6. 첫 번째 리포트 구조 ({first_report_key}):")
            print(f"   - 키들: {list(first_report.keys())}")

            if 'organization_name' in first_report:
                print(f"   - 조직명: {first_report['organization_name']}")
            if 'ipo_cards' in first_report:
                print(f"   - IPO 카드 수: {len(first_report['ipo_cards'])}")

        print("\n=== 리포트 생성 테스트 성공 ===")
        return True

    except Exception as e:
        print(f"\n=== 리포트 생성 테스트 실패 ===")
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_report_generation()
    sys.exit(0 if success else 1)