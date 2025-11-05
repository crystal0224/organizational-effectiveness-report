# /Users/crystal/flask-report/app.py
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, send_file, Response

from jinja2 import Environment, BaseLoader

BASE_DIR = Path(__file__).resolve().parent
app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


# -------------------------------
# 1. 하드코드 리포트 (기존 그대로)
# -------------------------------
def get_report_data() -> dict:
    return {
        "org_name": "SK하이닉스 메모리사업부",
        "dept_name": "생산기술",
        "survey_date": "2025-10-20",
        "report_date": "2025-10-31",
        "respondents": 142,
        "summary": {
            "intro": "본 진단은 IPO 모델 기반으로 조직의 입력-프로세스-산출 전 영역을 점검하기 위해 수행되었습니다.",
            "sub_intro": "응답 규모가 충분하여 부서 단위/직위 단위 세부 비교가 가능합니다.",
            "respondents": 142,
            "response_rate": 92.9,
            "ipo": {"input": 3.9, "process": 4.2, "output": 4.1},
            "rating": "상",
            "improvement_priorities": [
                "중간관리자 피드백 체계 통일",
                "성과관리 프로세스 실행력 제고",
                "부서 간 협업 미팅 주기화",
            ],
            "score_chart_img": None,
            "organization_insight": "구성원들은 리더십과 협업 구조에는 대체로 만족하나, 성과관리의 일관성과 실행력에 대한 필요를 반복적으로 언급했습니다.",
            # AI 결과가 실제로는 Streamlit에서 꽂히지만, Flask 테스트용으로 비워둔다.
            "ai": {},
        },
        "overview": {
            "background": [
                "AI, 디지털 전환 등 외부 변화에 따라 조직운영의 민첩성이 강조되고 있음.",
                "기존 조직문화 진단으로는 실행 프로세스까지 식별이 어려워 별도 진단을 시행함.",
            ],
            "model_desc": "IPO(Input-Process-Output) + SKMS 운영 프레임을 결합해 설계",
            "model_points": [
                "Input: 전략/구조/역할",
                "Process: 리더십/협업/의사소통",
                "Output: 성과/몰입/지속가능성",
            ],
        },
        "diagnostic": {
            "categories": [
                {
                    "title": "리더십",
                    "name": "리더십",
                    "description": "방향 제시, 피드백, 코칭 등 리더 역할 수행 수준.",
                    "average": 4.2,
                    "items": [
                        {
                            "question": "우리 조직의 리더는 명확한 목표와 방향을 제시한다.",
                            "average": 4.3,
                            "benchmark": 4.0,
                            "responses": {
                                "veryLow": 2,
                                "low": 4,
                                "medium": 16,
                                "high": 58,
                                "veryHigh": 20,
                            },
                        },
                        {
                            "question": "리더는 성과에 대해 적시에 피드백한다.",
                            "average": 3.9,
                            "benchmark": 3.7,
                            "responses": {
                                "veryLow": 5,
                                "low": 10,
                                "medium": 30,
                                "high": 40,
                                "veryHigh": 15,
                            },
                        },
                    ],
                },
                {
                    "title": "조직문화",
                    "name": "조직문화",
                    "description": "협업과 의사소통, 상호신뢰 수준.",
                    "average": 3.8,
                    "items": [
                        {
                            "question": "의견을 자유롭게 제시할 수 있는 분위기이다.",
                            "average": 3.7,
                            "benchmark": 3.5,
                            "responses": {
                                "veryLow": 4,
                                "low": 10,
                                "medium": 28,
                                "high": 42,
                                "veryHigh": 16,
                            },
                        }
                    ],
                },
            ]
        },
        "open_ended": [
            {
                "title": "가장 시급한 개선과제",
                "answers": [
                    "중간관리자 리더십 역량 강화를 위한 교육 필요",
                    "성과관리 프로세스 일원화 및 시각화",
                    "현장과 본사 간 커뮤니케이션 주기 확대",
                ],
            }
        ],
        "appendix": {
            "methodology": "온라인 5점 리커트 + 주관식 2문항 + 기존 HR 데이터 연계로 구성.",
            "scoring_guide": "4.0 이상: 강점, 3.5~3.9: 유지, 3.4 이하: 개선 권고.",
            "recommendations": ["부서장 회의에서 결과 공유", "6개월 후 팔로업 진단", "리더십 교육과제에 본 결과 반영"],
        },
    }


