#!/usr/bin/env python3
"""
PDF 생성 및 시스템 로깅 유틸리티
"""
import json
import time
from datetime import datetime
from pathlib import Path
import logging
from typing import Dict, Any, Optional

# 로그 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('system.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def log_pdf_generation_start(team_name: str, report_data: Dict[str, Any]) -> str:
    """PDF 생성 시작 로그"""
    start_time = datetime.now()
    log_id = f"pdf_{team_name}_{start_time.strftime('%Y%m%d_%H%M%S')}"

    log_entry = {
        "log_id": log_id,
        "type": "pdf_generation",
        "status": "started",
        "team_name": team_name,
        "start_time": start_time.isoformat(),
        "respondent_count": report_data.get("respondents", 0),
        "organization": report_data.get("org_name", "Unknown")
    }

    logger.info(f"PDF 생성 시작: {log_id} - {team_name}")

    # 데이터베이스에 기록
    try:
        from database_models import get_session, PDFGeneration, Report

        session = get_session()

        # 해당 리포트 찾기 (새로 생성하거나 기존 것 사용)
        report = session.query(Report).filter(
            Report.team_name == team_name,
            Report.organization.has(name=report_data.get("org_name"))
        ).first()

        if not report:
            # 새 리포트 생성 로직은 여기서는 생략
            # 실제로는 먼저 리포트가 생성되어야 함
            pass
        else:
            pdf_gen = PDFGeneration(
                report_id=report.id,
                pdf_filename=f"{team_name}_report.pdf",
                status="generating"
            )
            session.add(pdf_gen)
            session.commit()
            log_entry["pdf_generation_id"] = pdf_gen.id

        session.close()

    except Exception as e:
        logger.error(f"PDF 생성 로그 DB 기록 실패: {e}")

    return log_id

def log_pdf_generation_complete(log_id: str, pdf_path: str, generation_time: float, pdf_size: int):
    """PDF 생성 완료 로그"""
    log_entry = {
        "log_id": log_id,
        "type": "pdf_generation",
        "status": "completed",
        "end_time": datetime.now().isoformat(),
        "generation_time": generation_time,
        "pdf_path": pdf_path,
        "pdf_size": pdf_size,
        "pdf_size_mb": pdf_size / (1024 * 1024)
    }

    logger.info(f"PDF 생성 완료: {log_id} - {generation_time:.2f}초, {pdf_size/1024:.1f}KB")

    # 데이터베이스 업데이트
    try:
        from database_models import get_session, PDFGeneration

        session = get_session()

        # 파일명으로 PDF 생성 레코드 찾기
        team_name = log_id.split("_")[1]
        pdf_gen = session.query(PDFGeneration).join(PDFGeneration.report).filter(
            PDFGeneration.status == "generating",
            PDFGeneration.report.has(team_name=team_name)
        ).first()

        if pdf_gen:
            pdf_gen.status = "completed"
            pdf_gen.pdf_filename = Path(pdf_path).name
            pdf_gen.pdf_size = pdf_size
            pdf_gen.generation_time = int(generation_time)
            session.commit()

        session.close()

    except Exception as e:
        logger.error(f"PDF 생성 완료 로그 DB 업데이트 실패: {e}")

def log_pdf_generation_error(log_id: str, error_message: str):
    """PDF 생성 실패 로그"""
    log_entry = {
        "log_id": log_id,
        "type": "pdf_generation",
        "status": "failed",
        "end_time": datetime.now().isoformat(),
        "error_message": error_message
    }

    logger.error(f"PDF 생성 실패: {log_id} - {error_message}")

    # 데이터베이스 업데이트
    try:
        from database_models import get_session, PDFGeneration

        session = get_session()

        team_name = log_id.split("_")[1]
        pdf_gen = session.query(PDFGeneration).join(PDFGeneration.report).filter(
            PDFGeneration.status == "generating",
            PDFGeneration.report.has(team_name=team_name)
        ).first()

        if pdf_gen:
            pdf_gen.status = "failed"
            pdf_gen.error_message = error_message
            session.commit()

        session.close()

    except Exception as e:
        logger.error(f"PDF 생성 실패 로그 DB 업데이트 실패: {e}")

def log_email_send_start(recipients: list, subject: str, attachment_info: Dict[str, Any] = None) -> str:
    """이메일 발송 시작 로그"""
    start_time = datetime.now()
    log_id = f"email_{start_time.strftime('%Y%m%d_%H%M%S')}"

    log_entry = {
        "log_id": log_id,
        "type": "email_send",
        "status": "sending",
        "start_time": start_time.isoformat(),
        "recipients": recipients,
        "recipient_count": len(recipients),
        "subject": subject,
        "attachment_info": attachment_info
    }

    logger.info(f"이메일 발송 시작: {log_id} - {len(recipients)}명에게 발송")

    # 데이터베이스에 기록
    try:
        from database_models import get_session, EmailLog

        session = get_session()

        email_log = EmailLog(
            recipient_emails=json.dumps(recipients),
            subject=subject,
            attachment_filename=attachment_info.get("filename") if attachment_info else None,
            attachment_size=attachment_info.get("size") if attachment_info else None,
            status="sending"
        )
        session.add(email_log)
        session.commit()

        log_entry["email_log_id"] = email_log.id
        session.close()

    except Exception as e:
        logger.error(f"이메일 발송 로그 DB 기록 실패: {e}")

    return log_id

