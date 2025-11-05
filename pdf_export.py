# /Users/crystal/flask-report/pdf_export.py
from pathlib import Path
from playwright.sync_api import sync_playwright

def html_to_pdf_with_chrome(html: str, pdf_path: str, wait_until: str = "networkidle"):
    """
    Tailwind, Web Font, 이미지 등을 포함한 HTML을
    실제 Chromium 브라우저 엔진으로 렌더링 후 PDF로 저장한다.

    Parameters
    ----------
    html : str
        HTML 문자열 (Tailwind 포함)
    pdf_path : str
        출력될 PDF 경로
    wait_until : str, optional
        'load' | 'domcontentloaded' | 'networkidle'
        기본값은 'networkidle' (모든 리소스 로드 완료 시점)
    """
    pdf_path = Path(pdf_path)

    with sync_playwright() as p:
        # 고품질 렌더링을 위한 Chromium 설정 강화
        browser = p.chromium.launch(
            args=[
                "--no-sandbox",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",  # 렌더링 품질 향상
                "--force-color-profile=srgb",  # 색상 정확도
                "--disable-gpu-sandbox",  # GPU 가속
                "--disable-dev-shm-usage",  # 메모리 최적화
                "--no-first-run",
                "--disable-default-apps"
            ],
            headless=True
        )

        # 고해상도 페이지 생성
        page = browser.new_page(
            device_scale_factor=2.0,  # 고해상도 렌더링
            viewport={'width': 1920, 'height': 1080}  # 큰 뷰포트
        )

        # HTML 로드 (Tailwind CDN 및 웹폰트 로드 완료 대기)
        page.set_content(html, wait_until=wait_until)

        # 추가 대기 시간으로 폰트 로딩 보장
        page.wait_for_timeout(2000)  # 2초 추가 대기

        # 향상된 PDF 생성 옵션
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,  # Tailwind 배경색/도형 유지
            margin={
                "top": "15mm",
                "right": "15mm",
                "bottom": "18mm",
                "left": "15mm",
            },
            prefer_css_page_size=True,  # CSS @page 우선 적용
            display_header_footer=False,
            scale=1.0,  # 100% 크기 유지
        )

        browser.close()

    return pdf_path


if __name__ == "__main__":
    # 🔹 테스트 실행용 샘플
    sample_html = """
    <html>
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body class="bg-gray-50 text-gray-800 p-8">
        <h1 class="text-2xl font-bold mb-4">PDF Export Test</h1>
        <p>이 페이지는 Tailwind 스타일이 포함된 PDF 렌더링 테스트입니다.</p>
      </body>
    </html>
    """
    test_pdf = html_to_pdf_with_chrome(sample_html, "test_export.pdf")
    print(f"✅ PDF generated at: {test_pdf.resolve()}")