# -------------------------------
# 2. 점수 분포 주입
# -------------------------------
def attach_score_distribution_from_report(report: dict) -> dict:
    report = report or {}
    report.setdefault("summary", {})

    diag = report.get("diagnostic") or {}
    categories = diag.get("categories") or []

    labels = []
    our_scores = []
    bm_scores = []

    for cat in categories:
        label = cat.get("title") or cat.get("name") or "-"
        avg = cat.get("average")
        labels.append(label)
        our_scores.append(float(avg) if avg is not None else 0.0)

        items = cat.get("items") or []
        if items and items[0].get("benchmark") is not None:
            bm_scores.append(float(items[0]["benchmark"]))
        else:
            bm_scores.append(max((float(avg) - 0.2) if avg is not None else 0.0, 0.0))

    report["summary"]["score_distribution"] = {
        "title": "진단 영역/항목별 점수 분포",
        "labels": labels,
        "series": [
            {"name": "benchmark", "data": bm_scores},
            {"name": "our", "data": our_scores},
        ],
    }
    return report


# -------------------------------
# 3. AI 플레이스홀더 치환 (Flask용)
# -------------------------------
def materialize_ai_placeholders_for_flask(ai_raw: dict | None, report: dict) -> dict | None:
    if not ai_raw:
        return ai_raw

    ctx = {
        "org_units": report.get("org_name") or report.get("dept_name") or "해당 조직",
        "industry_guess": (report.get("summary") or {}).get("industry_guess") or "",
        "no40_text": (report.get("summary") or {}).get("no40_text") or [],
        "no40_text_joined": ", ".join((report.get("summary") or {}).get("no40_text") or []),
    }
    env = Environment(loader=BaseLoader())
    hydrated = {}
    for k, v in ai_raw.items():
        if isinstance(v, str):
            try:
                hydrated[k] = env.from_string(v).render(**ctx)
            except Exception:
                hydrated[k] = v
        else:
            hydrated[k] = v
    return hydrated


# -------------------------------
# 4. 라우트
# -------------------------------
@app.route("/")
def index():
    report = get_report_data()
    # 점수분포 먼저
    report = attach_score_distribution_from_report(report)

    # Flask에서는 실제 AI 호출이 없으니, 예시 AI를 하나 만들어본다
    ai_result = {
        "org_context": "해당 조직은 메모리사업부 생산기술 조직으로, 제조 기반의 공정 안정성과 협업 체계를 동시에 요구받는 환경입니다.",
        "items": "IPO 관점에서 Input은 전략/역량 투입이 안정적인 편이며, Process에서는 리더십 실행과 의사소통 구조의 일관성이 중점 과제로 보입니다.",
        "writer": "생산기술 조직의 응답은 전반적으로 양호하나, 협업성과 공유 체계는 프로젝트 단위로 편차가 존재합니다.",
    }
    ai_result = materialize_ai_placeholders_for_flask(ai_result, report)

    return render_template(
        "report.html",
        report=report,
        ai_result=ai_result,
        use_tailwind=True,
    )


@app.route("/export/pdf")
def export_pdf():
    """
    현재 report.html 렌더 결과를 Playwright로 PDF로 변환해서 내려준다.
    """
    report = get_report_data()
    report = attach_score_distribution_from_report(report)

    ai_result = {
        "org_context": "해당 조직은 메모리사업부 생산기술 조직으로, 제조 기반의 공정 안정성과 협업 체계를 동시에 요구받는 환경입니다.",
        "items": "IPO 관점 핵심 해석: Input은 자원 투입이 충분하나, Process에서 실행력과 피드백 체계가 과제로 보입니다.",
        "writer": "조직 효과성은 양호 하나, 산출(Output)에서의 경험 일관성 확보가 필요합니다.",
    }
    ai_result = materialize_ai_placeholders_for_flask(ai_result, report)

    html = render_template(
        "report.html",
        report=report,
        ai_result=ai_result,
        use_tailwind=True,
    )

    org = report.get("org_name", "organization")
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"{org}_report_{ts}.pdf"

    try:
        from pdf_export import html_to_pdf_with_chrome
    except Exception as e:
        return Response(f"[pdf_export 로드 실패] {e}", status=500)

    try:
        out_path = BASE_DIR / "tmp_export.pdf"
        html_to_pdf_with_chrome(html, str(out_path))
        return send_file(
            out_path,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
            max_age=0,
        )
    except Exception as e:
        return Response(f"[PDF 생성 실패] {e}", status=500)


@app.route("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
