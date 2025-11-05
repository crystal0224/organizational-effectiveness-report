# /Users/crystal/flask-report/branding_manager.py

import yaml
import os
from typing import Dict, Any, Optional

class BrandingManager:
    """조직별 브랜딩 설정 관리 클래스"""

    def __init__(self, config_path: str = "branding_config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """브랜딩 설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"❌ 브랜딩 설정 파일을 찾을 수 없습니다: {self.config_path}")
            return self._get_default_config()
        except Exception as e:
            print(f"❌ 브랜딩 설정 파일 로드 실패: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """기본 브랜딩 설정 반환"""
        return {
            "default": {
                "name": "기본 브랜딩",
                "colors": {
                    "primary": "#0f4fa8",
                    "secondary": "#10b981",
                    "accent": "#f97316"
                },
                "fonts": {
                    "primary": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
                    "heading": "Inter, -apple-system, BlinkMacSystemFont, sans-serif"
                },
                "template_path": "templates/branding/default/"
            }
        }

    def get_branding_for_organization(self, org_name: str) -> Dict[str, Any]:
        """조직명을 기반으로 적절한 브랜딩 설정 반환"""
        if not org_name:
            return self.config.get("default", {})

        # 매칭 규칙 확인
        matching_rules = self.config.get("matching_rules", {})

        for keyword, branding_keys in matching_rules.items():
            if keyword == "*":
                continue

            if keyword.upper() in org_name.upper():
                for branding_key in branding_keys:
                    if branding_key in self.config:
                        return self.config[branding_key]

        # 기본값 반환
        return self.config.get("default", {})

    def get_css_variables(self, org_name: str) -> str:
        """조직별 CSS 변수 생성"""
        branding = self.get_branding_for_organization(org_name)
        colors = branding.get("colors", {})
        fonts = branding.get("fonts", {})

        css_vars = """
        <style>
        :root {
            --brand-primary: %(primary)s;
            --brand-secondary: %(secondary)s;
            --brand-accent: %(accent)s;
            --brand-font-primary: %(font_primary)s;
            --brand-font-heading: %(font_heading)s;
        }

        .brand-primary { color: var(--brand-primary) !important; }
        .brand-secondary { color: var(--brand-secondary) !important; }
        .brand-accent { color: var(--brand-accent) !important; }

        .bg-brand-primary { background-color: var(--brand-primary) !important; }
        .bg-brand-secondary { background-color: var(--brand-secondary) !important; }
        .bg-brand-accent { background-color: var(--brand-accent) !important; }

        .border-brand-primary { border-color: var(--brand-primary) !important; }
        .border-brand-secondary { border-color: var(--brand-secondary) !important; }
        .border-brand-accent { border-color: var(--brand-accent) !important; }

        .font-brand-primary { font-family: var(--brand-font-primary) !important; }
        .font-brand-heading { font-family: var(--brand-font-heading) !important; }
        </style>
        """ % {
            'primary': colors.get('primary', '#0f4fa8'),
            'secondary': colors.get('secondary', '#10b981'),
            'accent': colors.get('accent', '#f97316'),
            'font_primary': fonts.get('primary', 'Inter, sans-serif'),
            'font_heading': fonts.get('heading', 'Inter, sans-serif')
        }

        return css_vars

    def get_logo_info(self, org_name: str) -> Dict[str, str]:
        """조직별 로고 정보 반환"""
        branding = self.get_branding_for_organization(org_name)
        logo = branding.get("logo", {})

        return {
            "path": logo.get("path", ""),
            "alt": logo.get("alt", f"{org_name} 로고"),
            "exists": os.path.exists(logo.get("path", "")) if logo.get("path") else False
        }

    def apply_branding_to_template(self, template_content: str, org_name: str) -> str:
        """템플릿에 브랜딩 적용"""
        # CSS 변수 삽입
        css_vars = self.get_css_variables(org_name)

        # 로고 정보 가져오기
        logo_info = self.get_logo_info(org_name)

        # 템플릿 변수 치환
        branding_vars = {
            'BRANDING_CSS': css_vars,
            'LOGO_PATH': logo_info['path'],
            'LOGO_ALT': logo_info['alt'],
            'ORGANIZATION_NAME': org_name
        }

        result = template_content
        for key, value in branding_vars.items():
            result = result.replace(f"{{{{ {key} }}}}", str(value))

        return result

    def list_available_brandings(self) -> Dict[str, str]:
        """사용 가능한 브랜딩 목록 반환"""
        brandings = {}
        for key, value in self.config.items():
            if key != "matching_rules" and isinstance(value, dict):
                brandings[key] = value.get("name", key)
        return brandings


# 싱글톤 인스턴스
branding_manager = BrandingManager()


def get_branding_css(org_name: str) -> str:
    """조직별 브랜딩 CSS 반환 (편의 함수)"""
    return branding_manager.get_css_variables(org_name)


def apply_branding(template_content: str, org_name: str) -> str:
    """템플릿에 브랜딩 적용 (편의 함수)"""
    return branding_manager.apply_branding_to_template(template_content, org_name)


if __name__ == "__main__":
    # 테스트
    manager = BrandingManager()

    # 테스트용 조직명들
    test_orgs = ["SK텔레콤", "삼성전자", "LG전자", "일반회사"]

    for org in test_orgs:
        print(f"\n=== {org} ===")
        branding = manager.get_branding_for_organization(org)
        print(f"브랜딩: {branding.get('name', 'Unknown')}")
        print(f"주 색상: {branding.get('colors', {}).get('primary', 'Unknown')}")

    print(f"\n사용 가능한 브랜딩: {manager.list_available_brandings()}")