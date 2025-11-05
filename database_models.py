# /Users/crystal/flask-report/database_models.py

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, LargeBinary, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

Base = declarative_base()

class Organization(Base):
    """조직 정보 테이블"""
    __tablename__ = 'organizations'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    group_name = Column(String(255))  # 그룹명 (상위 조직)
    contact_email = Column(String(255))
    branding_config = Column(Text)  # JSON 형태의 브랜딩 설정
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    reports = relationship("Report", back_populates="organization")
    branding_configs = relationship("BrandingConfig", back_populates="organization")


class Report(Base):
    """리포트 메타데이터 테이블"""
    __tablename__ = 'reports'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    team_name = Column(String(255))
    report_type = Column(String(50), default='organizational_effectiveness')
    file_path = Column(String(500))  # 원본 데이터 파일 경로
    report_data = Column(Text)  # JSON 형태의 리포트 데이터
    ai_analysis = Column(Text)  # JSON 형태의 AI 분석 결과
    status = Column(String(50), default='created')  # created, processing, completed, failed
    respondent_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    organization = relationship("Organization", back_populates="reports")
    pdf_generations = relationship("PDFGeneration", back_populates="report")
    email_logs = relationship("EmailLog", back_populates="report")


class PDFGeneration(Base):
    """PDF 생성 이력 테이블"""
    __tablename__ = 'pdf_generations'

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'))
    pdf_filename = Column(String(500))
    pdf_size = Column(Integer)  # 파일 크기 (bytes)
    generation_time = Column(Integer)  # 생성 시간 (seconds)
    status = Column(String(50), default='generating')  # generating, completed, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    report = relationship("Report", back_populates="pdf_generations")


class EmailLog(Base):
    """이메일 발송 로그 테이블"""
    __tablename__ = 'email_logs'

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=True)
    recipient_emails = Column(Text)  # JSON 배열 형태
    subject = Column(String(500))
    attachment_filename = Column(String(500))
    attachment_size = Column(Integer)
    status = Column(String(50), default='sending')  # sending, sent, failed
    sent_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    error_message = Column(Text)
    sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # 관계
    report = relationship("Report", back_populates="email_logs")


class BrandingConfig(Base):
    """조직별 브랜딩 설정 테이블"""
    __tablename__ = 'branding_configs'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'))
    config_name = Column(String(255), default='default')
    primary_color = Column(String(7), default='#0f4fa8')  # HEX 색상
    secondary_color = Column(String(7), default='#10b981')
    accent_color = Column(String(7), default='#f97316')
    logo_data = Column(LargeBinary)  # 로고 이미지 바이너리
    logo_filename = Column(String(255))
    font_family = Column(String(100), default='Inter')
    custom_css = Column(Text)  # 커스텀 CSS
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 관계
    organization = relationship("Organization", back_populates="branding_configs")


# 데이터베이스 설정
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./report_system.db')

def get_engine():
    """데이터베이스 엔진 생성"""
    if DATABASE_URL.startswith('sqlite'):
        engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    else:
        engine = create_engine(DATABASE_URL)
    return engine

def get_session():
    """데이터베이스 세션 생성"""
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()

def create_tables():
    """테이블 생성"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print("✅ 데이터베이스 테이블이 생성되었습니다.")

def init_database():
    """데이터베이스 초기화"""
    try:
        create_tables()

        # 기본 조직 데이터 생성 (있는 경우 스킵)
        session = get_session()
        if not session.query(Organization).first():
            default_org = Organization(
                name="샘플 조직",
                group_name="샘플 그룹",
                contact_email="admin@example.com"
            )
            session.add(default_org)
            session.commit()
            print("✅ 기본 조직 데이터가 생성되었습니다.")

        session.close()
        return True

    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        return False


if __name__ == "__main__":
    # 데이터베이스 초기화 실행
    init_database()