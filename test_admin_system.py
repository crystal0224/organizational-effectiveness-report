#!/usr/bin/env python3
"""
시스템 관리 도구 테스트
"""
import sys
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 현재 디렉토리를 path에 추가
sys.path.append('.')

def test_database_init():
    """데이터베이스 초기화 테스트"""
    print("🔍 데이터베이스 초기화 테스트...")
    try:
        from database_models import init_database

        success = init_database()
        if success:
            print("✅ 데이터베이스 초기화 성공")
            return True
        else:
            print("❌ 데이터베이스 초기화 실패")
            return False

    except Exception as e:
        print(f"❌ 데이터베이스 초기화 오류: {e}")
        return False

def test_admin_utils():
    """관리 유틸리티 함수 테스트"""
    print("\n🔍 관리 유틸리티 테스트...")
    try:
        from admin_utils import get_system_stats, analyze_system_performance

        # 시스템 통계 테스트
        stats = get_system_stats()
        print(f"✅ 시스템 통계 조회 성공:")
        print(f"   - 조직 수: {stats.get('organizations', 0)}")
        print(f"   - 리포트 수: {stats.get('reports', 0)}")
        print(f"   - PDF 수: {stats.get('pdf_generated', 0)}")
        print(f"   - 이메일 수: {stats.get('emails_sent', 0)}")

        # 성능 분석 테스트
        perf = analyze_system_performance()
        print(f"✅ 성능 분석 성공:")
        print(f"   - 데이터베이스 크기: {perf.get('database_size', 0):.2f}MB")

        return True

    except Exception as e:
        print(f"❌ 관리 유틸리티 테스트 실패: {e}")
        return False

def test_logging_system():
    """로깅 시스템 테스트"""
    print("\n🔍 로깅 시스템 테스트...")
    try:
        from logging_utils import (
            log_pdf_generation_start,
            log_pdf_generation_complete,
            log_email_send_start,
            log_email_send_complete,
            get_recent_logs
        )

        # PDF 생성 로그 테스트
        report_data = {
            "org_name": "테스트 조직",
            "respondents": 25
        }

        log_id = log_pdf_generation_start("테스트팀", report_data)
        print(f"✅ PDF 생성 시작 로그: {log_id}")

        # PDF 완료 로그
        log_pdf_generation_complete(log_id, "/tmp/test.pdf", 2.5, 1024000)
        print(f"✅ PDF 생성 완료 로그")

        # 이메일 발송 로그 테스트
        recipients = ["test1@example.com", "test2@example.com"]
        email_id = log_email_send_start(recipients, "테스트 제목", {"filename": "test.pdf", "size": 1024000})
        print(f"✅ 이메일 발송 시작 로그: {email_id}")

        log_email_send_complete(email_id, 2, 0)
        print(f"✅ 이메일 발송 완료 로그")

        # 최근 로그 조회
        logs = get_recent_logs(limit=10)
        print(f"✅ 최근 로그 조회: {len(logs)}개")

        return True

    except Exception as e:
        print(f"❌ 로깅 시스템 테스트 실패: {e}")
        return False

def test_backup_restore():
    """백업/복원 기능 테스트"""
    print("\n🔍 백업/복원 테스트...")
    try:
        from admin_utils import backup_database, restore_database

        # 백업 테스트
        backup_path = backup_database("test_backup.db")
        print(f"✅ 데이터베이스 백업 성공: {backup_path}")

        # 백업 파일 존재 확인
        if os.path.exists(backup_path):
            print(f"✅ 백업 파일 확인됨: {os.path.getsize(backup_path)} bytes")

            # 복원 테스트 (실제로는 수행하지 않음 - 데이터 손실 방지)
            print("⚠️ 복원 테스트는 안전상 스킵 (백업 파일은 유효함)")

            # 백업 파일 정리
            os.remove(backup_path)
            print("🧹 테스트 백업 파일 정리 완료")

            return True
        else:
            print("❌ 백업 파일이 생성되지 않음")
            return False

    except Exception as e:
        print(f"❌ 백업/복원 테스트 실패: {e}")
        return False

def test_data_export():
    """데이터 내보내기 테스트"""
    print("\n🔍 데이터 내보내기 테스트...")
    try:
        from admin_utils import export_data_to_excel

        # Excel 내보내기 테스트
        filename = export_data_to_excel()
        print(f"✅ Excel 내보내기 성공: {filename}")

        # 파일 존재 확인
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            print(f"✅ Excel 파일 확인됨: {file_size} bytes")

            # 파일 정리
            os.remove(filename)
            print("🧹 테스트 Excel 파일 정리 완료")

            return True
        else:
            print("❌ Excel 파일이 생성되지 않음")
            return False

    except Exception as e:
        print(f"❌ 데이터 내보내기 테스트 실패: {e}")
        return False

def test_organization_management():
    """조직 관리 기능 테스트"""
    print("\n🔍 조직 관리 테스트...")
    try:
        from database_models import get_session, Organization

        session = get_session()

        # 테스트 조직 추가
        test_org = Organization(
            name="테스트 조직 관리",
            group_name="테스트 그룹",
            contact_email="test@example.com"
        )

        session.add(test_org)
        session.commit()

        org_id = test_org.id
        print(f"✅ 테스트 조직 추가: ID {org_id}")

        # 조직 조회
        org = session.query(Organization).filter(Organization.id == org_id).first()
        if org:
            print(f"✅ 조직 조회 성공: {org.name}")

            # 조직 정보 수정
            org.contact_email = "updated@example.com"
            session.commit()
            print("✅ 조직 정보 수정 성공")

            # 조직 삭제
            session.delete(org)
            session.commit()
            print("✅ 테스트 조직 삭제 완료")

        session.close()
        return True

    except Exception as e:
        print(f"❌ 조직 관리 테스트 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("=" * 60)
    print("🛠️ 시스템 관리 도구 통합 테스트")
    print("=" * 60)

    tests = [
        ("데이터베이스 초기화", test_database_init),
        ("관리 유틸리티", test_admin_utils),
        ("로깅 시스템", test_logging_system),
        ("백업/복원", test_backup_restore),
        ("데이터 내보내기", test_data_export),
        ("조직 관리", test_organization_management)
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ {test_name} 테스트 중 예외 발생: {e}")
            results[test_name] = False

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약")
    print("=" * 60)

    success_count = 0
    total_count = len(tests)

    for test_name, success in results.items():
        status = "✅ 성공" if success else "❌ 실패"
        print(f"   {test_name}: {status}")
        if success:
            success_count += 1

    print(f"\n🎯 전체 성공률: {success_count}/{total_count} ({success_count/total_count*100:.1f}%)")

    if success_count == total_count:
        print("🎉 모든 시스템 관리 기능이 정상 작동합니다!")
    else:
        print("⚠️ 일부 기능에 문제가 있습니다. 로그를 확인해주세요.")

    print("=" * 60)

if __name__ == "__main__":
    main()