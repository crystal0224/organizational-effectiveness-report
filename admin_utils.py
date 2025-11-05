#!/usr/bin/env python3
"""
시스템 관리 유틸리티 함수들
"""
import json
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import shutil
import zipfile
import os
from typing import Dict, List, Any, Optional

def get_system_stats() -> Dict[str, Any]:
    """시스템 전체 통계 정보 조회"""
    try:
        from database_models import get_session, Organization, Report, PDFGeneration, EmailLog

        session = get_session()

        # 기본 통계
        stats = {
            "organizations": session.query(Organization).count(),
            "reports": session.query(Report).count(),
            "pdf_generated": session.query(PDFGeneration).filter(PDFGeneration.status == 'completed').count(),
            "emails_sent": session.query(EmailLog).filter(EmailLog.status == 'sent').count(),
        }

        # 최근 30일 활동
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        stats["recent_reports"] = session.query(Report).filter(
            Report.created_at >= thirty_days_ago
        ).count()

        stats["recent_pdfs"] = session.query(PDFGeneration).filter(
            PDFGeneration.created_at >= thirty_days_ago
        ).count()

        stats["recent_emails"] = session.query(EmailLog).filter(
            EmailLog.created_at >= thirty_days_ago
        ).count()

        # 성능 통계
        pdf_generations = session.query(PDFGeneration).filter(
            PDFGeneration.status == 'completed',
            PDFGeneration.generation_time.isnot(None)
        ).all()

        if pdf_generations:
            generation_times = [p.generation_time for p in pdf_generations]
            stats["avg_pdf_generation_time"] = sum(generation_times) / len(generation_times)
            stats["total_pdf_size_mb"] = sum([p.pdf_size or 0 for p in pdf_generations]) / (1024 * 1024)
        else:
            stats["avg_pdf_generation_time"] = 0
            stats["total_pdf_size_mb"] = 0

        session.close()
        return stats

    except Exception as e:
        print(f"통계 조회 실패: {e}")
        return {}

def get_organization_details(org_id: int) -> Optional[Dict[str, Any]]:
    """특정 조직의 상세 정보 조회"""
    try:
        from database_models import get_session, Organization, Report

        session = get_session()
        org = session.query(Organization).filter(Organization.id == org_id).first()

        if not org:
            return None

        # 조직 기본 정보
        details = {
            "id": org.id,
            "name": org.name,
            "group_name": org.group_name,
            "contact_email": org.contact_email,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "branding_config": org.branding_config
        }

        # 관련 리포트 통계
        reports = session.query(Report).filter(Report.organization_id == org_id).all()
        details["reports"] = []

        for report in reports:
            report_info = {
                "id": report.id,
                "team_name": report.team_name,
                "report_type": report.report_type,
                "status": report.status,
                "respondent_count": report.respondent_count,
                "created_at": report.created_at,
                "pdf_count": len(report.pdf_generations),
                "email_count": len(report.email_logs)
            }
            details["reports"].append(report_info)

        session.close()
        return details

    except Exception as e:
        print(f"조직 상세 정보 조회 실패: {e}")
        return None

def backup_database(backup_path: str = None) -> str:
    """데이터베이스 백업"""
    try:
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"backup_report_system_{timestamp}.db"

        # SQLite 데이터베이스 백업
        db_path = "report_system.db"
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)
            return backup_path
        else:
            raise FileNotFoundError("데이터베이스 파일을 찾을 수 없습니다.")

    except Exception as e:
        raise Exception(f"데이터베이스 백업 실패: {e}")

def restore_database(backup_path: str) -> bool:
    """데이터베이스 복원"""
    try:
        if not os.path.exists(backup_path):
            raise FileNotFoundError("백업 파일을 찾을 수 없습니다.")

        # 현재 데이터베이스 백업 (안전장치)
        current_backup = f"before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_database(current_backup)

        # 백업에서 복원
        shutil.copy2(backup_path, "report_system.db")
        return True

    except Exception as e:
        print(f"데이터베이스 복원 실패: {e}")
        return False