def log_email_send_complete(log_id: str, sent_count: int, failed_count: int):
    """이메일 발송 완료 로그"""
    log_entry = {
        "log_id": log_id,
        "type": "email_send",
        "status": "completed",
        "end_time": datetime.now().isoformat(),
        "sent_count": sent_count,
        "failed_count": failed_count,
        "success_rate": (sent_count / (sent_count + failed_count)) * 100 if (sent_count + failed_count) > 0 else 0
    }

    logger.info(f"이메일 발송 완료: {log_id} - 성공: {sent_count}, 실패: {failed_count}")

    # 데이터베이스 업데이트
    try:
        from database_models import get_session, EmailLog

        session = get_session()

        # 최근 생성된 sending 상태의 로그 찾기
        email_log = session.query(EmailLog).filter(
            EmailLog.status == "sending"
        ).order_by(EmailLog.created_at.desc()).first()

        if email_log:
            email_log.status = "sent" if failed_count == 0 else "partial_failed"
            email_log.sent_count = sent_count
            email_log.failed_count = failed_count
            email_log.sent_at = datetime.utcnow()
            session.commit()

        session.close()

    except Exception as e:
        logger.error(f"이메일 발송 완료 로그 DB 업데이트 실패: {e}")

def log_email_send_error(log_id: str, error_message: str):
    """이메일 발송 실패 로그"""
    log_entry = {
        "log_id": log_id,
        "type": "email_send",
        "status": "failed",
        "end_time": datetime.now().isoformat(),
        "error_message": error_message
    }

    logger.error(f"이메일 발송 실패: {log_id} - {error_message}")

    # 데이터베이스 업데이트
    try:
        from database_models import get_session, EmailLog

        session = get_session()

        email_log = session.query(EmailLog).filter(
            EmailLog.status == "sending"
        ).order_by(EmailLog.created_at.desc()).first()

        if email_log:
            email_log.status = "failed"
            email_log.error_message = error_message
            session.commit()

        session.close()

    except Exception as e:
        logger.error(f"이메일 발송 실패 로그 DB 업데이트 실패: {e}")

def log_system_event(event_type: str, message: str, data: Dict[str, Any] = None):
    """시스템 이벤트 로그"""
    log_entry = {
        "type": "system_event",
        "event_type": event_type,
        "timestamp": datetime.now().isoformat(),
        "message": message,
        "data": data or {}
    }

    logger.info(f"시스템 이벤트: {event_type} - {message}")

def get_recent_logs(log_type: str = None, limit: int = 100) -> list:
    """최근 로그 조회"""
    try:
        from database_models import get_session, PDFGeneration, EmailLog

        session = get_session()
        logs = []

        if log_type is None or log_type == "pdf":
            # PDF 생성 로그
            pdf_logs = session.query(PDFGeneration).order_by(
                PDFGeneration.created_at.desc()
            ).limit(limit).all()

            for pdf_log in pdf_logs:
                logs.append({
                    "type": "pdf_generation",
                    "id": pdf_log.id,
                    "status": pdf_log.status,
                    "filename": pdf_log.pdf_filename,
                    "size_mb": (pdf_log.pdf_size / 1024 / 1024) if pdf_log.pdf_size else 0,
                    "generation_time": pdf_log.generation_time,
                    "created_at": pdf_log.created_at,
                    "error_message": pdf_log.error_message,
                    "report_info": {
                        "team_name": pdf_log.report.team_name if pdf_log.report else "Unknown",
                        "organization": pdf_log.report.organization.name if pdf_log.report and pdf_log.report.organization else "Unknown"
                    }
                })

        if log_type is None or log_type == "email":
            # 이메일 발송 로그
            email_logs = session.query(EmailLog).order_by(
                EmailLog.created_at.desc()
            ).limit(limit).all()

            for email_log in email_logs:
                logs.append({
                    "type": "email_send",
                    "id": email_log.id,
                    "status": email_log.status,
                    "subject": email_log.subject,
                    "recipient_count": len(json.loads(email_log.recipient_emails)) if email_log.recipient_emails else 0,
                    "sent_count": email_log.sent_count,
                    "failed_count": email_log.failed_count,
                    "sent_at": email_log.sent_at,
                    "created_at": email_log.created_at,
                    "error_message": email_log.error_message
                })

        session.close()

        # 시간순 정렬
        logs.sort(key=lambda x: x.get("created_at", datetime.min), reverse=True)

        return logs[:limit]

    except Exception as e:
        logger.error(f"로그 조회 실패: {e}")
        return []

class PerformanceTimer:
    """성능 측정 컨텍스트 매니저"""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        log_system_event("performance_start", f"{self.operation_name} 시작")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        if exc_type is None:
            log_system_event("performance_complete",
                           f"{self.operation_name} 완료",
                           {"duration_seconds": duration})
        else:
            log_system_event("performance_error",
                           f"{self.operation_name} 실패",
                           {"duration_seconds": duration, "error": str(exc_val)})

if __name__ == "__main__":
    # 테스트 실행
    print("로깅 시스템 테스트")

    # PDF 생성 로그 테스트
    log_id = log_pdf_generation_start("테스트팀", {"org_name": "테스트조직", "respondents": 25})
    time.sleep(1)  # 실제 작업 시뮬레이션
    log_pdf_generation_complete(log_id, "/tmp/test.pdf", 1.5, 524288)

    # 이메일 발송 로그 테스트
    email_id = log_email_send_start(["test@example.com"], "테스트 제목", {"filename": "test.pdf", "size": 524288})
    time.sleep(0.5)
    log_email_send_complete(email_id, 1, 0)

    # 최근 로그 조회
    recent_logs = get_recent_logs(limit=10)
    print(f"최근 로그 {len(recent_logs)}개 조회 완료")