def export_data_to_excel(org_id: int = None) -> str:
    """데이터를 Excel로 내보내기"""
    try:
        from database_models import get_session, Organization, Report, PDFGeneration, EmailLog

        session = get_session()

        # Excel 파일 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if org_id:
            org = session.query(Organization).filter(Organization.id == org_id).first()
            filename = f"export_{org.name}_{timestamp}.xlsx"
        else:
            filename = f"export_all_data_{timestamp}.xlsx"

        with pd.ExcelWriter(filename, engine='openpyxl') as writer:

            # 조직 데이터
            if org_id:
                orgs_query = session.query(Organization).filter(Organization.id == org_id)
            else:
                orgs_query = session.query(Organization)

            orgs = orgs_query.all()
            org_data = []
            for org in orgs:
                org_data.append({
                    "ID": org.id,
                    "조직명": org.name,
                    "그룹명": org.group_name,
                    "연락처": org.contact_email,
                    "생성일": org.created_at,
                    "수정일": org.updated_at
                })

            if org_data:
                pd.DataFrame(org_data).to_excel(writer, sheet_name='조직정보', index=False)

            # 리포트 데이터
            if org_id:
                reports_query = session.query(Report).filter(Report.organization_id == org_id)
            else:
                reports_query = session.query(Report)

            reports = reports_query.all()
            report_data = []
            for report in reports:
                report_data.append({
                    "ID": report.id,
                    "조직ID": report.organization_id,
                    "팀명": report.team_name,
                    "리포트타입": report.report_type,
                    "상태": report.status,
                    "응답자수": report.respondent_count,
                    "생성일": report.created_at,
                    "수정일": report.updated_at
                })

            if report_data:
                pd.DataFrame(report_data).to_excel(writer, sheet_name='리포트', index=False)

            # PDF 생성 이력
            if org_id:
                pdf_query = session.query(PDFGeneration).join(Report).filter(Report.organization_id == org_id)
            else:
                pdf_query = session.query(PDFGeneration)

            pdfs = pdf_query.all()
            pdf_data = []
            for pdf in pdfs:
                pdf_data.append({
                    "ID": pdf.id,
                    "리포트ID": pdf.report_id,
                    "파일명": pdf.pdf_filename,
                    "크기(MB)": (pdf.pdf_size or 0) / (1024 * 1024),
                    "생성시간(초)": pdf.generation_time,
                    "상태": pdf.status,
                    "생성일": pdf.created_at
                })

            if pdf_data:
                pd.DataFrame(pdf_data).to_excel(writer, sheet_name='PDF생성이력', index=False)

            # 이메일 발송 이력
            if org_id:
                email_query = session.query(EmailLog).join(Report).filter(Report.organization_id == org_id)
            else:
                email_query = session.query(EmailLog)

            emails = email_query.all()
            email_data = []
            for email in emails:
                email_data.append({
                    "ID": email.id,
                    "리포트ID": email.report_id,
                    "제목": email.subject,
                    "첨부파일": email.attachment_filename,
                    "상태": email.status,
                    "성공수": email.sent_count,
                    "실패수": email.failed_count,
                    "발송일": email.sent_at,
                    "생성일": email.created_at
                })

            if email_data:
                pd.DataFrame(email_data).to_excel(writer, sheet_name='이메일발송이력', index=False)

        session.close()
        return filename

    except Exception as e:
        raise Exception(f"Excel 내보내기 실패: {e}")

def clean_old_data(days: int = 90) -> Dict[str, int]:
    """오래된 데이터 정리"""
    try:
        from database_models import get_session, Report, PDFGeneration, EmailLog

        session = get_session()
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        # 정리될 데이터 수 계산
        old_reports = session.query(Report).filter(Report.created_at < cutoff_date)
        old_pdfs = session.query(PDFGeneration).filter(PDFGeneration.created_at < cutoff_date)
        old_emails = session.query(EmailLog).filter(EmailLog.created_at < cutoff_date)

        counts = {
            "reports": old_reports.count(),
            "pdfs": old_pdfs.count(),
            "emails": old_emails.count()
        }

        # 실제 삭제 (외래키 제약조건 고려하여 순서대로)
        old_emails.delete(synchronize_session=False)
        old_pdfs.delete(synchronize_session=False)
        old_reports.delete(synchronize_session=False)

        session.commit()
        session.close()

        return counts

    except Exception as e:
        print(f"데이터 정리 실패: {e}")
        return {"reports": 0, "pdfs": 0, "emails": 0}

def analyze_system_performance() -> Dict[str, Any]:
    """시스템 성능 분석"""
    try:
        from database_models import get_session, PDFGeneration, EmailLog
        import sqlite3

        session = get_session()

        # PDF 생성 성능 분석
        pdf_stats = session.query(PDFGeneration).filter(
            PDFGeneration.status == 'completed',
            PDFGeneration.generation_time.isnot(None)
        ).all()

        analysis = {
            "pdf_performance": {
                "total_generated": len(pdf_stats),
                "avg_time": 0,
                "min_time": 0,
                "max_time": 0,
                "total_size_mb": 0
            },
            "email_performance": {
                "total_sent": 0,
                "success_rate": 0,
                "avg_recipients": 0
            },
            "database_size": 0
        }

        if pdf_stats:
            times = [p.generation_time for p in pdf_stats if p.generation_time]
            sizes = [p.pdf_size for p in pdf_stats if p.pdf_size]

            analysis["pdf_performance"].update({
                "avg_time": sum(times) / len(times) if times else 0,
                "min_time": min(times) if times else 0,
                "max_time": max(times) if times else 0,
                "total_size_mb": sum(sizes) / (1024 * 1024) if sizes else 0
            })

        # 이메일 성능 분석
        email_stats = session.query(EmailLog).all()
        if email_stats:
            total_sent = sum([e.sent_count for e in email_stats])
            total_failed = sum([e.failed_count for e in email_stats])

            analysis["email_performance"].update({
                "total_sent": total_sent,
                "success_rate": (total_sent / (total_sent + total_failed)) * 100 if (total_sent + total_failed) > 0 else 0,
                "avg_recipients": total_sent / len(email_stats) if email_stats else 0
            })

        # 데이터베이스 크기
        try:
            db_path = "report_system.db"
            if os.path.exists(db_path):
                analysis["database_size"] = os.path.getsize(db_path) / (1024 * 1024)  # MB
        except:
            pass

        session.close()
        return analysis

    except Exception as e:
        print(f"성능 분석 실패: {e}")
        return {}

if __name__ == "__main__":
    # 테스트 실행
    print("시스템 통계:")
    stats = get_system_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n성능 분석:")
    perf = analyze_system_performance()
    print(f"  데이터베이스 크기: {perf.get('database_size', 0):.2f}MB")
    print(f"  평균 PDF 생성 시간: {perf.get('pdf_performance', {}).get('avg_time', 0):.2f}초")