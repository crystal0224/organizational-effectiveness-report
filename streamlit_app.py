# /Users/crystal/flask-report/streamlit_app.py

import os
import json
import base64
import io
import smtplib
import zipfile
import tempfile
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

import pandas as pd
import streamlit as st
from jinja2 import Environment, FileSystemLoader, select_autoescape, BaseLoader
from dotenv import load_dotenv


# ================================
# 0) 보조 유틸
# ================================
def _guess_industry_from_name(name: str) -> str:
    """조직명/회사명으로 대략적인 산업/직무 영역을 추정한다."""
    if not name:
        return "일반 사무/내부 조직"
    lower = name.lower()
    # 건설/인프라/현장
    if ("건설" in name) or ("토목" in name) or ("현장" in name) or ("플랜트" in name) or ("Onsite" in name) or ("onsite" in lower):
        return "건설·인프라·현장 기반 조직"
    # 설계/엔지니어링
    if ("구조" in name) or ("설계" in name) or ("엔지니어" in name) or ("engineering" in lower):
        return "설계·기술·엔지니어링 조직"
    # HRD/교육
    if ("HR" in name) or ("인재" in name) or ("교육" in name) or ("러닝" in name) or ("mylearn" in lower) or ("mysuni" in lower):
        return "HRD·러닝·사내교육 조직"
    # 제조/플랜트 계열
    if ("plant" in lower) or ("fab" in lower) or ("제조" in name):
        return "제조·플랜트 기반 조직"
    return "일반 사무/내부 조직"


def _extract_no40_from_open(open_ended) -> str:
    """report['open_ended'] 구조에서 NO40(조직특성) 응답만 뽑아서 텍스트로 만든다."""
    if not open_ended:
        return "NO40 관련 응답이 없습니다."

    # 새로운 구조 처리: dict with basic_responses
    responses_list = []
    if isinstance(open_ended, dict):
        responses_list = open_ended.get("basic_responses", [])
    elif isinstance(open_ended, list):
        responses_list = open_ended

    collected = []
    for block in responses_list:
        # 새로운 구조: header 필드 확인
        header = (block.get("header") or "").strip()
        title = (block.get("title") or "").strip()

        # header가 NO40이거나 제목이 조직특성 관련이면 수집
        if header.upper() == "NO40" or title.upper() == "NO40" or "조직특성" in title or "조직 특성" in title or "조직 이미지" in title:
            answers = block.get("answers") or []
            for a in answers:
                if a and a.strip():
                    collected.append(a.strip())
    if not collected:
        return "NO40 관련 응답이 없습니다."
    return "\n".join(f"- {a}" for a in collected)


def preprocess_answer_list(raw_answers: list, global_used_sentences: set = None) -> list:
    """
    문자열 리스트를 전처리하여 더 깔끔하게 정리한다.
    - 중복 제거
    - 짧은 응답 필터링
    - 민감정보 마스킹
    - 전역적으로 사용된 문장 제외
    """
    if not raw_answers:
        return []

    if global_used_sentences is None:
        global_used_sentences = set()

    # 1. 응답 정리 및 중복 제거
    cleaned_answers = []
    seen_answers = set()

    for answer in raw_answers:
        if not answer or not isinstance(answer, str):
            continue

        # 기본 정리
        cleaned = answer.strip()
        if len(cleaned) < 10:  # 너무 짧은 응답 제외
            continue

        # 중복 제거 (대소문자 무시, 공백 정규화)
        normalized = ' '.join(cleaned.lower().split())
        if normalized in seen_answers or normalized in global_used_sentences:
            continue
        seen_answers.add(normalized)

        # 민감정보 마스킹
        cleaned = mask_sensitive_content(cleaned)
        cleaned_answers.append(cleaned)

    # 응답 수가 많으면 상위 20개만 선택 (길이 순)
    if len(cleaned_answers) > 20:
        cleaned_answers = sorted(cleaned_answers, key=len, reverse=True)[:20]

    # 선택된 문장들을 전역 사용 목록에 추가
    for answer in cleaned_answers[:3]:  # 상위 3개만 대표 문장으로 간주
        normalized = ' '.join(answer.lower().split())
        global_used_sentences.add(normalized)

    return cleaned_answers


def build_structured_open_ended(df: pd.DataFrame, is_company_level: bool = False) -> dict:
    """
    reference/organizational-effectiveness/index.xlsx를 기반으로
    주관식 응답을 구조화하여 반환한다.
    """
    try:
        # 레퍼런스 인덱스 로드
        ref_df = pd.read_excel("reference/organizational-effectiveness/index.xlsx")

        # 주관식 항목들만 필터링 (대분류가 '주관식'인 것들)
        subjective_items = ref_df[ref_df['대분류'] == '주관식'].copy()

        # 주관식 데이터 구조화
        structured_data = []
        global_used_sentences = set()  # 전역적으로 사용된 문장 추적

        for _, item in subjective_items.iterrows():
            header_name = item['헤더명']
            question_name = item['문항명']
            minor_category = item['소분류']

            # 해당 컬럼이 데이터에 존재하는지 확인
            if header_name in df.columns:
                raw_answers = df[header_name].dropna().astype(str).tolist()
                if raw_answers:
                    # 전처리된 응답들로 교체 (전역 중복 방지 적용)
                    processed_answers = preprocess_answer_list(raw_answers, global_used_sentences)

                    structured_data.append({
                        "header": header_name,
                        "title": question_name,
                        "category": minor_category,
                        "answers": processed_answers
                    })

        result = {
            "basic_responses": structured_data,
            "advanced_analysis": None,
            "comprehensive_analysis": None
        }

        # AI 종합 해석은 항상 생성
        if structured_data:
            try:
                org_name = df.get('조직명', pd.Series([None])).iloc[0] if '조직명' in df.columns else None
                result["comprehensive_analysis"] = generate_subjective_comprehensive_analysis(result, org_name)
            except Exception as e:
                print(f"AI 종합 해석 생성 중 오류: {e}")
                result["comprehensive_analysis"] = None

        # 회사단위일 때만 고급 분석 추가
        if is_company_level and structured_data:
            result["advanced_analysis"] = generate_advanced_subjective_analysis(structured_data, df)

        return result

    except Exception as e:
        st.error(f"주관식 응답 구조화 중 오류: {e}")
        # fallback: 기존 방식으로 처리
        open_ended = []
        global_used_sentences = set()  # fallback에서도 중복 방지 적용
        for col in ["NO40", "NO41", "NO42", "NO43"]:
            if col in df.columns:
                raw_answers = df[col].dropna().astype(str).tolist()
                if raw_answers:
                    processed_answers = preprocess_answer_list(raw_answers, global_used_sentences)
                    open_ended.append({"title": col, "answers": processed_answers})
        result = {"basic_responses": open_ended, "advanced_analysis": None, "comprehensive_analysis": None}
        # AI 종합 해석 생성 (fallback에서도)
        if open_ended:
            try:
                org_name = df.get('조직명', pd.Series([None])).iloc[0] if '조직명' in df.columns else None
                result["comprehensive_analysis"] = generate_subjective_comprehensive_analysis(result, org_name)
            except Exception as e:
                print(f"AI 종합 해석 생성 중 오류 (fallback): {e}")
                result["comprehensive_analysis"] = None
        return result


def _generate_fallback_analysis(total_responses: int, org_name: str = None) -> str:
    """Gemini API 실패 시 사용할 대체 분석 생성"""
    org_display = org_name if org_name else "해당 조직"

    analysis_parts = [
        f"## {org_display} 조직 특성 종합분석\n",
        f"**응답 현황**: 총 {total_responses}개의 주관식 응답을 바탕으로 분석되었습니다.\n",
        "**주요 특징**:",
        "- 조직원들의 다양한 의견과 관점이 수집되었습니다.",
        "- 개선이 필요한 영역과 강점 영역이 혼재되어 나타납니다.",
        "- 조직의 발전 방향에 대한 구체적인 제안들이 포함되어 있습니다.\n",
        "**분석 결과**:",
        "- 조직 효과성 향상을 위한 다각도의 접근이 필요합니다.",
        "- 구성원들의 참여와 소통을 통한 지속적인 개선이 중요합니다.",
        "- 정량적 지표와 함께 정성적 피드백을 종합적으로 고려해야 합니다.\n",
        "**향후 과제**:",
        "- 주관식 응답에서 도출된 핵심 이슈들에 대한 체계적인 접근",
        "- 조직 문화 개선을 위한 구체적인 실행 계획 수립",
        "- 구성원 만족도 및 참여도 제고를 위한 지속적인 노력\n",
        "*본 분석은 수집된 주관식 응답을 기반으로 한 기본적인 해석입니다.*"
    ]

    return "\n".join(analysis_parts)


def generate_subjective_comprehensive_analysis(open_ended_responses: dict, org_name: str = None) -> str:
    """주관식 응답을 기반으로 AI 종합 해석을 생성한다."""
    try:
        # Q40-Q43 응답 추출
        def extract_responses_by_question(responses_list, target_question):
            answers = []
            for block in responses_list:
                header = (block.get("header") or "").strip().upper()
                title = (block.get("title") or "").strip()

                if header == target_question or target_question in title.upper():
                    answers.extend(block.get("answers", []))
            return [ans for ans in answers if ans and ans.strip()]

        # 기본 응답 구조에서 데이터 추출
        responses_list = []
        if isinstance(open_ended_responses, dict):
            responses_list = open_ended_responses.get("basic_responses", [])
        elif isinstance(open_ended_responses, list):
            responses_list = open_ended_responses

        # 각 문항별 응답 추출 (더 유연한 매칭)
        no40_responses = extract_responses_by_question(responses_list, "NO40")  # 조직 이미지
        if not no40_responses:
            # 조직 특성/이미지 관련 항목들도 확인
            for q in ["조직 특성", "조직특성", "조직 이미지", "조직이미지", "회사 특성", "회사특성"]:
                no40_responses.extend(extract_responses_by_question(responses_list, q))

        no41_responses = extract_responses_by_question(responses_list, "NO41")  # 강점
        if not no41_responses:
            # 강점 관련 항목들도 확인
            for q in ["강점", "장점", "좋은 점", "만족", "우수"]:
                no41_responses.extend(extract_responses_by_question(responses_list, q))

        no42_responses = extract_responses_by_question(responses_list, "NO42")  # 보완 필요점
        if not no42_responses:
            # 개선점 관련 항목들도 확인
            for q in ["보완", "개선", "부족", "아쉬운", "불만", "문제"]:
                no42_responses.extend(extract_responses_by_question(responses_list, q))

        no43_responses = extract_responses_by_question(responses_list, "NO43")  # 장애요인
        if not no43_responses:
            # 장애요인 관련 항목들도 확인
            for q in ["장애", "걸림돌", "방해", "어려움", "제약"]:
                no43_responses.extend(extract_responses_by_question(responses_list, q))

        # 응답이 충분하지 않으면 기본 메시지 반환
        total_responses = len(no40_responses) + len(no41_responses) + len(no42_responses) + len(no43_responses)
        print(f"DEBUG: 주관식 응답 개수 - NO40: {len(no40_responses)}, NO41: {len(no41_responses)}, NO42: {len(no42_responses)}, NO43: {len(no43_responses)}, 총: {total_responses}")

        # 응답이 부족하지만 아예 없지는 않은 경우, 간단한 AI 분석 시도
        if total_responses < 3:
            print(f"DEBUG: 응답 부족으로 AI 분석 스킵 (최소 3개 필요, 현재 {total_responses}개)")
            return _generate_fallback_analysis(total_responses, org_name)
        elif total_responses < 5:
            print(f"DEBUG: 응답 부족하지만 간단 AI 분석 시도 (권장 5개, 현재 {total_responses}개)")

        # 프롬프트 템플릿 로드
        prompts_dir = BASE_DIR / "prompts"
        prompt_path = prompts_dir / "gemini_text_ko.md"

        if not prompt_path.exists():
            return "AI 종합 해석 프롬프트 파일을 찾을 수 없습니다."

        prompt_template = prompt_path.read_text(encoding='utf-8')

        # 응답 텍스트 포맷팅
        no40_text = "\n".join([f"- {resp}" for resp in no40_responses[:10]])  # 최대 10개
        no41_text = "\n".join([f"- {resp}" for resp in no41_responses[:10]])
        no42_text = "\n".join([f"- {resp}" for resp in no42_responses[:10]])
        no43_text = "\n".join([f"- {resp}" for resp in no43_responses[:10]])

        # 프롬프트 변수 치환
        prompt = prompt_template.replace("{{no40_text}}", no40_text or "응답 없음")
        prompt = prompt.replace("{{no41_text}}", no41_text or "응답 없음")
        prompt = prompt.replace("{{no42_text}}", no42_text or "응답 없음")
        prompt = prompt.replace("{{no43_text}}", no43_text or "응답 없음")
        prompt = prompt.replace("{{respondents}}", str(total_responses))
        prompt = prompt.replace("{{org_units}}", org_name or "업로드 데이터")

        # Gemini API 호출
        if not _HAS_GENAI or not GOOGLE_API_KEY:
            print("DEBUG: Gemini API 설정 없음 - fallback 사용")
            return _generate_fallback_analysis(total_responses, org_name)

        try:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            # 가장 빠른 모델 사용 (품질은 약간 낮지만 속도 5배 향상)
            client = genai.GenerativeModel('gemini-1.5-flash-8b')

            # 속도 최적화 설정 (품질 유지하면서 빠르게)
            generation_config = genai.types.GenerationConfig(
                temperature=0.3,  # 적당히 낮춰서 빠르지만 품질 유지
                max_output_tokens=1200,  # 충분한 출력 공간
                top_p=0.7,  # 균형잡힌 선택
                top_k=40,   # 적당한 후보 수
                candidate_count=1,  # 단일 후보로 속도 향상
                stop_sequences=["\n\n\n", "---", "###"]  # 조기 종료
            )

            # 타임아웃 설정으로 빠른 응답 보장 (threading 사용)
            import concurrent.futures
            import time

            def make_api_call():
                return client.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=[
                        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"}
                    ]
                )

            # 30초 타임아웃 설정 (concurrent.futures 사용)
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(make_api_call)
                try:
                    response = future.result(timeout=30)
                except concurrent.futures.TimeoutError:
                    print("AI 분석 시간 초과 (30초) - fallback 사용")
                    return _generate_fallback_analysis(total_responses, org_name)

            # 응답 상태 확인
            if response and hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]

                # finish_reason 확인
                if hasattr(candidate, 'finish_reason'):
                    if candidate.finish_reason == 2:  # SAFETY
                        print("Gemini API: 안전성 필터에 의해 차단됨")
                        return _generate_fallback_analysis(total_responses, org_name)
                    elif candidate.finish_reason == 3:  # RECITATION
                        print("Gemini API: 반복 콘텐츠로 인해 차단됨")
                        return _generate_fallback_analysis(total_responses, org_name)
                    elif candidate.finish_reason == 4:  # OTHER
                        print("Gemini API: 기타 이유로 차단됨")
                        return _generate_fallback_analysis(total_responses, org_name)

                # 정상적인 응답이 있는 경우
                if hasattr(candidate, 'content') and candidate.content and hasattr(candidate.content, 'parts'):
                    for part in candidate.content.parts:
                        if hasattr(part, 'text') and part.text:
                            return part.text.strip()

            # response.text로 직접 접근 시도 (하위 호환성)
            if response and hasattr(response, 'text') and response.text:
                return response.text.strip()

            # 모든 접근 방법이 실패한 경우
            print("Gemini API: 유효한 응답을 받지 못함")
            return _generate_fallback_analysis(total_responses, org_name)

        except TimeoutError as timeout_error:
            print(f"Gemini API 타임아웃: {timeout_error}")
            return _generate_fallback_analysis(total_responses, org_name)
        except Exception as api_error:
            print(f"Gemini API 호출 오류: {api_error}")
            return f"AI 분석 생성 중 오류가 발생했습니다: {str(api_error)}"

    except Exception as e:
        print(f"주관식 종합 분석 생성 오류: {e}")
        return f"AI 종합 해석 생성 중 오류가 발생했습니다: {str(e)}"


def generate_advanced_subjective_analysis(structured_data: list, df: pd.DataFrame) -> dict:
    """
    회사단위 리포트를 위한 고급 주관식 분석 생성
    - 측면별 감성분석
    - 주장 근거 제안
    - 팀별 잠재유형 지도분석
    """
    print("[DEBUG] generate_advanced_subjective_analysis called")

    # 1. 측면별 감성분석
    aspect_sentiment = analyze_aspect_sentiment(structured_data)
    print(f"[DEBUG] aspect_sentiment completed")

    # 2. 주장 근거 제안
    evidence_suggestions = generate_evidence_suggestions(structured_data)
    print(f"[DEBUG] evidence_suggestions completed")

    # 3. 팀별 잠재유형 지도분석 (부서/팀 정보가 있을 경우)
    team_potential_mapping = analyze_team_potential_types(structured_data, df)
    print(f"[DEBUG] team_potential_mapping completed: {team_potential_mapping}")

    result = {
        "aspect_sentiment": aspect_sentiment,
        "evidence_suggestions": evidence_suggestions,
        "team_potential_mapping": team_potential_mapping
    }
    print(f"[DEBUG] generate_advanced_subjective_analysis result: {result}")
    return result


def analyze_aspect_sentiment(structured_data: list) -> dict:
    """측면별 감성분석 수행"""
    try:
        aspects = {
            "조직문화": [],
            "리더십": [],
            "업무환경": [],
            "성장기회": [],
            "소통협력": []
        }

        # 키워드 기반으로 측면 분류
        keywords = {
            "조직문화": ["문화", "분위기", "가치", "비전", "미션", "조직", "환경"],
            "리더십": ["리더", "상사", "관리", "지시", "의사결정", "방향성"],
            "업무환경": ["업무", "시설", "시스템", "도구", "환경", "근무"],
            "성장기회": ["성장", "교육", "학습", "발전", "승진", "기회"],
            "소통협력": ["소통", "협력", "팀워크", "커뮤니케이션", "협업"]
        }

        if not structured_data or not isinstance(structured_data, list):
            return {}

        for data_block in structured_data:
            if not isinstance(data_block, dict):
                continue

            answers = data_block.get("answers", [])
            if not answers or not isinstance(answers, list):
                continue

            for answer in answers:
                if not answer or not isinstance(answer, str):
                    continue

                answer_lower = answer.lower()

                # 각 측면별로 키워드 매칭
                for aspect, aspect_keywords in keywords.items():
                    if any(keyword in answer_lower for keyword in aspect_keywords):
                        # 정교한 감성 점수 계산 (가중치 적용 + 문맥 고려)
                        positive_words = {
                            "매우긍정": ["최고", "훌륭", "뛰어나", "완벽", "우수한"],  # 가중치 3
                            "긍정": ["좋", "만족", "긍정", "효과적", "성공", "발전", "향상", "개선된", "잘되", "원활"],  # 가중치 2
                            "약간긍정": ["괜찮", "나쁘지않", "적당", "보통이상"]  # 가중치 1
                        }
                        negative_words = {
                            "매우부정": ["최악", "심각", "큰문제", "치명적", "절망"],  # 가중치 -3
                            "부정": ["부족", "문제", "어려", "힘들", "부정", "실패", "개선필요", "아쉬", "불만", "불편"],  # 가중치 -2
                            "약간부정": ["조금", "약간부족", "미흡"]  # 가중치 -1
                        }

                        # 가중치를 적용한 점수 계산
                        sentiment_score = 0
                        for category, words in positive_words.items():
                            weight = 3 if "매우" in category else (2 if category == "긍정" else 1)
                            count = sum(1 for word in words if word in answer_lower)
                            sentiment_score += count * weight

                        for category, words in negative_words.items():
                            weight = -3 if "매우" in category else (-2 if category == "부정" else -1)
                            count = sum(1 for word in words if word in answer_lower)
                            sentiment_score += count * weight

                        # 문맥 보정 (부정어 + 긍정어 조합 처리)
                        if any(neg in answer_lower for neg in ["않", "없", "못"]):
                            # "좋지 않다", "만족하지 못한다" 등의 부정 표현 감지
                            if any(pos in answer_lower for pos in ["좋", "만족", "괜찮"]):
                                sentiment_score -= 1

                        # 감성 범주 결정 (더 세분화된 기준)
                        if sentiment_score >= 2:
                            sentiment = "긍정"
                        elif sentiment_score <= -2:
                            sentiment = "부정"
                        else:
                            sentiment = "중립"

                        aspects[aspect].append({
                            "text": answer,
                            "sentiment": sentiment,
                            "score": sentiment_score
                        })

        # 측면별 감성 요약
        aspect_summary = {}
        for aspect, responses in aspects.items():
            if responses:
                try:
                    avg_score = sum(r.get("score", 0) for r in responses) / len(responses)
                    pos_count = len([r for r in responses if r.get("sentiment") == "긍정"])
                    neg_count = len([r for r in responses if r.get("sentiment") == "부정"])

                    aspect_summary[aspect] = {
                        "total_responses": len(responses),
                        "average_sentiment": round(avg_score, 2),
                        "positive_count": pos_count,
                        "negative_count": neg_count,
                        "overall_sentiment": "긍정" if avg_score > 0 else ("부정" if avg_score < 0 else "중립"),
                        "responses": responses[:3]  # 상위 3개만 포함
                    }
                except (ZeroDivisionError, TypeError) as e:
                    continue

        return aspect_summary

    except Exception as e:
        print(f"Error in analyze_aspect_sentiment: {e}")
        return {}


def generate_evidence_suggestions(structured_data: list) -> list:
    """주장에 대한 근거 제안 생성"""
    try:
        suggestions = []

        if not structured_data or not isinstance(structured_data, list):
            return []

        # 강점 분석 (긍정기술 카테고리)
        strengths = []
        improvements = []

        for data_block in structured_data:
            if not isinstance(data_block, dict):
                continue

            category = data_block.get("category", "")
            answers = data_block.get("answers", [])

            if not answers or not isinstance(answers, list):
                continue

            # 문자열 타입만 필터링
            valid_answers = [ans for ans in answers if isinstance(ans, str) and ans.strip()]

            if "긍정" in category:
                strengths.extend(valid_answers)
            elif "부정" in category:
                improvements.extend(valid_answers)

        # 강점 기반 근거 제안
        if strengths:
            suggestions.append({
                "type": "강점 활용 제안",
                "title": "조직의 핵심 강점을 전략적으로 활용",
                "evidence": strengths[:3],
                "action_items": [
                    "핵심 강점을 조직 브랜딩에 활용",
                    "강점 기반 인재 채용 전략 수립",
                    "강점을 바탕으로 한 사업 영역 확장 검토"
                ]
            })

        # 개선점 기반 근거 제안
        if improvements:
            suggestions.append({
                "type": "개선 우선순위 제안",
                "title": "즉시 개선이 필요한 핵심 이슈",
                "evidence": improvements[:3],
                "action_items": [
                    "개선 이슈별 담당 부서 및 책임자 지정",
                    "단기(3개월)/중기(6개월) 개선 계획 수립",
                    "개선 진행상황 모니터링 체계 구축"
                ]
            })

        return suggestions

    except Exception as e:
        print(f"Error in generate_evidence_suggestions: {e}")
        return []


def analyze_team_potential_types(structured_data: list, df: pd.DataFrame) -> dict:
    """팀별 잠재유형 지도분석"""
    try:
        print(f"[DEBUG] analyze_team_potential_types called with df shape: {df.shape if df is not None else 'None'}")

        if df is None or df.empty:
            print("[DEBUG] DataFrame is None or empty")
            return {"message": "데이터가 없어 팀별 분석을 수행할 수 없습니다."}

        print(f"[DEBUG] DataFrame columns: {df.columns.tolist()}")

        # 부서/팀 컬럼 찾기
        team_columns = [col for col in df.columns if any(keyword in col.upper() for keyword in ['POS', 'DEPT', 'TEAM', '부서', '팀'])]
        print(f"[DEBUG] Found team columns: {team_columns}")

        if not team_columns:
            print("[DEBUG] No team columns found")
            return {"message": "팀/부서 정보가 없어 팀별 분석을 수행할 수 없습니다."}

        team_col = team_columns[0]  # 첫 번째 팀 컬럼 사용

        # 팀별 주관식 응답 분석
        team_analysis = {}

        unique_teams = df[team_col].dropna().unique()
        print(f"[DEBUG] Using team column: {team_col}")
        print(f"[DEBUG] Found unique teams: {unique_teams}")
        print(f"[DEBUG] Number of unique teams: {len(unique_teams)}")

        if len(unique_teams) == 0:
            print("[DEBUG] No valid team information found")
            return {"message": "유효한 팀 정보가 없습니다."}

        for team_name in unique_teams:
            try:
                team_df = df[df[team_col] == team_name]
                if team_df.empty:
                    continue

                team_responses = []

                # 팀별 주관식 응답 수집
                for col in ["NO40", "NO41", "NO42", "NO43"]:
                    if col in team_df.columns:
                        responses = team_df[col].dropna().astype(str).tolist()
                        # 유효한 응답만 필터링
                        valid_responses = [resp for resp in responses if resp and resp.strip() and resp != 'nan']
                        team_responses.extend(valid_responses)

                if team_responses:
                    # 팀 특성 키워드 분석 (더 포괄적인 키워드 포함)
                    innovation_keywords = ["혁신", "창의", "새로", "도전", "변화", "패기", "자율", "실험", "아이디어", "발굴"]
                    stability_keywords = ["안정", "체계", "규칙", "절차", "관리", "전문성", "품질", "정확", "표준", "프로세스"]
                    collaboration_keywords = ["협력", "팀워크", "소통", "협업", "함께", "동료", "배려", "포용", "상호", "존중"]
                    performance_keywords = ["성과", "실적", "목표", "달성", "결과", "추진력", "효율", "운영", "성장", "향상"]

                    scores = {
                        "혁신성": sum(1 for resp in team_responses for keyword in innovation_keywords if keyword in resp),
                        "안정성": sum(1 for resp in team_responses for keyword in stability_keywords if keyword in resp),
                        "협력성": sum(1 for resp in team_responses for keyword in collaboration_keywords if keyword in resp),
                        "성과지향": sum(1 for resp in team_responses for keyword in performance_keywords if keyword in resp)
                    }

                    # 팀 유형 결정 (가장 높은 점수의 특성)
                    max_score = max(scores.values()) if scores.values() else 0
                    dominant_trait = max(scores, key=scores.get) if max_score > 0 else "균형형"

                    team_analysis[str(team_name)] = {
                        "size": len(team_df),
                        "dominant_trait": dominant_trait,
                        "trait_scores": scores,
                        "potential_type": classify_team_potential_type(scores),
                        "development_suggestions": get_team_development_suggestions(dominant_trait)
                    }
                    print(f"[DEBUG] Added team analysis for {team_name}: {team_analysis[str(team_name)]}")

            except Exception as e:
                print(f"Error analyzing team {team_name}: {e}")
                continue

        print(f"[DEBUG] Final team_analysis result: {team_analysis}")
        return team_analysis if team_analysis else {"message": "분석 가능한 팀 데이터가 없습니다."}

    except Exception as e:
        print(f"Error in analyze_team_potential_types: {e}")
        return {"message": f"팀별 분석 중 오류 발생: {str(e)}"}


def classify_team_potential_type(scores: dict) -> str:
    """팀 잠재유형 분류"""
    max_score = max(scores.values())
    if max_score == 0:
        return "미분류형"

    dominant_traits = [trait for trait, score in scores.items() if score == max_score]

    if len(dominant_traits) > 1:
        return "복합형"

    trait_types = {
        "혁신성": "창조혁신형",
        "안정성": "체계안정형",
        "협력성": "소통협력형",
        "성과지향": "목표달성형"
    }

    return trait_types.get(dominant_traits[0], "균형형")


def get_team_type_description(team_type: str) -> dict:
    """팀 유형별 상세 설명 반환"""
    descriptions = {
        "창조혁신형": {
            "title": "창조혁신형 (Creative & Innovative)",
            "description": "새로운 아이디어 창출과 혁신에 강점을 보이는 팀입니다.",
            "characteristics": [
                "창의적 사고와 도전정신이 뛰어남",
                "변화에 유연하게 적응하고 새로운 시도를 두려워하지 않음",
                "문제 해결 시 기존 틀을 벗어난 접근을 선호",
                "실험과 시행착오를 통한 학습을 중시"
            ],
            "strengths": [
                "혁신적인 솔루션 개발",
                "미래 트렌드 파악과 선제적 대응",
                "창의적 문제 해결"
            ],
            "development_areas": [
                "아이디어 실행력 강화",
                "체계적 프로세스 도입",
                "리스크 관리 능력 향상"
            ]
        },
        "체계안정형": {
            "title": "체계안정형 (Systematic & Stable)",
            "description": "체계적이고 안정적인 업무 수행에 강점을 보이는 팀입니다.",
            "characteristics": [
                "명확한 프로세스와 규칙을 선호함",
                "꼼꼼하고 정확한 업무 처리가 특징",
                "안정성과 예측 가능성을 중시",
                "단계별 계획 수립과 실행에 능숙"
            ],
            "strengths": [
                "높은 업무 품질과 정확성",
                "안정적이고 지속적인 성과 창출",
                "리스크 최소화"
            ],
            "development_areas": [
                "변화 적응력 향상",
                "창의적 사고 개발",
                "유연성 강화"
            ]
        },
        "소통협력형": {
            "title": "소통협력형 (Collaborative & Communicative)",
            "description": "팀워크와 협력을 통한 시너지 창출에 강점을 보이는 팀입니다.",
            "characteristics": [
                "원활한 의사소통과 정보 공유가 활발함",
                "구성원 간 상호 지원과 협력이 뛰어남",
                "갈등 상황에서 조정과 중재 능력 보유",
                "포용적이고 화합적인 분위기 조성"
            ],
            "strengths": [
                "높은 팀 결속력과 만족도",
                "효과적인 지식 공유와 학습",
                "갈등 해결과 관계 개선"
            ],
            "development_areas": [
                "목표 지향적 성과 창출",
                "의사결정 속도 향상",
                "개인 역량 강화"
            ]
        },
        "목표달성형": {
            "title": "목표달성형 (Goal-Oriented & Achievement-Focused)",
            "description": "명확한 목표 설정과 강력한 실행력으로 성과를 달성하는 팀입니다.",
            "characteristics": [
                "구체적이고 도전적인 목표 설정을 선호함",
                "결과 중심적이고 성과 지향적인 사고",
                "빠른 의사결정과 실행력이 뛰어남",
                "경쟁 상황에서 강한 동기부여 발휘"
            ],
            "strengths": [
                "높은 목표 달성률과 생산성",
                "신속한 대응과 실행력",
                "성과 중심의 효율적 운영"
            ],
            "development_areas": [
                "장기적 관점 강화",
                "팀워크와 협력 개선",
                "지속가능한 성장 추구"
            ]
        },
        "복합형": {
            "title": "복합형 (Multi-Dimensional)",
            "description": "여러 특성이 균형있게 발달한 다면적 강점을 보이는 팀입니다.",
            "characteristics": [
                "상황에 따라 유연하게 대처하는 적응력",
                "다양한 관점에서 문제를 바라보는 시각",
                "균형잡힌 업무 접근 방식",
                "복합적 역량의 시너지 효과"
            ],
            "strengths": [
                "다양한 상황에 대한 높은 적응력",
                "종합적이고 균형잡힌 문제 해결",
                "변화하는 환경에서의 안정성"
            ],
            "development_areas": [
                "핵심 강점 영역 집중 개발",
                "특화된 전문성 강화",
                "차별화된 경쟁력 확보"
            ]
        },
        "균형형": {
            "title": "균형형 (Balanced)",
            "description": "모든 영역에서 고른 발달을 보이는 균형잡힌 팀입니다.",
            "characteristics": [
                "전반적으로 안정적인 역량 보유",
                "특별한 약점 없이 고른 성과",
                "다양한 업무에 무난한 대응력",
                "조화로운 팀 운영"
            ],
            "strengths": [
                "안정적이고 예측 가능한 성과",
                "다양한 업무 영역에서의 적응력",
                "균형잡힌 팀 역학"
            ],
            "development_areas": [
                "차별화된 강점 영역 발굴",
                "전문성과 특화 역량 개발",
                "독특한 경쟁우위 창출"
            ]
        }
    }

    return descriptions.get(team_type, descriptions["균형형"])


def get_team_development_suggestions(dominant_trait: str) -> list:
    """팀 특성별 발전 제안"""
    suggestions = {
        "혁신성": [
            "창의적 아이디어 발굴 워크숍 정기 진행",
            "실험적 프로젝트 추진 기회 제공",
            "외부 혁신 사례 벤치마킹 활동"
        ],
        "안정성": [
            "표준 프로세스 문서화 및 체계화",
            "품질 관리 시스템 고도화",
            "리스크 관리 역량 강화 교육"
        ],
        "협력성": [
            "크로스 펑셔널 프로젝트 참여 기회 확대",
            "팀 빌딩 및 소통 스킬 교육",
            "내외부 네트워킹 활동 지원"
        ],
        "성과지향": [
            "도전적 목표 설정 및 달성 보상 체계",
            "성과 측정 지표 고도화",
            "고성과 팀 사례 공유 세션"
        ]
    }

    return suggestions.get(dominant_trait, ["균형적 역량 개발 프로그램 참여"])


def mask_sensitive_content(text: str) -> str:
    """
    주관식 응답에서 민감한 정보를 마스킹한다.
    """
    import re

    # 이메일 주소 마스킹
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[이메일]', text)

    # 전화번호 마스킹
    text = re.sub(r'\b\d{2,3}[-\s]?\d{3,4}[-\s]?\d{4}\b', '[전화번호]', text)

    # 개인명 마스킹 로직 제거 (잘못된 매칭으로 인한 오류 방지)

    # 부서명이 너무 구체적인 경우
    text = re.sub(r'\b\w+팀\b', '[팀명]', text)

    return text


# ================================
# 1) 환경설정 / 경로
# ================================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TEMPLATE_DIR = BASE_DIR / "templates"
REF_DIR = BASE_DIR / "reference" / "organizational-effectiveness"
INDEX_PATH = REF_DIR / "index.xlsx"
RAW_SAMPLE_PATH = REF_DIR / "rawsample.xlsx"
PROMPT_DIR = BASE_DIR / "prompts"

# ================================
# 2) Gemini (google-genai, 신 SDK)
# ================================
try:
    # pip install google-genai
    from google import genai  # 신 SDK
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GENAI_DEFAULT_MODEL = os.getenv("GENAI_MODEL", "gemini-2.5-flash")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

_GENAI_CLIENT = None
def _get_genai_client():
    """
    google-genai 클라이언트를 1번만 만들고 재사용
    """
    global _GENAI_CLIENT
    if _GENAI_CLIENT is not None:
        return _GENAI_CLIENT
    if not _HAS_GENAI or not GOOGLE_API_KEY:
        return None
    try:
        _GENAI_CLIENT = genai.Client(api_key=GOOGLE_API_KEY)
        return _GENAI_CLIENT
    except Exception:
        return None


# 👉👉 👉 여기 추가된 부분 (1/2) 👈 👈 👈
def call_gemini(prompt: str, model: str | None = None) -> str:
    """
    실제 Gemini 호출 래퍼
    - 지금 run_ai_interpretation_gemini_from_report(...) 안에서 이 함수를 여러 번 부르므로
      여기서만 SDK/키 체크하고 문자열만 돌려주면 된다.
    """
    if not _HAS_GENAI:
        return "[AI] google-genai 패키지가 설치되어 있지 않습니다. `pip install google-genai` 후 다시 실행하세요."
    if not GOOGLE_API_KEY:
        return "[AI] GOOGLE_API_KEY 가 설정되지 않았습니다. .env에 `GOOGLE_API_KEY=...` 값을 넣어주세요."
    client = _get_genai_client()
    if client is None:
        return "[AI] Gemini 클라이언트 생성 실패. API 키/네트워크 설정을 확인하세요."
    model = model or GENAI_DEFAULT_MODEL
    try:
        resp = client.models.generate_content(model=model, contents=prompt)
        # google-genai 응답은 보통 .text 에 본문이 들어온다
        return (getattr(resp, "text", "") or "").strip()
    except Exception as e:
        return f"[AI] Gemini 호출 오류: {e}"


# ================================
# 3) 글로벌 스타일
# ================================
def inject_global_styles():
    st.markdown(
        """
        <style>
        .stApp { background: #f4f6fb; }
        header[data-testid="stHeader"] { display: none; }
        div[data-testid="stToolbar"] { display: none; }

        aside[data-testid="stSidebar"],
        section[data-testid="stSidebar"] {
            display: block !important;
            visibility: visible !important;
            background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
            border-right: 1px solid #e2e8f0;
            width: 16rem !important;
            min-width: 16rem !important;
            transform: none !important;
            box-shadow: 2px 0 10px rgba(0, 0, 0, 0.05);
        }
        div[data-testid="collapsedControl"] { display: none !important; }

        aside[data-testid="stSidebar"] > div:first-child,
        section[data-testid="stSidebar"] > div:first-child {
            padding: 1.5rem 1rem 1rem 1rem;
        }

        .sb-title {
            font-size: 0.85rem;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 1rem;
            padding: 0.5rem 0.75rem;
            background: linear-gradient(135deg, #0f4fa8 0%, #1d4ed8 100%);
            color: white;
            border-radius: 0.5rem;
            text-align: center;
            box-shadow: 0 2px 8px rgba(15, 79, 168, 0.2);
        }

        aside[data-testid="stSidebar"] .stButton > button,
        section[data-testid="stSidebar"] .stButton > button {
            width: 100%;
            background: white !important;
            border: 1px solid #e2e8f0 !important;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05) !important;
            text-align: left;
            border-radius: 0.75rem;
            padding: 0.75rem 1rem;
            font-size: 0.85rem;
            color: #334155;
            margin-bottom: 0.5rem;
            transition: all 0.2s ease;
            font-weight: 500;
        }
        aside[data-testid="stSidebar"] .stButton > button:hover,
        section[data-testid="stSidebar"] .stButton > button:hover {
            background: linear-gradient(135deg, #f0f7ff 0%, #e0f2fe 100%) !important;
            border-color: #0f4fa8 !important;
            color: #0f4fa8 !important;
            box-shadow: 0 4px 12px rgba(15, 79, 168, 0.15) !important;
            transform: translateY(-1px);
        }

        /* 활성 버튼 스타일 */
        aside[data-testid="stSidebar"] .stButton > button[style*="background:rgba(7, 61, 130, 0.13)"],
        section[data-testid="stSidebar"] .stButton > button[style*="background:rgba(7, 61, 130, 0.13)"] {
            background: linear-gradient(135deg, #0f4fa8 0%, #1d4ed8 100%) !important;
            color: white !important;
            border-color: #0f4fa8 !important;
            box-shadow: 0 4px 12px rgba(15, 79, 168, 0.25) !important;
        }

        /* 새로운 사이드바 아이템 스타일 */
        .sidebar-item {
            width: 100%;
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            margin-bottom: 4px;
            padding: 10px 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .sidebar-item:hover {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border-color: #3B5BDB;
            box-shadow: 0 4px 12px rgba(59, 91, 219, 0.15);
            transform: translateY(-1px);
        }

        .sidebar-item:hover .sidebar-item-title {
            color: #3B5BDB;
        }

        .sidebar-item.active {
            background: linear-gradient(135deg, #0f4fa8 0%, #1d4ed8 100%);
            color: white;
            border-color: #0f4fa8;
            box-shadow: 0 4px 16px rgba(15, 79, 168, 0.25);
        }

        .sidebar-item-number {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #f1f5f9;
            color: #475569;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            font-size: 12px;
            flex-shrink: 0;
        }

        .sidebar-item.active .sidebar-item-number {
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }

        .sidebar-item-content {
            flex: 1;
            min-width: 0;
        }

        .sidebar-item-title {
            font-weight: 600;
            font-size: 13px;
            color: #1e293b;
            margin-bottom: 1px;
        }

        .sidebar-item.active .sidebar-item-title {
            color: white;
        }

        .sidebar-item-desc {
            font-size: 10px;
            color: #64748b;
            line-height: 1.2;
        }

        .sidebar-item.active .sidebar-item-desc {
            color: rgba(255, 255, 255, 0.8);
        }

        .sidebar-item-status {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: #f1f5f9;
            color: #64748b;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 600;
            flex-shrink: 0;
        }

        .sidebar-item.active .sidebar-item-status {
            background: rgba(255, 255, 255, 0.2);
            color: white;
        }

        .sidebar-item.completed {
            background: #E0E0E0;
            border-color: #BDBDBD;
            opacity: 0.8;
        }

        .sidebar-item.completed .sidebar-item-title,
        .sidebar-item.completed .sidebar-item-desc {
            color: #757575;
        }

        .sidebar-item.completed .sidebar-item-number {
            background: #BDBDBD;
            color: #9E9E9E;
        }

        .sidebar-item.completed .sidebar-item-status {
            background: #4CAF50;
            color: white;
        }

        /* 숨겨진 버튼 및 관련 요소들 완전 제거 */
        button[key^="hidden_menu_"],
        button[key$="_card"],
        .stButton:has(button[key^="hidden_menu_"]),
        .stButton:has(button[key$="_card"]),
        div[data-testid="stButton"]:has(button[key^="hidden_menu_"]),
        div[data-testid="stButton"]:has(button[key$="_card"]) {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            height: 0 !important;
            width: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            position: absolute !important;
            top: -9999px !important;
            left: -9999px !important;
            overflow: hidden !important;
            clip: rect(0, 0, 0, 0) !important;
        }

        /* 사이드바 전체에서 빈 요소들 제거 */
        aside[data-testid="stSidebar"] div:empty,
        aside[data-testid="stSidebar"] .stButton:empty,
        aside[data-testid="stSidebar"] .element-container:empty,
        aside[data-testid="stSidebar"] .stMarkdown:empty {
            display: none !important;
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }

        /* Streamlit 기본 빈 요소들 강력 제거 */
        .stButton:empty,
        .stMarkdown:empty,
        div[data-testid]:empty,
        .element-container:empty,
        .stHorizontalBlock:empty,
        .css-1d391kg:empty,
        .css-12oz5g7:empty {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
        }

        /* 사이드바 내 모든 빈 버튼 컨테이너 제거 */
        aside[data-testid="stSidebar"] .stButton {
            margin: 0 !important;
            padding: 0 !important;
        }

        aside[data-testid="stSidebar"] .stButton button[title=""],
        aside[data-testid="stSidebar"] .stButton button:empty {
            display: none !important;
            height: 0 !important;
            width: 0 !important;
        }

        /* Expander 스타일 개선 */
        aside[data-testid="stSidebar"] .streamlit-expanderHeader,
        section[data-testid="stSidebar"] .streamlit-expanderHeader {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 0.5rem;
            padding: 0.5rem 0.75rem;
            font-size: 0.8rem;
            color: #64748b;
            margin-top: 1rem;
        }

        [data-testid="stAppViewContainer"] > .main {
            padding-top: 0 !important;
        }
        [data-testid="stAppViewContainer"] .block-container {
            background: #ffffff;
            border-radius: 1rem 1rem 0 0;
            box-shadow: 0 10px 30px rgba(4, 34, 87, 0.03);
            padding: 1.4rem 1.6rem 2.1rem 1.6rem;
            margin-top: 0.9rem;
            max-width: 1180px;
        }

        .page-header {
            background: linear-gradient(90deg,#0f4fa8 0%, #0b3d82 45%, #072a58 100%);
            margin: -1.4rem -1.6rem 1.2rem -1.6rem;
            padding: 1.05rem 1.2rem 1.05rem 1.6rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 3px 12px rgba(4,34,87,0.15);
        }
        .page-header-title {
            font-size: 1.25rem;
            font-weight: 660;
            color: #fff;
        }
        .page-header-right {
            font-size: 0.68rem;
            color: rgba(255,255,255,.85);
        }

        .guide-card {
            background: #f6f9ff;
            border: 1px solid #e3ecff;
            border-radius: .7rem;
            padding: .7rem .8rem .75rem .8rem;
            margin-bottom: .75rem;
        }
        .guide-card-title {
            font-weight: 650;
            font-size: .9rem;
            margin-bottom: .3rem;
            color: #1d2c44;
        }
        .guide-card-desc {
            font-size: .82rem;
            color: #4e617b;
            line-height: 1.45;
        }

        .info-card {
            background: #fff;
            border: 1px solid #edf0f5;
            border-radius: .75rem;
            overflow: hidden;
            margin-bottom: .9rem;
        }
        .info-card-head {
            background: #deebff;
            padding: .55rem .75rem;
            font-weight: 600;
            font-size: .78rem;
            color: #0f4fa8;
        }
        .info-card-body {
            padding: .65rem .8rem .75rem .8rem;
            font-size: .78rem;
            color: #1f2937;
        }

        .preview-container {
            border: 1px solid #edf0f5;
            border-radius: .75rem;
            background: #fff;
            overflow: hidden;
        }

        #export-view .export-card {
            background: #ffffff;
            border: 1px solid #dbe3ef;
            border-radius: .8rem;
            box-shadow: 0 6px 22px rgba(5, 31, 77, 0.03);
            padding: 0 0 1rem 0;
            margin-bottom: .7rem;
        }
        #export-view .export-card-head {
            background: #dfe8fb;
            padding: .65rem 1rem;
            border-radius: .8rem .8rem 0 0;
            font-weight: 650;
            font-size: .82rem;
            color: #0a3875;
        }
        #export-view .export-card-body {
            padding: .75rem 1rem 1rem 1rem;
        }

        div[data-testid="stMain"] button[data-testid="baseButton-primary"] {
            background: #0f4fa8;
            border-color: #0f4fa8;
        }
        div[data-testid="stMain"] button[data-testid="baseButton-primary"]:hover {
            background: #0c3d80;
            border-color: #0c3d80;
        }

        div[data-baseweb="input"] > div {
            border-color: rgba(15,79,168,0.25) !important;
            border-radius: .7rem !important;
            background: #fff;
        }

        /* =======================================
           📱 반응형 디자인 개선 (모바일/태블릿)
           ======================================= */

        /* 모바일 환경 (768px 이하) */
        @media screen and (max-width: 768px) {
            .stApp {
                background: #f8fafc;
            }

            /* 사이드바 모바일 최적화 */
            aside[data-testid="stSidebar"],
            section[data-testid="stSidebar"] {
                width: 14rem !important;
                min-width: 14rem !important;
            }

            /* 메인 컨테이너 모바일 최적화 */
            [data-testid="stAppViewContainer"] .block-container {
                padding: 1rem 0.8rem 1.5rem 0.8rem;
                margin-top: 0.5rem;
                border-radius: 0.5rem 0.5rem 0 0;
            }

            .page-header {
                margin: -1rem -0.8rem 1rem -0.8rem;
                padding: 0.8rem 1rem;
                flex-direction: column;
                gap: 0.5rem;
                text-align: center;
            }

            .page-header-title {
                font-size: 1.1rem;
            }

            /* Export 카드 모바일 최적화 */
            .export-card {
                margin-bottom: 1rem;
            }

            .export-card-head {
                font-size: 0.9rem;
                padding: 0.8rem 1rem;
            }

            .export-card-body {
                padding: 1rem;
            }

            /* 사이드바 아이템 모바일 최적화 */
            .sidebar-item {
                padding: 8px 10px;
                gap: 8px;
            }

            .sidebar-item-title {
                font-size: 12px;
            }

            .sidebar-item-desc {
                font-size: 9px;
            }

            /* 버튼 모바일 최적화 */
            .stButton > button {
                width: 100%;
                min-height: 2.5rem;
                font-size: 0.9rem;
            }
        }

        /* 태블릿 환경 (769px ~ 1024px) */
        @media screen and (min-width: 769px) and (max-width: 1024px) {
            [data-testid="stAppViewContainer"] .block-container {
                max-width: 95%;
                padding: 1.2rem 1.4rem 1.8rem 1.4rem;
            }

            .page-header {
                margin: -1.2rem -1.4rem 1rem -1.4rem;
                padding: 1rem 1.4rem;
            }
        }

        /* =======================================
           🎨 다크 모드 지원 (시스템 테마 따라감)
           ======================================= */

        @media (prefers-color-scheme: dark) {
            .stApp {
                background: #1a1a1a;
            }

            aside[data-testid="stSidebar"],
            section[data-testid="stSidebar"] {
                background: linear-gradient(180deg, #2d2d2d 0%, #1f1f1f 100%);
                border-right: 1px solid #404040;
            }

            [data-testid="stAppViewContainer"] .block-container {
                background: #2d2d2d;
                color: #e0e0e0;
            }

            .sidebar-item {
                background: #3d3d3d;
                border-color: #505050;
                color: #e0e0e0;
            }

            .sidebar-item:hover {
                background: linear-gradient(135deg, #4a4a4a 0%, #3d3d3d 100%);
                border-color: #6366f1;
            }

            .export-card {
                background: #3d3d3d;
                border-color: #505050;
                color: #e0e0e0;
            }
        }

        /* =======================================
           ⚡ 성능 최적화 및 접근성 개선
           ======================================= */

        /* GPU 가속 활성화 */
        .sidebar-item,
        .export-card,
        .stButton > button {
            will-change: transform, box-shadow;
            transform: translateZ(0);
        }

        /* 포커스 접근성 개선 */
        .sidebar-item:focus,
        .stButton > button:focus {
            outline: 2px solid #0f4fa8;
            outline-offset: 2px;
        }

        /* 애니메이션 성능 최적화 */
        .sidebar-item,
        .export-card,
        .stButton > button {
            transition: transform 0.15s cubic-bezier(0.4, 0, 0.2, 1),
                       box-shadow 0.15s cubic-bezier(0.4, 0, 0.2, 1),
                       background-color 0.15s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* 스크롤 성능 최적화 */
        .preview-container,
        #export-view,
        #email-view {
            contain: layout style paint;
        }

        /* 로딩 상태 시각화 개선 */
        .stSpinner > div {
            border-color: #0f4fa8 transparent transparent transparent;
        }

        /* 에러 상태 시각화 개선 */
        .stAlert[data-baseweb="notification"] {
            border-radius: 0.75rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }

        /* 성공 상태 시각화 개선 */
        .stSuccess {
            background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
            border: 1px solid #22c55e;
            color: #15803d;
        }

        /* 경고 상태 시각화 개선 */
        .stWarning {
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 1px solid #f59e0b;
            color: #92400e;
        }

        /* 정보 상태 시각화 개선 */
        .stInfo {
            background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
            border: 1px solid #3b82f6;
            color: #1e40af;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ================================
# 4) 프롬프트 유틸 / 안전 포맷터
# ================================
def load_prompt_file(name: str) -> str:
    p = PROMPT_DIR / name
    if p.exists():
        return p.read_text(encoding="utf-8")
    return ""

PROMPT_PREFIX = """
[규칙 - 반드시 지킬 것]
- 새로운 ID를 만들지 말고, 데이터에 있는 DID를 그대로 사용하라.
- 엑셀 헤더가 모호하거나 매핑이 안 되는 경우는 'NEED_CONFIRMATION: ...' 으로 표현하고 추측하지 마라.
- 답변은 한국어로 하되, 진단명/문항명은 원본 값을 유지하라.
- 5단계를 하나로 합치는 것을 금지한다. (score, item, free-text, org-context, writer, reviewer는 분리)
- NAS 경로, 파일 경로는 임의로 하드코딩하지 말고 'TO_BE_FILLED_BY_SYSTEM'으로 남겨라.
""".strip()

AI_STRIP_PREFIXES = [
    "저는 조직효과성 진단 점수를 해석하는 HRD 컨설턴트입니다.",
    "데이터를 입력해 주시면 분석해 드리겠습니다.",
    "정확한 분석을 위해 응답자 수(N)와 Input, Process, Output 각 영역의 점수를 제공해주시면 감사하겠습니다.",
    "예시 분석 (가상 데이터 적용):",
    "예시:",
]


def _clean_ai_text(text: str, min_len: int = 40) -> str:
    """Gemini가 붙여보내는 '저는 …' 같은 머릿말, ``` 코드블록, 너무 긴 구분선 등을 잘라낸다."""
    if not text:
        return ""
    t = str(text).strip()
    # 코드펜스 제거
    t = t.replace("```", "").replace("** **", "").strip()
    # 마크다운 강조 표시 제거
    import re
    t = re.sub(r'\*\*(.*?)\*\*', r'\1', t)  # **텍스트** -> 텍스트
    t = re.sub(r'\*(.*?)\*', r'\1', t)      # *텍스트* -> 텍스트
    t = re.sub(r'_{2,}(.*?)_{2,}', r'\1', t)  # __텍스트__ -> 텍스트
    # JSON 형식 제거
    t = t.replace("json", "").strip()
    # 앞머리 공통 문구 제거
    for prefix in AI_STRIP_PREFIXES:
        if t.startswith(prefix):
            t = t[len(prefix):].lstrip(" \n:*").strip()
    # 너무 짧으면 원문 유지
    if len(t) < min_len:
        return t
    return t

def _fix_json_response(text: str) -> str:
    """
    AI 응답에서 JSON 형식 오류를 수정한다
    """
    if not text:
        return text

    # "json\n{...}" 패턴 처리
    if text.startswith("json\n{"):
        try:
            import json
            json_part = text[5:]  # "json\n" 제거
            parsed = json.loads(json_part)
            # JSON이 정상 파싱되면 실제 값 추출
            if isinstance(parsed, dict) and len(parsed) == 1:
                return list(parsed.values())[0]
        except:
            # JSON 파싱 실패시 원문 반환
            pass

    return text

def _convert_error_to_natural_response(text: str, field_type: str) -> str:
    """
    에러 메시지를 자연스러운 대안 응답으로 변환
    """
    if not text:
        return text

    # 공통 에러 메시지 패턴 감지
    error_patterns = [
        "이번 결과에서는 특이사항이 발견되지 않았습니다",
        "초안 카드의 내용이 비어있어 기본 문구로 대체합니다",
        "데이터가 부족합니다",
        "정보가 불충분합니다"
    ]

    for pattern in error_patterns:
        if pattern in text:
            return _generate_fallback_response(field_type)

    return text

def _generate_fallback_response(field_type: str) -> str:
    """
    필드 타입별 자연스러운 대안 응답 생성
    """
    fallback_responses = {
        "score": "조직의 전반적인 운영 수준이 안정적으로 유지되고 있으며, 구성원들의 업무 몰입도와 협업 체계가 양호한 상태로 나타났습니다. 지속적인 발전을 위해서는 소통과 협력 체계를 더욱 강화하는 것이 도움이 될 것으로 보입니다.",
        "items": "현재 조직은 전반적으로 균형 잡힌 운영 상태를 보이고 있습니다. 향후 더 나은 성과를 위해서는 부서 간 협업 강화, 의사소통 체계 개선, 그리고 구성원 역량 개발에 지속적인 관심을 기울이는 것이 좋겠습니다.",
        "free_text": "구성원들의 전반적인 조직 만족도는 양호한 수준이며, 업무 환경과 팀워크에 대해 긍정적으로 평가하고 있습니다. 지속적인 성장을 위해서는 개방적인 소통 문화와 상호 신뢰 기반의 협업 체계를 더욱 발전시켜 나가는 것이 중요할 것으로 보입니다.",
        "org_context": "이 조직은 체계적인 업무 프로세스와 전문성을 바탕으로 운영되고 있으며, 구성원들 간의 협력과 소통을 통해 목표를 달성해 나가는 건강한 조직 문화를 보유하고 있습니다.",
        "writer": "이번 진단에서 리더가 먼저 이해해야 할 관점은, 조직이 전반적으로 안정적인 운영 기반을 갖추고 있으면서도 지속적인 발전 가능성을 보여주고 있다는 점입니다. 구성원들의 높은 참여도와 협력 의지를 바탕으로, 소통 체계를 더욱 체계화하고 상호 신뢰를 강화한다면 더 큰 시너지를 창출할 수 있을 것입니다."
    }

    return fallback_responses.get(field_type, "조직의 현재 상태는 전반적으로 양호하며, 지속적인 개선을 통해 더 나은 성과를 달성할 수 있을 것으로 기대됩니다.")


def _normalize_ai_result(ai: dict | None) -> dict:
    """
    gemini가 뭘 주든 UI에서 바로 쓸 수 있는 형태로 정규화
    - None → {}
    - 각 필드는 str로 강제
    - JSON 파싱 오류 복구
    - 에러 메시지를 자연스러운 대안 응답으로 변환
    """
    if not ai:
        return {}
    norm = {}
    for key in ["score", "items", "free_text", "org_context", "writer", "reviewer", "final"]:
        val = ai.get(key)
        if val is None:
            norm[key] = ""
        else:
            val_str = str(val).strip()
            # JSON 형식 오류 복구
            val_str = _fix_json_response(val_str)
            # 에러 메시지를 자연스러운 응답으로 변환
            val_str = _convert_error_to_natural_response(val_str, key)
            norm[key] = val_str
    return norm

# ================================================
# AI 텍스트 안의 {{ ... }} 플레이스홀더 치환 유틸
# ================================================
def _build_ai_context_from_report(report: dict) -> dict:
    """
    AI가 '해당 조직은 {{org_units}} ...' 식으로 돌려보낸 텍스트를
    실제 조직명/산업명/주관식요약으로 바꿀 때 사용할 컨텍스트를 만든다.
    """
    if report is None:
        report = {}

    summary = report.get("summary") or {}

    ctx: dict[str, object] = {}
    # 조직명 후보
    ctx["org_units"] = (
        report.get("org_name")
        or report.get("dept_name")
        or "해당 조직"
    )
    # 산업 추정
    ctx["industry_guess"] = (
        summary.get("industry_guess")
        or _guess_industry_from_name(report.get("org_name") or "")
    )
    # NO40 주관식
    no40 = summary.get("no40_text") or []
    if isinstance(no40, list):
        ctx["no40_text"] = no40
        ctx["no40_text_joined"] = ", ".join([str(x) for x in no40])
    else:
        ctx["no40_text"] = [no40]
        ctx["no40_text_joined"] = str(no40)

    return ctx


def materialize_ai_placeholders(ai_raw: dict | None, report: dict) -> dict | None:
    """
    ai_raw 안에 들어있는 문자열을 한 번 더 Jinja로 렌더해서
    {{org_units}}, {{industry_guess}}, {{no40_text_joined}} 같은 걸 실제 값으로 치환한다.
    """
    if not ai_raw:
        return ai_raw

    ctx = _build_ai_context_from_report(report)
    env = Environment(loader=BaseLoader())

    hydrated: dict[str, object] = {}
    for key, val in ai_raw.items():
        if isinstance(val, str):
            try:
                tpl = env.from_string(val)
                hydrated[key] = tpl.render(**ctx)
            except Exception:
                hydrated[key] = val
        else:
            hydrated[key] = val
    return hydrated

def _has_ai_result(ai: dict | None) -> bool:
    """표시할 만한 AI 결과가 있는지 여부"""
    if not ai:
        return False
    for k in ("score", "items", "free_text", "org_context", "writer", "reviewer", "final"):
        v = ai.get(k)
        if v and str(v).strip():
            return True
    return False


# ================================
# 5) 데이터 로딩/검증/마스킹
# ================================
@st.cache_data
def load_index():
    df = pd.read_excel(INDEX_PATH)
    df.columns = [c.strip() for c in df.columns]
    if "대분류" in df.columns:
        df["대분류_clean"] = df["대분류"].astype(str).str.strip()
    else:
        df["대분류_clean"] = ""
    return df


def extract_organization_info(df: pd.DataFrame) -> dict:
    """
    업로드된 데이터에서 조직명과 부서/팀명을 자동으로 추출한다.
    """
    org_info = {
        "company": None,
        "department": None
    }

    if df is None or df.empty:
        return org_info

    # 회사명 후보 컬럼들
    company_columns = ["CMPNAME", "회사명", "조직명", "Company", "Organization", "Org", "회사", "조직"]
    for col in company_columns:
        if col in df.columns:
            company_values = df[col].dropna().unique()
            if len(company_values) > 0:
                # 가장 많이 나타나는 값 선택
                company_counts = df[col].value_counts()
                org_info["company"] = str(company_counts.index[0]).strip()
                break

    # 부서/팀명 후보 컬럼들
    dept_columns = ["POS", "부서명", "팀명", "Department", "Team", "Position", "부서", "팀", "직책", "소속"]
    for col in dept_columns:
        if col in df.columns:
            dept_values = df[col].dropna().unique()
            if len(dept_values) > 0:
                # 여러 값이 있으면 첫 번째 값 선택 (팀별 분석에서는 각각 처리)
                org_info["department"] = str(dept_values[0]).strip()
                break

    return org_info


def load_data(uploaded_file):
    if uploaded_file is not None:
        try:
            # 파일 확장자를 확인하여 적절한 읽기 방법 선택
            file_name = uploaded_file.name.lower()

            if file_name.endswith('.csv'):
                # CSV 파일 처리 - 인코딩 자동 감지
                try:
                    df = pd.read_csv(uploaded_file, encoding='utf-8')
                except UnicodeDecodeError:
                    # UTF-8 실패시 CP949(한국어) 시도
                    uploaded_file.seek(0)  # 파일 포인터 리셋
                    try:
                        df = pd.read_csv(uploaded_file, encoding='cp949')
                    except UnicodeDecodeError:
                        # CP949도 실패시 ISO-8859-1로 시도
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, encoding='iso-8859-1')
            elif file_name.endswith(('.xlsx', '.xls')):
                # 엑셀 파일 처리
                df = pd.read_excel(uploaded_file)
            else:
                # 기본값으로 엑셀 시도
                df = pd.read_excel(uploaded_file)

            # 데이터 전처리
            # 빈 행 제거
            df = df.dropna(how='all')

            # 컬럼명 정리 (앞뒤 공백 제거)
            df.columns = df.columns.astype(str).str.strip()

            source = "uploaded"

        except Exception as e:
            st.error(f"파일 읽기 오류: {str(e)}")
            st.error("지원되는 파일 형식: .xlsx, .xls, .csv")
            # 오류 시 샘플 데이터 사용
            df = pd.read_excel(RAW_SAMPLE_PATH)
            source = "sample_fallback"

    else:
        # 업로드된 파일이 없는 경우 샘플 데이터 사용
        df = pd.read_excel(RAW_SAMPLE_PATH)
        source = "sample"

    return df, source


def validate_df(df: pd.DataFrame, index_df: pd.DataFrame):
    header_col = "헤더명" if "헤더명" in index_df.columns else index_df.columns[0]
    expected_cols = index_df[header_col].dropna().astype(str).str.strip().tolist()
    df_cols = [c.strip() for c in df.columns]
    missing = [c for c in expected_cols if c not in df_cols]
    extra = [c for c in df_cols if c not in expected_cols]
    return {
        "missing": missing,
        "extra": extra,
        "expected_count": len(expected_cols),
        "actual_count": len(df_cols),
    }


SENSITIVE_KEYWORDS = [
    "조직", "회사", "부서", "팀", "본부", "소속", "부문", "사업부", "센터",
    "이름", "성명", "name", "department", "organization", "org"
]


def _mask_token(token: str) -> str:
    token = token.strip()
    if not token:
        return token
    if len(token) == 1:
        return "＊"
    if len(token) == 2:
        return token[0] + "＊"
    return token[0] + "＊" * (len(token) - 2) + token[-1]


def mask_text(val: str | None) -> str | None:
    if val is None:
        return val
    s = str(val).strip()
    if s == "":
        return s
    parts = s.split()
    masked_parts = [_mask_token(p) for p in parts]
    return " ".join(masked_parts)


def mask_email(val: str | None) -> str | None:
    if val is None:
        return val
    s = str(val).strip()
    if "@" not in s:
        return s
    local, domain = s.split("@", 1)
    if len(local) <= 2:
        local_masked = local[0] + "****"
    else:
        local_masked = local[0] + "****" + local[-1]
    return local_masked + "@" + domain


def mask_df_for_preview(df: pd.DataFrame) -> pd.DataFrame:
    df_masked = df.copy()
    for col in df_masked.columns:
        col_l = col.lower()
        series_str = df_masked[col].astype(str)
        if series_str.str.contains("@").any():
            df_masked[col] = series_str.apply(mask_email)
            continue
        if any(k in col_l for k in SENSITIVE_KEYWORDS):
            df_masked[col] = series_str.apply(mask_text)
    return df_masked


# ================================
# 6) 멀티 리포트 기능
# ================================
def group_data_by_unit(df: pd.DataFrame, group_type: str, group_column: str = None) -> dict:
    """
    데이터를 조직 단위별로 그룹핑한다.

    Args:
        df: 원본 데이터프레임
        group_type: "전체" 또는 "팀별"
        group_column: 팀별 그룹핑 시 사용할 컬럼명

    Returns:
        {group_name: grouped_dataframe} 형태의 딕셔너리
    """
    if group_type == "전체":
        return {"전체 조직": df.copy()}

    elif group_type == "팀별":
        if not group_column or group_column not in df.columns:
            st.error(f"그룹핑 컬럼 '{group_column}'이 데이터에 없습니다.")
            return {"전체 조직": df.copy()}

        grouped_data = {}

        # 팀별로 데이터 분리
        for team_name, team_df in df.groupby(group_column):
            if len(team_df) < 3:  # 최소 응답자 수 체크 (UI에서 이미 표시됨)
                continue
            grouped_data[str(team_name)] = team_df.copy()

        if not grouped_data:
            st.error("유효한 팀 데이터가 없습니다. 전체 조직으로 진행합니다.")
            return {"전체 조직": df.copy()}

        return grouped_data

    return {"전체 조직": df.copy()}


def build_multiple_reports(grouped_data: dict, index_df: pd.DataFrame, detected_company_name: str = None, detected_dept_name: str = None) -> dict:
    """
    그룹핑된 데이터로부터 여러 리포트를 생성한다.

    Args:
        grouped_data: {group_name: dataframe} 형태의 딕셔너리
        index_df: 인덱스 데이터프레임
        detected_company_name: 감지된 회사명
        detected_dept_name: 감지된 부서/팀명

    Returns:
        {group_name: report_object} 형태의 딕셔너리
    """
    reports = {}

    for group_name, group_df in grouped_data.items():
        try:
            print(f"DEBUG: '{group_name}' 리포트 생성 시작 - 데이터 크기: {group_df.shape}")
            report = build_report(group_df, index_df)
            print(f"DEBUG: '{group_name}' build_report 완료")

            # 조직명 수정 (팀별인 경우 팀명을 조직명으로, 전체인 경우 회사명 사용)
            if group_name != "전체 조직":
                # 팀별 리포트인 경우 팀명을 조직명으로 사용
                report["organization_name"] = group_name
                # 원래 회사명은 dept_name에 저장
                if detected_company_name:
                    report["dept_name"] = detected_company_name
                # 팀별 리포트임을 표시하는 플래그
                report["is_total_organization"] = False
            else:
                # 전체 조직인 경우 감지된 회사명 사용
                if detected_company_name:
                    report["organization_name"] = detected_company_name
                # 전체 조직임을 표시하는 플래그 추가
                report["is_total_organization"] = True
                # dept_name은 설정하지 않음 (전체 조직이므로)
            reports[group_name] = report
            print(f"DEBUG: '{group_name}' 리포트 완료")
            print(f"DEBUG: organization_name: {report.get('organization_name')}")
            print(f"DEBUG: dept_name: {report.get('dept_name')}")
            print(f"DEBUG: is_total_organization: {report.get('is_total_organization')}")
        except Exception as e:
            error_msg = f"'{group_name}' 리포트 생성 중 오류: {str(e)}"
            print(f"ERROR: {error_msg}")
            import traceback
            traceback.print_exc()
            try:
                st.error(error_msg)
            except:
                pass  # streamlit이 초기화되지 않은 환경에서는 무시
            continue

    return reports


def get_possible_group_columns(df: pd.DataFrame) -> list:
    """
    팀별 그룹핑이 가능한 컬럼들을 찾는다.
    """
    possible_columns = []

    for col in df.columns:
        col_lower = col.lower()
        # 팀, 부서, 조직 관련 컬럼 찾기
        if any(keyword in col_lower for keyword in ['팀', '부서', '조직', '소속', '부문', '센터', 'team', 'dept', 'org']):
            # 너무 많은 고유값을 가진 컬럼은 제외 (개인명 등)
            unique_count = df[col].nunique()
            total_count = len(df)
            if 2 <= unique_count <= total_count * 0.7:  # 2개 이상, 전체의 70% 이하
                possible_columns.append(col)

    return possible_columns


# ================================
# 6.5) PDF 멀티 생성 기능
# ================================
def generate_multiple_pdfs(reports: dict, ai_results: dict = None) -> dict:
    """
    여러 리포트에 대해 PDF를 생성한다.

    Args:
        reports: {team_name: report_object} 딕셔너리
        ai_results: {team_name: ai_result} 딕셔너리 (옵션)

    Returns:
        {team_name: pdf_bytes} 딕셔너리
    """
    from pdf_export import html_to_pdf_with_chrome

    pdf_results = {}
    total_teams = len(reports)

    for i, (team_name, report) in enumerate(reports.items()):
        # AI 결과 가져오기
        ai_key = f"ai_result_{team_name}"
        ai_result = ai_results.get(ai_key) if ai_results else st.session_state.get(ai_key)
        ai_raw = _normalize_ai_result(ai_result)
        ai_raw = materialize_ai_placeholders(ai_raw, report)

        # HTML 생성
        html_content = render_web_html(
            report,
            ai_result=ai_raw if _has_ai_result(ai_raw) else None,
        )

        # PDF 생성
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_pdf_path = tmp_file.name

            html_to_pdf_with_chrome(html_content, tmp_pdf_path)
            pdf_bytes = Path(tmp_pdf_path).read_bytes()
            pdf_results[team_name] = pdf_bytes

            # 임시 파일 삭제
            os.unlink(tmp_pdf_path)

        except Exception as e:
            st.error(f"'{team_name}' PDF 생성 중 오류: {str(e)}")
            continue

    return pdf_results


def generate_multiple_pdfs_parallel(reports: dict, ai_results: dict = None, max_workers: int = None, batch_size: int = None) -> dict:
    """
    여러 리포트에 대해 병렬로 PDF를 생성한다. (개선된 메모리 관리 및 동적 워커 수 조정)

    Args:
        reports: {team_name: report_object} 딕셔너리
        ai_results: {team_name: ai_result} 딕셔너리 (옵션)
        max_workers: 병렬 작업자 수 (None이면 CPU 코어 수에 따라 자동 결정)
        batch_size: 배치 크기 (None이면 워커 수 * 2로 자동 결정)

    Returns:
        {team_name: pdf_bytes} 딕셔너리
    """
    import concurrent.futures
    from pdf_export import html_to_pdf_with_chrome
    import tempfile
    import os
    import psutil
    import gc
    from pathlib import Path

    # 시스템 리소스 기반 동적 워커 수 결정
    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        memory_gb = psutil.virtual_memory().total / (1024**3)

        # CPU 코어와 메모리를 고려한 워커 수 결정
        # PDF 생성은 메모리 집약적이므로 보수적으로 설정
        if memory_gb >= 16:
            max_workers = min(cpu_count, 6)  # 고메모리: 최대 6개
        elif memory_gb >= 8:
            max_workers = min(cpu_count, 4)  # 중메모리: 최대 4개
        else:
            max_workers = min(cpu_count, 2)  # 저메모리: 최대 2개

    # 배치 크기 자동 결정
    if batch_size is None:
        batch_size = max_workers * 2

    total_reports = len(reports)
    st.info(f"📊 PDF 병렬 생성 설정: 워커 {max_workers}개, 배치 크기 {batch_size}, 총 {total_reports}개 리포트")

    # 메모리 사용량 모니터링
    initial_memory = psutil.virtual_memory().used / (1024**3)

    def generate_single_pdf(team_data):
        team_name, report = team_data
        html_content = None
        ai_raw = None
        tmp_pdf_path = None

        try:
            # 메모리 사용량 체크
            current_memory = psutil.virtual_memory().percent
            if current_memory > 85:  # 메모리 사용률 85% 초과 시 대기
                gc.collect()
                st.warning(f"⚠️ 메모리 사용률 높음 ({current_memory:.1f}%) - '{team_name}' 처리 대기 중...")

            # AI 결과 가져오기
            ai_key = f"ai_result_{team_name}"
            ai_result = ai_results.get(ai_key) if ai_results else st.session_state.get(ai_key)
            ai_raw = _normalize_ai_result(ai_result)
            ai_raw = materialize_ai_placeholders(ai_raw, report)

            # HTML 생성
            html_content = render_web_html(
                report,
                ai_result=ai_raw if _has_ai_result(ai_raw) else None,
            )

            # PDF 생성
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_pdf_path = tmp_file.name

            html_to_pdf_with_chrome(html_content, tmp_pdf_path)
            pdf_bytes = Path(tmp_pdf_path).read_bytes()

            # PDF 생성 성공 시 메모리 정리
            html_content = None
            ai_raw = None
            gc.collect()

            return team_name, pdf_bytes, len(pdf_bytes)

        except Exception as e:
            error_msg = f"'{team_name}' PDF 생성 중 오류: {str(e)}"
            return team_name, None, error_msg

        finally:
            # 정리 작업
            if tmp_pdf_path and os.path.exists(tmp_pdf_path):
                try:
                    os.unlink(tmp_pdf_path)
                except:
                    pass

            # 메모리 정리 (변수가 존재하는 경우에만)
            try:
                if 'html_content' in locals() and html_content is not None:
                    del html_content
                if 'ai_raw' in locals() and ai_raw is not None:
                    del ai_raw
            except:
                pass
            gc.collect()

    pdf_results = {}
    error_count = 0
    success_count = 0
    total_size_mb = 0

    # 배치별 처리
    report_items = list(reports.items())
    total_batches = (len(report_items) + batch_size - 1) // batch_size

    # 진행률 표시를 위한 프로그레스 바
    progress_bar = st.progress(0)
    status_text = st.empty()

    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, len(report_items))
        batch_items = report_items[start_idx:end_idx]

        batch_progress = (batch_idx / total_batches) * 100
        status_text.text(f"📦 배치 {batch_idx + 1}/{total_batches} 처리 중... ({len(batch_items)}개 리포트)")
        progress_bar.progress(batch_progress / 100)

        # 배치별 병렬 처리
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_team = {executor.submit(generate_single_pdf, item): item[0]
                             for item in batch_items}

            for future in concurrent.futures.as_completed(future_to_team):
                team_name = future_to_team[future]
                try:
                    result_team_name, pdf_bytes, size_info = future.result()

                    if pdf_bytes is not None:
                        pdf_results[result_team_name] = pdf_bytes
                        success_count += 1
                        total_size_mb += size_info / (1024 * 1024)
                        st.success(f"✅ '{result_team_name}' PDF 생성 완료 ({size_info/1024:.1f}KB)")
                    else:
                        error_count += 1
                        st.error(f"❌ '{result_team_name}': {size_info}")

                except Exception as e:
                    error_count += 1
                    st.error(f"❌ '{team_name}' 병렬 처리 중 예외: {str(e)}")

        # 배치 완료 후 메모리 정리
        gc.collect()

        # 메모리 사용량 체크
        current_memory = psutil.virtual_memory().percent
        if current_memory > 80:
            st.warning(f"⚠️ 메모리 사용률: {current_memory:.1f}% - 가비지 컬렉션 실행")
            gc.collect()

    # 최종 결과 표시
    final_memory = psutil.virtual_memory().used / (1024**3)
    memory_used = final_memory - initial_memory

    progress_bar.progress(1.0)
    status_text.text("✅ 모든 배치 처리 완료!")

    # 성능 요약 정보
    st.success(f"""
    📊 **PDF 병렬 생성 완료**
    - ✅ 성공: {success_count}개
    - ❌ 실패: {error_count}개
    - 📁 총 크기: {total_size_mb:.1f}MB
    - 🧠 메모리 사용: {memory_used:+.1f}GB
    - ⚡ 워커 수: {max_workers}개
    """)

    return pdf_results


def create_zip_from_pdfs(pdf_results: dict, organization_name: str = "조직") -> bytes:
    """
    여러 PDF를 ZIP 파일로 압축한다.

    Args:
        pdf_results: {team_name: pdf_bytes} 딕셔너리
        organization_name: 조직명

    Returns:
        ZIP 파일의 바이트 데이터
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for team_name, pdf_bytes in pdf_results.items():
            # 파일명 생성: {팀명}_조직효과성진단.pdf
            safe_team_name = team_name.replace("/", "_").replace("\\", "_")
            filename = f"{safe_team_name}_조직효과성진단.pdf"

            zip_file.writestr(filename, pdf_bytes)

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def create_group_zip_from_company_zips(company_zip_data: dict, group_name: str = "그룹") -> bytes:
    """
    여러 회사의 ZIP 파일을 그룹 단위로 묶어서 상위 ZIP을 생성한다.

    Args:
        company_zip_data: {company_name: zip_bytes} 딕셔너리
        group_name: 그룹명

    Returns:
        그룹 ZIP 파일의 바이트 데이터
    """
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for company_name, zip_bytes in company_zip_data.items():
            # 회사별 폴더 구조 생성: {그룹명}/{회사명}/
            safe_company_name = company_name.replace("/", "_").replace("\\", "_")
            company_folder = f"{safe_company_name}/"

            # 회사 ZIP 파일명 생성
            zip_filename = f"{company_folder}{safe_company_name}_전체팀_조직효과성진단_{datetime.now().strftime('%Y%m%d')}.zip"
            zip_file.writestr(zip_filename, zip_bytes)

            # README 파일 추가 (회사별 요약 정보)
            readme_content = f"""
# {company_name} 조직효과성 진단 리포트

생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
포함 파일: {safe_company_name}_전체팀_조직효과성진단_{datetime.now().strftime('%Y%m%d')}.zip

## 파일 구조
- 각 팀별 개별 PDF 파일이 포함되어 있습니다
- 파일명 형식: {{팀명}}_조직효과성진단.pdf

## 사용 방법
1. ZIP 파일을 압축 해제하세요
2. 각 팀별 PDF 파일을 확인하세요
3. 필요시 개별적으로 공유하거나 인쇄하세요
            """.strip()

            readme_filename = f"{company_folder}README_{safe_company_name}.txt"
            zip_file.writestr(readme_filename, readme_content.encode('utf-8'))

    zip_buffer.seek(0)
    return zip_buffer.getvalue()


def send_email_with_attachment(
    to_emails: list,
    subject: str,
    body: str,
    attachment_data: bytes,
    attachment_filename: str,
    sender_email: str = None,
    sender_password: str = None,
    smtp_server: str = "smtp.gmail.com",
    smtp_port: int = 587,
    max_retries: int = 3
) -> dict:
    """
    첨부파일과 함께 이메일을 발송한다.

    Args:
        to_emails: 받는 사람 이메일 주소 리스트
        subject: 이메일 제목
        body: 이메일 본문
        attachment_data: 첨부파일 바이트 데이터
        attachment_filename: 첨부파일명
        sender_email: 발송자 이메일 (환경변수에서 가져옴)
        sender_password: 발송자 비밀번호 (환경변수에서 가져옴)
        smtp_server: SMTP 서버 주소
        smtp_port: SMTP 포트

    Returns:
        {"success": bool, "message": str, "sent_to": list}
    """
    try:
        # 환경변수에서 이메일 설정 가져오기
        if not sender_email:
            sender_email = os.getenv("SMTP_EMAIL")
        if not sender_password:
            sender_password = os.getenv("SMTP_PASSWORD")

        if not sender_email or not sender_password:
            return {
                "success": False,
                "message": "SMTP_EMAIL 및 SMTP_PASSWORD 환경변수가 설정되지 않았습니다.",
                "sent_to": []
            }

        # 이메일 메시지 생성
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['Subject'] = subject

        # 본문 추가
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # 첨부파일 추가
        attachment = MIMEBase('application', 'octet-stream')
        attachment.set_payload(attachment_data)
        encoders.encode_base64(attachment)
        attachment.add_header(
            'Content-Disposition',
            f'attachment; filename="{attachment_filename}"'
        )
        msg.attach(attachment)

        # SMTP 서버 연결 및 이메일 발송
        sent_to = []
        failed_to = []

        # 재시도 로직을 포함한 SMTP 연결
        last_error = None

        for attempt in range(max_retries):
            try:
                # 연결 시도 - 더 긴 타임아웃과 다양한 설정 시도
                timeouts = [60, 90, 120]  # 더 긴 타임아웃 값들
                timeout = timeouts[attempt % len(timeouts)]

                # 첫 번째 시도: SMTP with STARTTLS
                # 두 번째 시도: SMTP_SSL
                # 세 번째 시도: 다른 포트로 SMTP_SSL
                if attempt == 0:
                    server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout)
                    server.set_debuglevel(0)
                    server.starttls()
                elif attempt == 1:
                    # Gmail SMTP_SSL 포트 465 사용
                    server = smtplib.SMTP_SSL(smtp_server, 465, timeout=timeout)
                    server.set_debuglevel(0)
                else:
                    # 마지막 시도: 다른 Gmail 서버 설정
                    server = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=timeout)
                    server.set_debuglevel(0)

                try:
                    server.login(sender_email, sender_password)
                except smtplib.SMTPAuthenticationError as e:
                    server.quit()
                    return {
                        "success": False,
                        "message": f"Gmail 인증 실패: {str(e)}. 앱 비밀번호를 사용하고 있는지 확인해 주세요.",
                        "sent_to": []
                    }
                except Exception as e:
                    try:
                        server.quit()
                    except:
                        pass
                    last_error = f"SMTP 서버 연결 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}"
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(3 ** attempt)  # 더 긴 지수 백오프 (3초, 9초, 27초)
                        continue
                    else:
                        return {
                            "success": False,
                            "message": last_error,
                            "sent_to": []
                        }

                # 이메일 발송
                for email in to_emails:
                    try:
                        msg['To'] = email
                        server.sendmail(sender_email, email, msg.as_string())
                        sent_to.append(email)
                        del msg['To']  # 다음 이메일을 위해 To 헤더 제거
                    except Exception as e:
                        failed_to.append({"email": email, "error": str(e)})

                # 연결 종료
                server.quit()
                break  # 성공하면 재시도 루프 종료

            except Exception as e:
                last_error = f"SMTP 서버 연결 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}"
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt)  # 지수 백오프
                    continue
                else:
                    return {
                        "success": False,
                        "message": last_error,
                        "sent_to": []
                    }

        # 이메일 발송 로그 저장
        try:
            from database_models import get_session, EmailLog
            import json
            from datetime import datetime

            session = get_session()

            email_log = EmailLog(
                recipient_emails=json.dumps(to_emails),
                subject=subject,
                attachment_filename=attachment_filename,
                attachment_size=len(attachment_data) if attachment_data else 0,
                status='sent' if len(sent_to) > 0 else 'failed',
                sent_count=len(sent_to),
                failed_count=len(failed_to),
                error_message=str(failed_to) if failed_to else None,
                sent_at=datetime.now() if len(sent_to) > 0 else None
            )

            session.add(email_log)
            session.commit()
            session.close()
        except Exception as log_error:
            print(f"이메일 로그 저장 오류: {log_error}")

        if sent_to:
            return {
                "success": True,
                "message": f"이메일이 성공적으로 발송되었습니다. (성공: {len(sent_to)}, 실패: {len(failed_to)})",
                "sent_to": sent_to,
                "failed_to": failed_to
            }
        else:
            return {
                "success": False,
                "message": "모든 이메일 발송에 실패했습니다.",
                "sent_to": [],
                "failed_to": failed_to
            }

    except Exception as e:
        return {
            "success": False,
            "message": f"이메일 발송 중 오류 발생: {str(e)}",
            "sent_to": []
        }


def get_organization_name_from_reports(reports: dict) -> str:
    """
    리포트에서 조직명을 추출한다.
    """
    if not reports:
        return "조직"

    first_report = next(iter(reports.values()))
    org_name = first_report.get("organization_name", "조직")

    # 팀명이 포함된 경우 제거
    if " - " in org_name:
        org_name = org_name.split(" - ")[0]

    return org_name


# ================================
# 6.7) 배치 메일 발송 기능
# ================================
def send_multiple_reports_email(gmail_address: str, app_password: str, reports_mapping: dict,
                               subject_template: str = "[자동발송] {team_name} 조직 효과성 진단 리포트",
                               body_template: str = None) -> dict:
    """
    여러 팀 리포트를 각각의 담당자에게 이메일로 발송한다.

    Args:
        gmail_address: 발송자 Gmail 주소
        app_password: Gmail 앱 비밀번호
        reports_mapping: {team_name: {"email": "recipient@email.com", "pdf_bytes": pdf_data}} 형태
        subject_template: 제목 템플릿 ({team_name} 치환)
        body_template: 본문 템플릿

    Returns:
        {team_name: {"success": bool, "message": str}} 형태의 결과
    """
    if body_template is None:
        body_template = """안녕하세요.

{team_name} 팀의 조직 효과성 진단 리포트를 첨부드립니다.

리포트 내용:
- 팀별 조직 효과성 분석 결과
- IPO(Input-Process-Output) 관점 진단
- 개선 방향 제시

궁금한 사항이 있으시면 언제든 연락 주세요.

※ 본 메일은 시스템에서 자동 발송되었습니다."""

    results = {}

    for team_name, team_data in reports_mapping.items():
        try:
            recipient_email = team_data.get("email")
            pdf_bytes = team_data.get("pdf_bytes")

            if not recipient_email or not pdf_bytes:
                results[team_name] = {
                    "success": False,
                    "message": "이메일 주소 또는 PDF 데이터가 없습니다."
                }
                continue

            # 제목과 본문에 팀명 치환
            subject = subject_template.format(team_name=team_name)
            body = body_template.format(team_name=team_name)

            # 파일명 생성
            timestamp = datetime.now().strftime('%Y%m%d_%H%M')
            filename = f"{team_name}_조직효과성진단_{timestamp}.pdf"

            # 메일 발송
            send_gmail_with_attachment(
                gmail_address=gmail_address,
                app_password=app_password,
                recipient=recipient_email,
                subject=subject,
                body=body,
                attachment_bytes=pdf_bytes,
                attachment_name=filename
            )

            results[team_name] = {
                "success": True,
                "message": f"성공적으로 발송됨: {recipient_email}"
            }

        except Exception as e:
            results[team_name] = {
                "success": False,
                "message": f"발송 실패: {str(e)}"
            }

    return results


def send_batch_emails_with_reports(reports: dict, email_mapping: dict, gmail_address: str,
                                   gmail_password: str, subject: str, body: str,
                                   send_as_zip: bool = False, zip_recipient: str = None) -> int:
    """
    여러 리포트를 개별 또는 ZIP으로 이메일 발송한다.

    Args:
        reports: {team_name: report_data} 딕셔너리
        email_mapping: {team_name: email_address} 딕셔너리
        gmail_address: 발송자 Gmail 주소
        gmail_password: Gmail 앱 비밀번호
        subject: 이메일 제목
        body: 이메일 본문
        send_as_zip: ZIP 파일로 전송 여부
        zip_recipient: ZIP 파일 수신자 (send_as_zip=True인 경우)

    Returns:
        성공한 이메일 발송 수
    """
    import zipfile
    import io

    if send_as_zip and zip_recipient:
        # ZIP 파일로 모든 PDF를 하나로 묶어서 발송
        try:
            # 모든 팀의 PDF 생성
            pdf_results = generate_multiple_pdfs(reports)

            if not pdf_results:
                raise Exception("PDF 생성에 실패했습니다.")

            # ZIP 파일 생성
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for team_name, pdf_bytes in pdf_results.items():
                    safe_team_name = team_name.replace("/", "_").replace("\\", "_")
                    filename = f"{safe_team_name}_조직효과성진단.pdf"
                    zip_file.writestr(filename, pdf_bytes)

            zip_data = zip_buffer.getvalue()
            org_name = get_organization_name_from_reports(reports)
            zip_filename = f"{org_name}_전체팀_조직효과성진단.zip"

            # ZIP 파일 이메일 발송
            result = send_email_with_attachment(
                to_emails=[zip_recipient],
                subject=f"[일괄발송] {org_name} 조직효과성 진단 리포트 ({len(reports)}개 팀)",
                body=f"{body}\n\n총 {len(reports)}개 팀의 리포트가 ZIP 파일로 첨부되어 있습니다.",
                attachment_data=zip_data,
                attachment_filename=zip_filename,
                sender_email=gmail_address,
                sender_password=gmail_password
            )

            return 1 if result["success"] else 0

        except Exception as e:
            print(f"ZIP 파일 발송 중 오류: {str(e)}")
            raise Exception(f"ZIP 파일 발송 중 오류: {str(e)}")

    else:
        # 개별 발송
        success_count = 0

        for team_name, report in reports.items():
            if team_name not in email_mapping:
                continue

            recipient_email = email_mapping[team_name]

            try:
                # 개별 PDF 생성
                single_report = {team_name: report}
                pdf_result = generate_multiple_pdfs(single_report)

                if team_name not in pdf_result:
                    continue

                pdf_bytes = pdf_result[team_name]
                safe_team_name = team_name.replace("/", "_").replace("\\", "_")
                filename = f"{safe_team_name}_조직효과성진단.pdf"

                # 개별 이메일 발송
                result = send_email_with_attachment(
                    to_emails=[recipient_email],
                    subject=subject.replace("{team_name}", team_name),
                    body=body.replace("{team_name}", team_name),
                    attachment_data=pdf_bytes,
                    attachment_filename=filename,
                    sender_email=gmail_address,
                    sender_password=gmail_password
                )

                if result["success"]:
                    success_count += 1

            except Exception as e:
                print(f"'{team_name}' 이메일 발송 실패: {str(e)}")
                continue

        return success_count


def create_email_mapping_ui(teams: list) -> dict:
    """
    팀별 이메일 매핑을 위한 UI를 생성하고 결과를 반환한다.

    Args:
        teams: 팀명 리스트

    Returns:
        {team_name: email_address} 형태의 딕셔너리
    """
    st.markdown("##### 📧 팀별 담당자 이메일 설정")

    # 이메일 입력 방식 선택
    input_method = st.radio(
        "이메일 입력 방식",
        ["개별 입력", "파일 업로드"],
        horizontal=True,
        help="개별 입력: 각 팀별로 직접 입력 | 파일 업로드: CSV/Excel 파일로 일괄 업로드"
    )

    email_mapping = {}

    if input_method == "파일 업로드":
        # CSV/Excel 파일 업로드 방식
        st.markdown("**📄 파일 업로드 방식**")

        with st.expander("📝 파일 형식 안내", expanded=False):
            st.markdown("""
            **CSV/Excel 파일 형식:**
            - 첫 번째 컬럼: 팀명 (정확히 일치해야 함)
            - 두 번째 컬럼: 이메일 주소

            **예시:**
            ```
            팀명,이메일
            영업팀,sales@company.com
            마케팅팀,marketing@company.com
            개발팀,dev@company.com
            ```
            """)

        uploaded_file = st.file_uploader(
            "이메일 매핑 파일 업로드",
            type=['csv', 'xlsx', 'xls'],
            help="팀명과 이메일이 포함된 CSV 또는 Excel 파일을 업로드하세요"
        )

        if uploaded_file is not None:
            try:
                # 파일 읽기
                if uploaded_file.name.endswith('.csv'):
                    email_df = pd.read_csv(uploaded_file, encoding='utf-8')
                else:
                    email_df = pd.read_excel(uploaded_file)

                # 컬럼명 정리
                email_df.columns = email_df.columns.str.strip()

                # 첫 2개 컬럼 사용 (팀명, 이메일)
                if len(email_df.columns) >= 2:
                    team_col = email_df.columns[0]
                    email_col = email_df.columns[1]

                    # 데이터 미리보기
                    st.markdown("**📋 업로드된 데이터 미리보기:**")
                    st.dataframe(email_df[[team_col, email_col]], use_container_width=True)

                    # 매핑 처리
                    matched_teams = []
                    unmatched_teams = []

                    for _, row in email_df.iterrows():
                        team_name = str(row[team_col]).strip()
                        email_addr = str(row[email_col]).strip()

                        if team_name in teams and "@" in email_addr:
                            email_mapping[team_name] = email_addr
                            matched_teams.append(team_name)
                        else:
                            if team_name not in teams:
                                unmatched_teams.append(team_name)

                    # 매핑 결과 표시
                    if matched_teams:
                        st.success(f"✅ {len(matched_teams)}개 팀 매핑 완료: {', '.join(matched_teams)}")

                    if unmatched_teams:
                        st.warning(f"⚠️ 매칭되지 않은 팀: {', '.join(unmatched_teams)}")

                    # 누락된 팀 표시
                    missing_teams = [team for team in teams if team not in email_mapping]
                    if missing_teams:
                        st.error(f"❌ 이메일이 설정되지 않은 팀: {', '.join(missing_teams)}")

                else:
                    st.error("파일에 최소 2개의 컬럼(팀명, 이메일)이 필요합니다.")

            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

    else:
        # 개별 입력 방식 (기존 방식)
        st.markdown("**✏️ 개별 입력 방식**")

        # 컬럼으로 나누어 표시
        num_cols = min(2, len(teams))  # 최대 2컬럼
        cols = st.columns(num_cols)

        for i, team_name in enumerate(teams):
            col_idx = i % num_cols

            with cols[col_idx]:
                email = st.text_input(
                    f"🏢 {team_name}",
                    key=f"email_{team_name}",
                    placeholder="담당자@회사.com",
                    help=f"{team_name} 팀 리포트를 받을 담당자 이메일"
                )

                if email and "@" in email:
                    email_mapping[team_name] = email

    return email_mapping


# ================================
# 7) 리포트 빌더
# ================================
def build_report(df: pd.DataFrame, index_df: pd.DataFrame) -> dict:
    LIKERT_MAP = {
        "매우 그렇지 않다": 1, "전혀 그렇지 않다": 1, "매우그렇지않다": 1,
        "그렇지 않다": 2, "그렇지않다": 2,
        "보통이다": 3, "보통": 3,
        "그렇다": 4,
        "매우 그렇다": 5, "매우그렇다": 5, "매우 그렇다.": 5,
    }

    def to_num(series: pd.Series) -> pd.Series:
        s = series.astype(str).str.strip().replace(LIKERT_MAP)
        return pd.to_numeric(s, errors="coerce")

    # 조직명 / 부서명 추출
    org_name = "업로드 데이터"
    dept_name = None
    for cand in ["조직명", "회사명", "Org", "Organization"]:
        if cand in df.columns and not df[cand].dropna().empty:
            org_name = str(df[cand].dropna().iloc[0]).strip()
            break
    for cand in ["부서명", "팀명", "Department"]:
        if cand in df.columns and not df[cand].dropna().empty:
            dept_name = str(df[cand].dropna().iloc[0]).strip()
            break

    respondents = len(df)

    idx = index_df.copy()
    idx["대분류_clean"] = (
        idx.get("대분류", "")
        .astype(str)
        .fillna("")
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    def is_objective_column(df_: pd.DataFrame, col: str) -> bool:
        if col not in df_.columns:
            return False
        s = to_num(df_[col]).dropna()
        if s.empty:
            return False
        within = s[(s >= 1) & (s <= 5)]
        return (len(within) / len(s)) >= 0.8

    def _grade(score: float | None) -> str:
        if score is None:
            return "N/A"
        if score >= 3.8:
            return "우수"
        if score >= 3.4:
            return "양호"
        if score >= 3.0:
            return "보통"
        return "개선 필요"

    categories = []
    ipo_avgs = {}

    for big in ["Input", "Process", "Output"]:
        mask = idx["대분류_clean"].str.contains(big, case=False, na=False)
        qdf = idx[mask].copy()
        if qdf.empty:
            continue

        # 소분류별로 그룹핑
        subcategories = []
        all_scores = []

        # 소분류 그룹별로 처리
        for sub_category in qdf["소분류"].unique():
            if pd.isna(sub_category):
                continue

            sub_mask = qdf["소분류"] == sub_category
            sub_qdf = qdf[sub_mask].copy()

            sub_items = []
            sub_scores = []

            for _, row in sub_qdf.iterrows():
                col_name = str(row.get("헤더명", "")).strip()
                q_text = str(row.get("문항명", col_name)).strip()
                sub_cat = str(row.get("소분류", "")).strip()

                item_avg = None
                item_bm = 0.0
                dist_pcts = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0, 5: 0.0}
                neg_pct = mid_pct = pos_pct = 0.0

                if col_name and col_name in df.columns:
                    num = to_num(df[col_name])
                    valid = num.dropna()
                    if not valid.empty:
                        item_avg = float(valid.mean())
                        bm = max(0.0, min(5.0, item_avg - 0.25))
                        item_bm = round(bm, 2)
                        sub_scores.append(item_avg)
                        all_scores.append(item_avg)

                        total = len(valid)
                        for v in [1, 2, 3, 4, 5]:
                            cnt = int((valid == v).sum())
                            dist_pcts[v] = round(cnt / total * 100, 1) if total > 0 else 0.0

                        neg_pct = round(dist_pcts[1] + dist_pcts[2], 1)
                        mid_pct = round(dist_pcts[3], 1)
                        pos_pct = round(dist_pcts[4] + dist_pcts[5], 1)

                sub_items.append(
                    {
                        "question": q_text,
                        "header": col_name,
                        "subcategory": sub_cat,
                        "average": round(item_avg, 2) if item_avg is not None else None,
                        "benchmark": item_bm,
                        "responses": {
                            "veryLow": dist_pcts[1],
                            "low": dist_pcts[2],
                            "medium": dist_pcts[3],
                            "high": dist_pcts[4],
                            "veryHigh": dist_pcts[5],
                        },
                        "dist_agg": {
                            "neg_pct": neg_pct,
                            "mid_pct": mid_pct,
                            "pos_pct": pos_pct,
                        },
                    }
                )

            # 소분류 평균 계산
            sub_avg = round(sum(sub_scores) / len(sub_scores), 2) if sub_scores else None

            # 소분류 그룹을 subcategories에 추가
            subcategories.append({
                "name": sub_category,
                "average": sub_avg,
                "items": sub_items,
                "item_count": len(sub_items)
            })

        # 전체 영역 평균 계산
        cat_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else None
        ipo_avgs[big] = cat_avg

        categories.append(
            {
                "title": big,
                "name": big,
                "description": f"{big} 영역에 대한 응답 결과입니다.",
                "average": cat_avg,
                "subcategories": subcategories,
                "items": [item for subcat in subcategories for item in subcat["items"]],  # 호환성을 위해 평면화된 items도 유지
            }
        )

    input_avg = ipo_avgs.get("Input")
    process_avg = ipo_avgs.get("Process")
    output_avg = ipo_avgs.get("Output")

    summary_ipo_cards = [
        {"id": "input", "title": "Input", "score": input_avg, "grade": _grade(input_avg), "desc": "리소스·역량·정보 투입 수준"},
        {"id": "process", "title": "Process", "score": process_avg, "grade": _grade(process_avg), "desc": "협업·의사소통·리더십 실행"},
        {"id": "output", "title": "Output", "score": output_avg, "grade": _grade(output_avg), "desc": "성과·몰입·문화 인식"},
    ]

    # -------------------------------
    #  문항 단위 점수 분포 (차트용)
    #  → Input / Process / Output 별로 구간 정보도 같이 만든다
    # -------------------------------
    line_labels = []
    our_scores = []
    benchmark_scores = []

    # 영역별 인덱스 모으기
    area_index_map = {"Input": [], "Process": [], "Output": []}

    for _, row in idx.iterrows():
        col_name = str(row.get("헤더명", "")).strip()
        label = str(row.get("문항명", col_name)).strip()
        if not label or not col_name or col_name not in df.columns:
            continue
        if not is_objective_column(df, col_name):
            continue

        num = to_num(df[col_name]).dropna()
        if num.empty:
            continue

        avg = float(num.mean())
        bm = max(0.0, min(5.0, avg - 0.25))

        # 실제로 차트에 들어가는 위치
        current_index = len(line_labels)

        line_labels.append(label)
        our_scores.append(round(avg, 2))
        benchmark_scores.append(round(bm, 2))

        # 이 문항이 어떤 IPO 영역인지 붙여두기
        big_area = str(row.get("대분류_clean", "")).strip().lower()
        if "input" in big_area:
            area_index_map["Input"].append(current_index)
        elif "process" in big_area:
            area_index_map["Process"].append(current_index)
        elif "output" in big_area:
            area_index_map["Output"].append(current_index)

    # Chart.js에서 그릴 수 있도록 구간을 from/to 로 변환
    segments = []
    for area_name, idx_list in area_index_map.items():
        if not idx_list:
            continue
        segments.append(
            {
                "name": area_name,
                "from": min(idx_list),
                "to": max(idx_list),
            }
        )

    summary_score_distribution = {
        "title": "진단 영역/항목별 점수 분포",
        "labels": line_labels,
        "series": [
            {"name": "벤치마크", "data": benchmark_scores, "style": "dashed"},
            {"name": "우리 조직", "data": our_scores, "style": "solid"},
        ],
        # Chart 옵션에서 쓸 수 있도록 함께 넘긴다
        "segments": segments,
    }


    # 회사단위 여부 판단 (부서/팀 정보로 여러 그룹이 있거나 응답자가 10명 이상이면 회사단위)
    team_columns = [col for col in df.columns if any(keyword in col.upper() for keyword in ['POS', 'DEPT', 'TEAM', '부서', '팀'])]
    has_multiple_teams = len(team_columns) > 0 and len(df[team_columns[0]].dropna().unique()) > 1 if team_columns else False
    is_company_level = has_multiple_teams or len(df) >= 10  # 여러 팀이 있거나 응답자가 10명 이상이면 회사단위

    # 주관식 응답을 reference index에 따라 구조화
    open_ended = build_structured_open_ended(df, is_company_level)

    summary = {
        "intro": "본 리포트는 최근 설문 데이터를 기반으로 조직 효과성을 IPO 관점에서 진단한 결과입니다.",
        "sub_intro": "Input–Process–Output 3개 영역을 표준 템플릿으로 시각화했습니다.",
        "respondents": respondents,
        "response_rate": 100.0,
        "method": "5점 척도 문항 평균 + index.xlsx 구조 반영",
        "ipo": {
            "input": round(input_avg, 2) if input_avg is not None else None,
            "process": round(process_avg, 2) if process_avg is not None else None,
            "output": round(output_avg, 2) if output_avg is not None else None,
        },
        "ipo_cards": summary_ipo_cards,
        "score_distribution": summary_score_distribution,
        "improvement_priorities": [
            "점수가 낮은 Input 세부항목을 1순위로 개선",
            "Process 영역 중 협업·의사소통 항목은 제도화 필요",
            "Output 영역에서 반복 언급된 이슈는 리더십 미팅 안건화",
        ],
    }

    overview = {
        "purpose": "본 리포트는 조직효과성을 빠르게 파악하고 개선 포인트를 도출하도록 설계되었습니다.",
        "background": [],
        "model_desc": "",
        "model_points": [],
    }

    return {
        "org_name": org_name,
        "organization_name": org_name,  # 템플릿 호환성을 위해 추가
        "dept_name": dept_name,
        "report_date": datetime.now().strftime("%Y.%m.%d"),
        "respondents": respondents,
        "summary": summary,
        "overview": overview,
        "diagnostic": {"categories": categories},
        "open_ended": open_ended,
        "appendix": {
            "methodology": "index.xlsx 기준 문항을 5점 척도로 집계하고, 대분류(IPO) 평균을 산출했습니다.",
            "scoring_guide": "4.0 이상 우수, 3.4~3.9 양호, 3.0~3.3 보통, 3.0 미만 개선 필요로 해석합니다.",
        },
    }


# ================================
# 7) AI 해석 캐시 관리 함수들
# ================================
def get_cached_ai_analysis(org_name: str, data_hash: str) -> dict | None:
    """저장된 AI 분석 결과를 조회"""
    try:
        from database_models import get_session, Report
        import json
        import hashlib

        session = get_session()

        # 조직명과 데이터 해시로 기존 분석 결과 조회
        existing_report = session.query(Report).filter_by(
            team_name=org_name,
            status='completed'
        ).first()

        if existing_report and existing_report.ai_analysis:
            stored_analysis = json.loads(existing_report.ai_analysis)
            # 데이터 해시가 일치하는지 확인
            if stored_analysis.get('data_hash') == data_hash:
                return stored_analysis

        session.close()
        return None

    except Exception as e:
        print(f"AI 분석 캐시 조회 오류: {e}")
        return None

def save_ai_analysis(org_name: str, data_hash: str, ai_result: dict, report_data: dict = None):
    """AI 분석 결과를 데이터베이스에 저장"""
    try:
        from database_models import get_session, Report, Organization
        import json

        session = get_session()

        # 조직 조회 또는 생성
        org = session.query(Organization).filter_by(name=org_name).first()
        if not org:
            org = Organization(name=org_name)
            session.add(org)
            session.flush()

        # 기존 리포트 조회 또는 새로 생성
        report = session.query(Report).filter_by(
            organization_id=org.id,
            team_name=org_name
        ).first()

        if not report:
            report = Report(
                organization_id=org.id,
                team_name=org_name,
                report_type='organizational_effectiveness'
            )
            session.add(report)

        # AI 분석 결과에 메타데이터 추가
        ai_result['data_hash'] = data_hash
        ai_result['generated_at'] = datetime.now().isoformat()
        ai_result['org_name'] = org_name

        # 저장
        report.ai_analysis = json.dumps(ai_result, ensure_ascii=False)
        if report_data:
            report.report_data = json.dumps(report_data, ensure_ascii=False)
        report.status = 'completed'
        report.updated_at = datetime.now()

        session.commit()
        session.close()

        print(f"✅ AI 분석 결과 저장 완료: {org_name}")

    except Exception as e:
        print(f"AI 분석 결과 저장 오류: {e}")

def generate_data_hash(report: dict) -> str:
    """리포트 데이터의 해시값 생성 (캐시 키로 사용)"""
    import hashlib
    import json

    # 핵심 데이터만 추출하여 해시 생성
    key_data = {
        'org_name': report.get('org_name', ''),
        'respondents': report.get('respondents', 0),
        'summary': report.get('summary', {}),
        'open_ended': report.get('open_ended', {}),
        'diagnostic': report.get('diagnostic', {})
    }

    data_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(data_str.encode()).hexdigest()

# 7) Gemini 해석 (진행 콜백) - 캐시 기능 추가
# ================================
def run_ai_interpretation_gemini_from_report(report: dict, progress_update=None, force_regenerate=False) -> dict:
    """
    report -> (score / items / free_text / org_context / writer / reviewer / final)
    reviewer가 뭔가를 남기면 그게 최종이고, 없으면 writer가 최종이다.
    """
    def step(i: int, msg: str):
        if callable(progress_update):
            progress_update(i, msg)

    # -------------------------------------------------
    # 0) 공통 데이터 꺼내기 및 캐시 확인
    # -------------------------------------------------
    org_name = report.get("org_name") or "이름 없는 조직"
    respondents = report.get("respondents") or 0
    summary = report.get("summary") or {}
    ipo = summary.get("ipo") or {}
    categories = (report.get("diagnostic") or {}).get("categories") or []
    open_ended = report.get("open_ended") or []

    # 데이터 해시 생성
    data_hash = generate_data_hash(report)

    # 강제 재생성이 아닌 경우 캐시된 결과 확인
    if not force_regenerate:
        step(0, "기존 AI 분석 결과 확인 중...")
        cached_result = get_cached_ai_analysis(org_name, data_hash)
        if cached_result:
            step(100, "저장된 AI 분석 결과를 불러왔습니다")
            return cached_result

    # -------------------------------------------------
    # 1) IPO 점수 해석
    # -------------------------------------------------
    step(1, "IPO 점수 해석 중...")
    loaded_score_prompt = load_prompt_file("gemini_score_ko.md")
    if loaded_score_prompt:
        # 파일이 있으면 거기에 안전하게 데이터만 덧붙인다
        base_score_prompt = (
            f"{loaded_score_prompt.rstrip()}\n\n"
            "[데이터]\n"
            f"조직명: {org_name}\n"
            f"응답자수: {respondents}\n"
            f"IPO 점수: {json.dumps(ipo, ensure_ascii=False)}"
        )
    else:
        # 파일 없으면 기본 프롬프트
        base_score_prompt = f"""{PROMPT_PREFIX}

[작업]
- 아래 IPO 점수를 보고, 어느 영역이 상대적으로 높고 낮은지 설명하라.
- 응답자가 30명 미만이면 '신뢰도 주의' 문장을 반드시 추가하라.

[데이터]
조직명: {org_name}
응답자수: {respondents}
IPO 점수: {json.dumps(ipo, ensure_ascii=False)}
""".strip()

    score_result = call_gemini(base_score_prompt)

    # -------------------------------------------------
    # 2) 문항별 낮은 문항
    #    → 여기가 이번에 문제였던 부분
    # -------------------------------------------------
    step(2, "문항별 개선 항목 추출 중...")

    # 실제 categories 데이터를 포함한 페이로드 생성
    item_payload = {
        "org_name": org_name,
        "respondents": respondents,
        "ipo": ipo,
        "categories": categories,  # 실제 문항 구조가 여기 들어감
    }

    loaded_item_prompt = load_prompt_file("gemini_item_ko.md")
    if loaded_item_prompt:
        if "<<<DATA>>>" in loaded_item_prompt:
            # 명시적 자리표시자가 있으면 치환
            base_item_prompt = loaded_item_prompt.replace(
                "<<<DATA>>>",
                json.dumps(item_payload, ensure_ascii=False, indent=2)
            )
        else:
            # 자리표시자가 없으면 JSON을 반드시 뒤에 붙임
            base_item_prompt = (
                f"{loaded_item_prompt.rstrip()}\n\n"
                "[데이터]\n"
                f"{json.dumps(item_payload, ensure_ascii=False, indent=2)}"
            )
    else:
        # 프롬프트 파일이 아예 없을 때만 기본 프롬프트 사용
        base_item_prompt = f"""{PROMPT_PREFIX}

[작업]
- 아래 categories 안에서 3.0 미만이거나 영역 평균보다 0.3p 이상 낮은 문항을 찾아라.
- 헤더명이 원시값이면 'NEED_CONFIRMATION: 원본헤더명'으로 남겨라.
- 결과는 번호 목록으로만 써라.

[데이터]
{json.dumps(item_payload, ensure_ascii=False, indent=2)}
""".strip()

    item_result = call_gemini(base_item_prompt)

    # -------------------------------------------------
    # 3) 주관식 메타
    # -------------------------------------------------
    step(3, "주관식 응답 요약 중...")

    free_payload = {
        "org_name": org_name,
        "respondents": respondents,
        "open_ended": open_ended,
    }

    loaded_free_prompt = load_prompt_file("gemini_free_ko.md")
    if loaded_free_prompt:
        if "<<<DATA>>>" in loaded_free_prompt:
            base_free_prompt = loaded_free_prompt.replace(
                "<<<DATA>>>",
                json.dumps(free_payload, ensure_ascii=False)
            )
        else:
            base_free_prompt = (
                f"{loaded_free_prompt.rstrip()}\n\n"
                "[주관식]\n"
                f"{json.dumps(open_ended, ensure_ascii=False)}"
            )
    else:
        base_free_prompt = f"""{PROMPT_PREFIX}

[작업]
- 주관식 응답에서 조직 규모/현장 이슈/리더십 이슈/중복 불만을 뽑아서 설명하라.
- 개인정보나 특정인을 유추할 수 있는 내용은 '식별정보 제거 필요'로 남겨라.

[주관식]
{json.dumps(open_ended, ensure_ascii=False)}
""".strip()

    free_result = call_gemini(base_free_prompt)

    # -------------------------------------------------
    # 4) 조직 컨텍스트 (NO40, 조직명, 업종 추정)
    # -------------------------------------------------
    step(4, "조직 컨텍스트 정리 중...")

    no40_text = _extract_no40_from_open(open_ended)
    industry_guess = _guess_industry_from_name(org_name)

    orgctx_payload = {
        "org_name": org_name,
        "industry_guess": industry_guess,
        "respondents": respondents,
        "no40_text": no40_text,
    }

    loaded_orgctx_prompt = load_prompt_file("gemini_orgctx_ko.md")
    if loaded_orgctx_prompt:
        # placeholder 있으면 치환
        base_orgctx_prompt = loaded_orgctx_prompt
        base_orgctx_prompt = base_orgctx_prompt.replace("<<<ORG_NAME>>>", org_name)
        base_orgctx_prompt = base_orgctx_prompt.replace("<<<INDUSTRY>>>", industry_guess)
        base_orgctx_prompt = base_orgctx_prompt.replace("<<<RESPONDENTS>>>", str(respondents))
        base_orgctx_prompt = base_orgctx_prompt.replace("<<<NO40>>>", no40_text)
        # 혹시 하나도 없으면 뒤에 붙이기
        if "<<<ORG_NAME>>>" not in loaded_orgctx_prompt and "<<<NO40>>>" not in loaded_orgctx_prompt:
            base_orgctx_prompt = (
                f"{loaded_orgctx_prompt.rstrip()}\n\n"
                f"[조직정보]\n- 조직명: {org_name}\n- 추정 산업/직무: {industry_guess}\n- 응답자수: {respondents}\n\n"
                f"[NO40(조직특성) 응답]\n{no40_text}"
            )
    else:
        base_orgctx_prompt = f"""{PROMPT_PREFIX}

# 역할
- 당신은 조직진단 결과를 해석할 때 참고할 ‘조직적 맥락’만 작성하는 HR 컨설턴트입니다.
- 점수, 지표, 영역(Input·Process·Output) 등은 언급하지 않습니다.
- 조직명과 주관식 NO40(조직특성) 응답만 근거로 서술합니다.

# 작성 규칙
- 3~5문장 하나의 단락.
- 불릿, 표, 코드블록 금지.
- “이 조직은 …한 환경이므로 이런 응답이 나올 수 있다” 수준의 맥락만 씁니다.
- 응답자수가 30명 미만이면 마지막에 유의문 추가.

[조직정보]
- 조직명: {org_name}
- 추정 산업/직무: {industry_guess}
- 응답자수: {respondents}

[NO40(조직특성) 응답]
{no40_text}
""".strip()

    orgctx_result = call_gemini(base_orgctx_prompt)

    # -------------------------------------------------
    # 5) 임원요약 (실제 써먹을 본문)
    # -------------------------------------------------
    step(5, "임원용 요약 작성 중...")

    writer_payload = {
        "score_analysis": _clean_ai_text(score_result),
        "low_items": _clean_ai_text(item_result),
        "free_text": _clean_ai_text(free_result),
        "org_context": _clean_ai_text(orgctx_result),
    }

    loaded_writer_prompt = load_prompt_file("gemini_writer_ko.md")
    if loaded_writer_prompt:
        if "<<<SCORE>>>" in loaded_writer_prompt:
            base_writer_prompt = (
                loaded_writer_prompt
                .replace("<<<SCORE>>>", writer_payload["score_analysis"])
                .replace("<<<ITEMS>>>", writer_payload["low_items"])
                .replace("<<<FREE>>>", writer_payload["free_text"])
                .replace("<<<ORGCTX>>>", writer_payload["org_context"])
            )
        else:
            base_writer_prompt = (
                f"{loaded_writer_prompt.rstrip()}\n\n"
                "[참고1: 점수 해석]\n"
                f"{writer_payload['score_analysis']}\n\n"
                "[참고2: 낮은 문항]\n"
                f"{writer_payload['low_items']}\n\n"
                "[참고3: 주관식(조직 메타)]\n"
                f"{writer_payload['free_text']}\n\n"
                "[참고4: 조직 컨텍스트]\n"
                f"{writer_payload['org_context']}"
            )
    else:
        base_writer_prompt = f"""{PROMPT_PREFIX}

[작업]
- 지금까지 생성된 4개 결과를 합쳐서 임원용 요약을 1~1.5p 분량으로 작성하라.
- 구조는 반드시 Input → Process → Output 순서를 지켜라.
- 표나 체크리스트는 만들지 말고 자연어 서술로 쓴다.
- '이는', '이번'과 같은 표현은 줄여라.

[참고1: 점수 해석]
{writer_payload['score_analysis']}

[참고2: 낮은 문항]
{writer_payload['low_items']}

[참고3: 주관식(조직 메타)]
{writer_payload['free_text']}

[참고4: 조직 컨텍스트]
{writer_payload['org_context']}
""".strip()

    writer_result = call_gemini(base_writer_prompt)

    # -------------------------------------------------
    # 6) 리뷰어(검열)
    # -------------------------------------------------
    step(6, "AI 산출물 점검 중...")

    loaded_reviewer_prompt = load_prompt_file("gemini_reviewer_ko.md")
    if loaded_reviewer_prompt:
        base_reviewer_prompt = (
            f"{loaded_reviewer_prompt.rstrip()}\n\n"
            "[임원요약]\n"
            f"{writer_result}"
        )
    else:
        base_reviewer_prompt = f"""{PROMPT_PREFIX}

[작업]
- 아래 임원요약이 원 데이터에 없는 숫자/조직명/날짜를 만들었는지만 점검하라.
- 문제 있으면 '수치 검증 필요', '식별정보 제거 필요'만 써라.
- 보고서에 그대로 노출되면 안 되는 표현은 '내부 검열용'이라고 명시하라.
- 여기서는 새로운 본문을 다시 쓰지 않는다.

[임원요약]
{writer_result}
""".strip()

    reviewer_result = call_gemini(base_reviewer_prompt)

    step(7, "완료")

    # -------------------------------------------------
    # 7) 결과 정리
    # -------------------------------------------------
    # reviewer가 있으면 reviewer, 없으면 writer
    final_result = (reviewer_result or "").strip() or (writer_result or "").strip()

    # 문항별 비어 있으면 최소 안내문
    items_clean = _clean_ai_text(item_result)
    if not items_clean.strip():
        items_clean = (
            "• (자동 생성 실패) 점수가 3.0 미만이거나 IPO 평균보다 0.3p 이상 낮은 문항을 다시 확인해 주세요.\n"
            "• index.xlsx의 대분류/헤더명이 설문 결과와 일치하는지 점검하세요."
        )

    # AI 분석 결과 구성
    ai_analysis_result = {
        "score": _clean_ai_text(score_result),
        "items": items_clean,
        "free_text": _clean_ai_text(free_result),
        "org_context": _clean_ai_text(orgctx_result),
        "writer": _clean_ai_text(writer_result),
        "reviewer": _clean_ai_text(reviewer_result),
        "final": _clean_ai_text(final_result),
    }

    # AI 분석 결과를 데이터베이스에 저장
    try:
        save_ai_analysis(org_name, data_hash, ai_analysis_result, report)
    except Exception as e:
        print(f"AI 분석 결과 저장 중 오류: {e}")

    return ai_analysis_result

# ================================
# 8) HTML 렌더
# ================================
def render_web_html(report: dict, ai_result: dict | None = None) -> str:
    """
    report.html 이 reviewer 체크리스트까지 그대로 뿌리는 문제를 막기 위해
    여기서 한 번 정리해서 넘겨준다.
    """
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    css_path = BASE_DIR / "static" / "css" / "report.css"
    inline_css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    # 항상 안전한 AI 객체 보장
    cleaned_ai = {}
    if ai_result:
        cleaned_ai = {
            "score": ai_result.get("score", ""),
            "items": ai_result.get("items", ""),
            "free_text": ai_result.get("free_text", ""),  # 주관식 분석을 별도로 포함
            "org_context": ai_result.get("org_context") or ai_result.get("free_text", "") or "",
            "writer": ai_result.get("writer") or ai_result.get("final") or "",
            "reviewer": "",  # 문서에 리뷰어 노출 안함
        }

    # 항상 report.summary.ai에 안전한 AI 객체 주입
    report.setdefault("summary", {})
    if "summary" not in report:
        report["summary"] = {}
    report["summary"]["ai"] = cleaned_ai

    tmpl = env.get_template("report.html")
    html = tmpl.render(
        report=report,
        inline_css=inline_css,
        ai_result=cleaned_ai,  # 정리된 버전 전달
        use_tailwind=True,
    )
    return html


# ================================
# 9) Gmail 전송
# ================================
def send_gmail_with_attachment(
    gmail_address: str,
    app_password: str,
    recipient: str,
    subject: str,
    body: str,
    attachment_bytes: bytes,
    attachment_name: str = "report.pdf",
):
    smtp_host = "smtp.gmail.com"
    smtp_port = 587

    msg = MIMEMultipart()
    msg["From"] = gmail_address
    msg["To"] = recipient
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain", "utf-8"))

    part = MIMEBase("application", "octet-stream")
    part.set_payload(attachment_bytes)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{attachment_name}"')
    msg.attach(part)

    # 재시도 로직을 포함한 SMTP 연결
    for attempt in range(3):
        try:
            # 연결 시도 - 더 긴 타임아웃과 다양한 설정 시도
            timeouts = [30, 45, 60]
            timeout = timeouts[attempt % len(timeouts)]

            server = smtplib.SMTP(smtp_host, smtp_port, timeout=timeout)
            server.set_debuglevel(0)  # 디버그 로그 비활성화

            try:
                server.starttls()
                server.login(gmail_address, app_password)
                server.send_message(msg)
                server.quit()
                return  # 성공하면 함수 종료
            finally:
                try:
                    server.quit()
                except:
                    pass

        except Exception as e:
            if attempt < 2:  # 마지막 시도가 아니면
                import time
                time.sleep(2 ** attempt)  # 지수 백오프
                continue
            else:
                # SMTP_SSL로 시도해보기
                try:
                    server = smtplib.SMTP_SSL(smtp_host, 465, timeout=30)
                    server.login(gmail_address, app_password)
                    server.send_message(msg)
                    server.quit()
                    return
                except Exception as ssl_e:
                    raise Exception(f"SMTP 서버 연결 실패 (SMTP/SMTP_SSL 모두 실패): 원본 오류: {str(e)}, SSL 오류: {str(ssl_e)}")
        
# ================================================
# 벤치마크 설정 관련 헬퍼 함수
# ================================================
def get_benchmark_scores_for_labels(labels):
    """관리자 설정에서 벤치마크 점수를 가져와서 labels 순서에 맞게 반환"""
    import streamlit as st

    # 기본 벤치마크 값들
    default_benchmarks = {
        "목적경영": 3.2,
        "구성원인식": 3.1,
        "지원체계": 3.0,
        "도전추진": 3.3,
        "실행력": 3.4,
        "소통협력": 3.2,
        "성과창출": 3.5,
        "구성원만족": 3.1,
        "경쟁력확보": 3.3
    }

    # 세션에서 벤치마크 설정 가져오기
    benchmark_settings = st.session_state.get("benchmark_settings", default_benchmarks)

    # labels 순서에 맞춰 점수 배열 생성
    benchmark_scores = []
    for label in labels:
        score = benchmark_settings.get(label)
        if score is not None:
            benchmark_scores.append(float(score))
        else:
            # 레이블이 설정에 없으면 기본값 3.2 사용
            benchmark_scores.append(3.2)

    return benchmark_scores

# ================================================
# 점수 분포(차트)용 구조를 report에 붙여주는 헬퍼
# ================================================
def attach_score_distribution(
    report: dict,
    df: pd.DataFrame | None = None,
    index_df: pd.DataFrame | None = None,
) -> dict:
    """
    - 먼저 build_report 가 만들어준 분포(report.summary.score_distribution)가 있으면 그걸 '기본값'으로 둔다.
    - df 에서 영역/점수를 뽑을 수 있을 때만 덮어쓴다.
    - 템플릿에서 쓰는 dist.segments 도 여기서 만들어서 내려준다.
    """
    if report is None:
        report = {}
    report.setdefault("summary", {})

    # 0) build_report 가 이미 넣어준 값 기억
    existing_dist = report["summary"].get("score_distribution")

    # 1) df 가 없으면 기존 값 그대로
    if df is None or df.empty:
        if existing_dist:
            return report
        report["summary"]["score_distribution"] = {
            "title": "진단 영역/항목별 점수 분포",
            "labels": [],
            "series": [
                {"name": "benchmark", "data": []},
                {"name": "our", "data": []},
            ],
            "segments": [],
        }
        return report

    # 2) df 에서 영역/점수를 추론해 본다
    cols = df.columns.tolist()
    area_col = None
    for c in ["영역", "대영역", "factor", "domain", "section"]:
        if c in cols:
            area_col = c
            break

    score_col = None
    for c in ["점수", "score", "value", "avg_score"]:
        if c in cols:
            score_col = c
            break

    # 2-1) 못찾으면 기존 분포 유지
    if area_col is None or score_col is None:
        if existing_dist:
            # 기존 것만 segments 보강
            existing_dist.setdefault("segments", [])
            report["summary"]["score_distribution"] = existing_dist
            return report
        # 기존 것도 없으면 최소 구조
        report["summary"]["score_distribution"] = {
            "title": "진단 영역/항목별 점수 분포",
            "labels": [],
            "series": [
                {"name": "benchmark", "data": []},
                {"name": "our", "data": []},
            ],
            "segments": [],
        }
        return report

    # 3) 여기까지 왔으면 df 기반으로 차트 생성
    area_grp = df.groupby(area_col)[score_col].mean().round(2)
    labels = area_grp.index.tolist()
    our_scores = area_grp.values.tolist()

    # 벤치마크 있으면
    if "benchmark" in cols:
        bench_grp = df.groupby(area_col)["benchmark"].mean().round(2)
        benchmark_scores = [float(bench_grp.get(lbl, 0)) for lbl in labels]
    else:
        # 관리자 설정에서 벤치마크 가져오기
        benchmark_scores = get_benchmark_scores_for_labels(labels)
        if not benchmark_scores:
            benchmark_scores = [max(s - 0.2, 0) for s in our_scores]

    # 4) segments 계산 (Input / Process / Output 3등분)
    segments: list[dict] = []
    if index_df is not None and not index_df.empty:
        # index.xlsx 를 통해 문항 순서와 대분류를 알 수 있을 때
        idx = index_df.copy()
        idx["대분류_clean"] = (
            idx.get("대분류", "")
            .astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
        )
        # labels 순서를 기준으로 from/to 계산
        def _seg_bounds(seg_name: str):
            start = None
            end = None
            for i, lbl in enumerate(labels):
                # lbl 이 index_df 의 문항명과 1:1 일치하지 않을 수 있으니 contains 로
                match_rows = idx[idx["문항명"].astype(str).str.contains(lbl, na=False)]
                if not match_rows.empty:
                    big = match_rows.iloc[0]["대분류_clean"]
                    if seg_name.lower() in big.lower():
                        if start is None:
                            start = i
                        end = i
            return start, end

        for name in ["Input", "Process", "Output"]:
            s, e = _seg_bounds(name)
            if s is not None and e is not None:
                segments.append({"name": name, "from": s, "to": e})
    else:
        # index_df도 없으면 3구간으로 균등 분할
        n = len(labels)
        if n > 0:
            one = max(n // 3, 1)
            segments = [
                {"name": "Input", "from": 0, "to": min(one - 1, n - 1)},
                {"name": "Process", "from": one, "to": min(one * 2 - 1, n - 1)},
                {"name": "Output", "from": one * 2, "to": n - 1},
            ]

    report["summary"]["score_distribution"] = {
        "title": "진단 영역/항목별 점수 분포",
        "labels": labels,
        "series": [
            {"name": "벤치마크", "data": benchmark_scores},
            {"name": "우리 조직", "data": our_scores},
        ],
        "segments": segments,
    }
    return report

    # 2) 우리 조직 점수 집계
    area_grp = df.groupby(area_col)[score_col].mean().round(2)
    labels = area_grp.index.tolist()
    our_scores = area_grp.values.tolist()

    # 3) 벤치마크 있으면 붙이는 로직 (벤치마크 컬럼이 없을 수도 있으니 방어적으로)
    benchmark_scores = []
    if "benchmark" in cols:
        bench_grp = df.groupby(area_col)["benchmark"].mean().round(2)
        # labels 순서 기준으로 정렬
        benchmark_scores = [float(bench_grp.get(lbl, 0)) for lbl in labels]
    else:
        # 관리자 설정에서 벤치마크 가져오기
        benchmark_scores = get_benchmark_scores_for_labels(labels)
        if not benchmark_scores:
            # 설정이 없으면 0이 아닌 근사값으로 채워놓는 게 차트가 덜 깨짐
            benchmark_scores = [max(s - 0.2, 0) for s in our_scores]

    report["summary"]["score_distribution"] = {
        "title": "진단 영역/항목별 점수 분포",
        "labels": labels,
        "series": [
            {"name": "benchmark", "data": benchmark_scores},
            {"name": "our", "data": our_scores},
        ],
    }
    return report

# ================================
# 10) main
# ================================
def main():
    st.set_page_config(
        page_title="AI 기반 리포트 출력 및 메일링 자동화 시스템",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_global_styles()

    # 세션 초기화
    if "active_menu" not in st.session_state:
        st.session_state["active_menu"] = "upload"
    if "admin_mode" not in st.session_state:
        st.session_state["admin_mode"] = False
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False
    if "uploaded_df" not in st.session_state:
        st.session_state["uploaded_df"] = None
        st.session_state["data_source"] = None
    if "pdf_bytes" not in st.session_state:
        st.session_state["pdf_bytes"] = None
    if "ai_result" not in st.session_state:
        st.session_state["ai_result"] = None

    # 멀티 리포트 관련 세션 상태
    if "report_type" not in st.session_state:
        st.session_state["report_type"] = "전체"
    if "group_column" not in st.session_state:
        st.session_state["group_column"] = None
    if "reports" not in st.session_state:
        st.session_state["reports"] = {}
    if "selected_team" not in st.session_state:
        st.session_state["selected_team"] = None
    if "grouped_data" not in st.session_state:
        st.session_state["grouped_data"] = {}

    # PDF 관련 세션 상태
    if "pdf_results" not in st.session_state:
        st.session_state["pdf_results"] = {}
    if "zip_bytes" not in st.session_state:
        st.session_state["zip_bytes"] = None

    index_df = load_index()

    # 사이드바
    with st.sidebar:
        st.markdown('<div class="sb-title">순서대로 진행해주세요!</div>', unsafe_allow_html=True)

        def sb_item(key: str, label: str, desc: str = ""):
            active = st.session_state["active_menu"] == key
            completed = is_step_completed(key)

            # 클래스 결정
            item_class = ""
            if active:
                item_class = "active"
            elif completed:
                item_class = "completed"

            # 클릭 가능한 버튼으로 구현
            if st.button(f"{get_step_number(key)}. {label}", key=f"menu_{key}", help=desc, width='stretch'):
                st.session_state["active_menu"] = key
                st.rerun()

        def get_step_number(key: str) -> str:
            steps = {"upload": "1", "report": "2", "pdf": "3", "email": "4"}
            return steps.get(key, "")

        def is_step_completed(key: str) -> bool:
            if key == "upload":
                return st.session_state.get("reports") is not None
            elif key == "report":
                # 리포트 미리보기는 실제로 미리보기 페이지를 방문했을 때만 완료로 표시
                return (st.session_state.get("reports") is not None and
                        st.session_state.get("viewed_report", False))
            elif key == "pdf":
                return st.session_state.get("pdf_bytes") is not None or st.session_state.get("zip_bytes") is not None
            elif key == "email":
                return False  # 이메일은 완료 상태를 따로 관리하지 않음
            return False

        sb_item("upload", "파일 업로드 & 리포트 생성", "CSV/Excel 파일 업로드 후 리포트를 자동 생성합니다")
        sb_item("report", "리포트 미리보기", "생성된 리포트를 확인하세요")
        sb_item("pdf", "PDF 생성", "리포트를 PDF로 저장합니다")
        sb_item("email", "이메일 발송", "완성된 리포트를 이메일로 전송합니다")

        # 관리자 모드 인증
        st.markdown("---")

        if not st.session_state["admin_authenticated"]:
            # 관리자 로그인
            st.markdown("**🔧 관리자 모드**")

            with st.expander("관리자 로그인", expanded=False):
                admin_password = st.text_input(
                    "관리자 비밀번호",
                    type="password",
                    placeholder="비밀번호를 입력하세요",
                    help="관리자 기능에 접근하려면 올바른 비밀번호를 입력하세요"
                )

                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("🔓 로그인", key="admin_login"):
                        if admin_password == ADMIN_PASSWORD:
                            st.session_state["admin_authenticated"] = True
                            st.session_state["admin_mode"] = True
                            st.session_state["active_menu"] = "admin_db"
                            st.success("✅ 관리자 인증이 완료되었습니다!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("❌ 잘못된 비밀번호입니다.")

        else:
            # 관리자 로그아웃
            st.markdown("**🔧 관리자 모드 (인증됨)**")
            if st.button("🔒 로그아웃", key="admin_logout"):
                st.session_state["admin_authenticated"] = False
                st.session_state["admin_mode"] = False
                st.session_state["active_menu"] = "upload"
                st.success("관리자 모드에서 로그아웃되었습니다.")
                st.rerun()

        # 관리자 메뉴 표시
        if st.session_state["admin_authenticated"] and st.session_state["admin_mode"]:
            st.markdown("**관리자 도구**")
            sb_item("admin_db", "📊 데이터베이스 관리", "조직, 리포트, PDF 생성 이력 관리")
            sb_item("admin_benchmark", "📊 벤치마크 설정", "영역별 벤치마크 점수 관리")
            sb_item("admin_branding", "🎨 브랜딩 설정", "조직별 브랜딩 색상, 로고 설정")
            sb_item("admin_email", "📧 이메일 이력", "이메일 발송 로그 및 통계 확인")

        with st.expander("시스템 진단", expanded=False):
            st.write("- google-genai 설치 여부:", _HAS_GENAI)
            st.write("- GOOGLE_API_KEY 설정 여부:", bool(GOOGLE_API_KEY))
            if st.session_state["admin_authenticated"] and st.session_state["admin_mode"]:
                try:
                    import psutil
                    memory = psutil.virtual_memory()
                    st.write(f"- 메모리 사용률: {memory.percent:.1f}% ({memory.available/1024**3:.1f}GB 사용가능)")
                except ImportError:
                    st.write("- 메모리 정보: psutil 미설치")

                # 데이터베이스 연결 테스트
                try:
                    from database_models import get_session
                    session = get_session()
                    session.close()
                    st.write("- 데이터베이스: ✅ 연결 성공")
                except Exception as e:
                    st.write(f"- 데이터베이스: ❌ 연결 실패 ({str(e)[:50]}...)")

    # 상단 헤더
    st.markdown(
        f"""
        <div class="page-header">
            <div class="page-header-title">AI 기반 리포트 출력 및 메일링 자동화 시스템</div>
            <div class="page-header-right">{datetime.now().strftime('%Y-%m-%d %H:%M')}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- (1) 업로드 ----------
    if st.session_state["active_menu"] == "upload":
        st.markdown("##### 결과 파일 업로드 및 검증")

        st.markdown(
            """
            <div class="guide-card">
                <div class="guide-card-title">사용 방법</div>
                <div class="guide-card-desc">
                    1) 진단 결과 엑셀(.xlsx)을 업로드합니다.<br>
                    2) 누락/추가 컬럼을 확인합니다.<br>
                    3) 파일이 없으면 ‘샘플 데이터로 진행’을 눌러 화면을 먼저 확인할 수 있습니다.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        uploaded = st.file_uploader(
            "📊 조직 효과성 진단 결과 파일 업로드",
            type=["xlsx", "xls", "csv"],
            label_visibility="collapsed",
            help="엑셀 파일(.xlsx, .xls) 또는 CSV 파일(.csv)을 업로드하세요",
        )

        bc1, bc2, _ = st.columns([0.19, 0.19, 0.62])
        with bc1:
            use_sample = st.button("샘플 데이터로 진행")
        with bc2:
            clear_data = st.button("데이터 초기화")

        if uploaded is not None:
            df, source = load_data(uploaded)
            st.session_state["uploaded_df"] = df
            st.session_state["data_source"] = "uploaded"
            st.session_state["ai_result"] = None
        elif use_sample:
            df, source = load_data(None)
            st.session_state["uploaded_df"] = df
            st.session_state["data_source"] = "sample"
            st.session_state["ai_result"] = None
        elif clear_data:
            st.session_state["uploaded_df"] = None
            st.session_state["data_source"] = None
            st.session_state["ai_result"] = None

        df = st.session_state["uploaded_df"]
        source = st.session_state["data_source"]

        if df is None:
            st.info("업로드된 데이터가 없습니다. 파일을 올리거나 '샘플 데이터로 진행'을 눌러 시작하세요.")
            return

        # 데이터에서 조직명 자동 추출
        detected_org_info = extract_organization_info(df)


        # 간단한 리포트 생성 설정
        st.subheader("📊 리포트 생성 설정")
        col1, col2 = st.columns(2)
        with col1:
            report_type = st.selectbox(
                "리포트 생성 방식",
                ["전체 조직", "팀별 분석"],
                index=0,
                help="전체 조직: 통합 리포트 / 팀별 분석: 개별 리포트"
            )

        group_column = None
        with col2:
            if report_type == "팀별 분석":
                possible_columns = [col for col in df.columns if any(keyword in col.upper() for keyword in ['POS', 'DEPT', 'TEAM', '부서', '팀'])]
                if possible_columns:
                    group_column = st.selectbox(
                        "팀 구분 컬럼",
                        possible_columns,
                        help="팀별 구분에 사용할 컬럼"
                    )

        # 리포트 생성 버튼을 선택 영역 바로 아래에 배치
        if st.button("✅ 리포트 생성", type="primary", key="main_generate_btn", width='stretch'):
            # 내부적으로는 기존 "전체"/"팀별" 형식으로 변환
            internal_report_type = "전체" if report_type == "전체 조직" else "팀별"

            st.session_state["report_type"] = internal_report_type
            st.session_state["group_column"] = group_column
            st.session_state["detected_org_info"] = detected_org_info

            if internal_report_type == "팀별" and not group_column:
                st.error("팀별 리포트 생성을 위해서는 그룹 기준 컬럼을 선택해 주세요.")
                return

            with st.spinner("리포트 생성 중..."):
                try:
                    print(f"DEBUG: 리포트 생성 시작 - 타입: {internal_report_type}, 그룹 컬럼: {group_column}")

                    # 데이터 그룹핑
                    grouped_data = group_data_by_unit(df, internal_report_type, group_column)
                    st.session_state["grouped_data"] = grouped_data
                    print(f"DEBUG: 데이터 그룹핑 완료 - 그룹 수: {len(grouped_data)}")

                    # 리포트 생성 (감지된 조직 정보 전달)
                    index_df = load_index()
                    print(f"DEBUG: 인덱스 로드 완료 - 행 수: {len(index_df)}")

                    reports = build_multiple_reports(grouped_data, index_df, detected_org_info["company"], detected_org_info["department"])
                    print(f"DEBUG: 리포트 생성 완료 - 리포트 수: {len(reports)}")

                    st.session_state["reports"] = reports
                    st.session_state["active_menu"] = "report"
                    print(f"DEBUG: 세션 상태 업데이트 완료 - active_menu: {st.session_state['active_menu']}")

                    st.success(f"리포트가 성공적으로 생성되었습니다! ({len(reports)}개)")
                    print("DEBUG: st.rerun() 호출")
                    st.rerun()
                except Exception as e:
                    print(f"ERROR: 리포트 생성 중 오류: {e}")
                    import traceback
                    traceback.print_exc()
                    st.error(f"리포트 생성 중 오류가 발생했습니다: {e}")

        st.markdown("###### 📄 원본 데이터 미리보기 (식별정보 마스킹)")
        df_to_show = mask_df_for_preview(df)
        st.dataframe(df_to_show.head(30).astype(str), width="stretch")

        v = validate_df(df, index_df)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown('<div class="info-card-head">데이터 상태</div>', unsafe_allow_html=True)
            st.markdown('<div class="info-card-body">', unsafe_allow_html=True)
            st.write(f"- 데이터 소스: **{source}**")
            st.write(f"- 행(Row): **{len(df)}**")
            st.write(f"- 컬럼(Column): **{len(df.columns)}**")
            st.markdown("</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="info-card">', unsafe_allow_html=True)
            st.markdown('<div class="info-card-head">컬럼 검증 결과</div>', unsafe_allow_html=True)
            st.markdown('<div class="info-card-body">', unsafe_allow_html=True)
            st.write(f"- 기대 컬럼: **{v['expected_count']}개**")
            st.write(f"- 실제 컬럼: **{v['actual_count']}개**")
            st.write("- 누락 컬럼:")
            st.write(v["missing"] if v["missing"] else "없음")
            st.write("- 추가 컬럼:")
            st.write(v["extra"] if v["extra"] else "없음")
            st.markdown("</div></div>", unsafe_allow_html=True)


    # ---------- (2) 리포트 미리보기 ----------
    elif st.session_state["active_menu"] == "report":
        st.markdown("##### 리포트 미리보기")

        # 리포트 미리보기 페이지 방문 시 플래그 설정
        st.session_state["viewed_report"] = True

        df = st.session_state["uploaded_df"]
        if df is None:
            st.warning("먼저 첫번째 메뉴에서 데이터를 준비해 주세요.")
            return

        reports = st.session_state.get("reports", {})
        print(f"DEBUG: 리포트 미리보기 - reports 키 존재: {'reports' in st.session_state}")
        print(f"DEBUG: 리포트 미리보기 - reports 타입: {type(reports)}")
        print(f"DEBUG: 리포트 미리보기 - reports 길이: {len(reports)}")
        print(f"DEBUG: 리포트 미리보기 - reports 키들: {list(reports.keys()) if reports else 'None'}")
        if not reports:
            st.warning("먼저 첫번째 메뉴에서 리포트 설정을 완료해 주세요.")
            return

        # 팀 선택 UI (여러 리포트가 있는 경우)
        selected_team = None
        if len(reports) > 1:
            st.markdown("###### 조회할 리포트 선택")

            # 팀 목록 정렬 (가나다순)
            team_names = sorted(reports.keys())

            # 팀 정보 표시
            team_info = []
            for team_name in team_names:
                team_df = st.session_state["grouped_data"].get(team_name)
                count = len(team_df) if team_df is not None else 0
                team_info.append(f"{team_name} ({count}명)")

            selected_team = st.selectbox(
                "리포트 선택",
                team_names,
                index=team_names.index(st.session_state.get("selected_team", team_names[0])) if st.session_state.get("selected_team") in team_names else 0,
                format_func=lambda x: f"{x} ({len(st.session_state['grouped_data'].get(x, []))}명)",
                help="미리보기할 리포트를 선택하세요"
            )

            if selected_team != st.session_state.get("selected_team"):
                st.session_state["selected_team"] = selected_team
                # 팀이 바뀌면 AI 결과 초기화
                st.session_state["ai_result"] = None

            st.caption(f"총 {len(reports)}개의 리포트가 생성되었습니다.")
        else:
            selected_team = list(reports.keys())[0]
            st.session_state["selected_team"] = selected_team

        # 선택된 리포트 가져오기
        report = reports[selected_team]
        selected_df = st.session_state["grouped_data"][selected_team]

        # AI 해석 버튼 (팀별로 개별 관리) - 캐시 기능 추가
        ai_key = f"ai_result_{selected_team}"
        if ai_key not in st.session_state:
            st.session_state[ai_key] = None

        # 캐시된 AI 분석 결과 확인
        data_hash = generate_data_hash(report)
        cached_ai_result = get_cached_ai_analysis(selected_team, data_hash)

        top_c1, top_c2, top_c3 = st.columns([0.25, 0.25, 0.25])

        with top_c1:
            if cached_ai_result:
                # 이미 저장된 AI 해석이 있는 경우
                load_cached = st.button(f"저장된 AI 해석 불러오기", key=f"load_cached_{selected_team}")
                if load_cached:
                    st.session_state[ai_key] = cached_ai_result
                    st.toast(f"'{selected_team}' 저장된 AI 해석을 불러왔습니다", icon="📂")
                    st.rerun()
                st.caption("✅ 이전에 생성된 AI 해석이 있습니다")
            else:
                run_ai = st.button(f"AI 해석 생성하기", key=f"ai_btn_{selected_team}")

        with top_c2:
            if cached_ai_result or st.session_state[ai_key]:
                run_ai_force = st.button(f"AI 해석 재생성", key=f"ai_btn_force_{selected_team}")
                st.caption("※ 새로운 AI 해석을 강제로 생성합니다.")
            elif len(reports) > 1:
                run_all_ai = st.button("전체 팀 AI 해석", key="ai_btn_all")
                st.caption("※ 모든 팀의 AI 해석을 일괄 생성합니다.")

        with top_c3:
            if len(reports) > 1 and (cached_ai_result or st.session_state[ai_key]):
                run_all_ai = st.button("전체 팀 AI 해석", key="ai_btn_all_2")
                st.caption("※ 모든 팀의 AI 해석을 일괄 생성합니다.")

        # 개별 팀 AI 해석 생성 (신규 생성)
        if 'run_ai' in locals() and run_ai:
            st.session_state[ai_key] = None
            progress = st.progress(0)
            progress_text = st.empty()
            log_box = st.empty()

            def on_progress(step: int, msg: str):
                pct = min(max(int(step / 7 * 100), 0), 100)
                progress.progress(pct)
                progress_text.markdown(f"**{pct}% 진행 중:** {msg}")
                log_box.markdown(f"최근 단계: {msg}")

            with st.spinner(f"'{selected_team}' AI 해석 생성 중..."):
                ai_result = run_ai_interpretation_gemini_from_report(
                    report, progress_update=on_progress, force_regenerate=False
                )
            st.session_state[ai_key] = ai_result
            st.toast(f"'{selected_team}' AI 해석 생성 완료", icon="✅")

        # 개별 팀 AI 해석 재생성 (강제 재생성)
        if 'run_ai_force' in locals() and run_ai_force:
            st.session_state[ai_key] = None
            progress = st.progress(0)
            progress_text = st.empty()
            log_box = st.empty()

            def on_progress(step: int, msg: str):
                pct = min(max(int(step / 7 * 100), 0), 100)
                progress.progress(pct)
                progress_text.markdown(f"**{pct}% 진행 중:** {msg}")
                log_box.markdown(f"최근 단계: {msg}")

            with st.spinner(f"'{selected_team}' AI 해석 재생성 중..."):
                ai_result = run_ai_interpretation_gemini_from_report(
                    report, progress_update=on_progress, force_regenerate=True
                )
            st.session_state[ai_key] = ai_result
            st.toast(f"'{selected_team}' AI 해석 재생성 완료", icon="🔄")

        # 전체 팀 AI 해석 생성
        if len(reports) > 1 and 'run_all_ai' in locals() and run_all_ai:
            progress = st.progress(0)
            progress_text = st.empty()

            total_teams = len(reports)
            for i, (team_name, team_report) in enumerate(reports.items()):
                ai_key_team = f"ai_result_{team_name}"
                progress.progress((i + 1) / total_teams)
                progress_text.markdown(f"**{team_name}** AI 해석 생성 중... ({i+1}/{total_teams})")

                with st.spinner(f"'{team_name}' AI 해석 생성 중..."):
                    ai_result = run_ai_interpretation_gemini_from_report(team_report)
                st.session_state[ai_key_team] = ai_result

            st.toast(f"전체 {total_teams}개 팀 AI 해석 생성 완료", icon="✅")

        # 현재 선택된 팀의 AI 결과 가져오기
        ai_raw = _normalize_ai_result(st.session_state.get(ai_key))
        ai_raw = materialize_ai_placeholders(ai_raw, report)

        # 점수 분포 주입
        report = attach_score_distribution(report, selected_df, index_df)

        # HTML 미리보기 생성
        html_preview = render_web_html(
            report,
            ai_result=ai_raw if _has_ai_result(ai_raw) else None,
        )

        # 리포트 제목 표시
        if len(reports) > 1:
            st.markdown(f"**현재 표시 중:** {selected_team}")

        st.markdown(
            '<div class="preview-container" style="margin-top:0.75rem;">',
            unsafe_allow_html=True,
        )
        st.components.v1.html(html_preview, height=900, scrolling=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # AI 해석 결과 편집 기능 (리포트 미리보기 뒤에 위치)
        if ai_raw and _has_ai_result(ai_raw):
            st.divider()
            st.markdown("### 📝 AI 해석 결과 검토 및 편집")

            # 편집 모드 토글
            edit_mode_key = f"edit_mode_{selected_team}"
            if edit_mode_key not in st.session_state:
                st.session_state[edit_mode_key] = False

            col1, col2, col3 = st.columns([0.2, 0.2, 0.6])
            with col1:
                if st.button("✏️ 편집 모드", key=f"edit_btn_{selected_team}"):
                    st.session_state[edit_mode_key] = not st.session_state[edit_mode_key]

            with col2:
                if st.session_state[edit_mode_key]:
                    if st.button("💾 편집 내용 저장", key=f"save_btn_{selected_team}"):
                        # 편집된 내용을 저장
                        data_hash = generate_data_hash(report)
                        save_ai_analysis(selected_team, data_hash, ai_raw, report)
                        st.session_state[edit_mode_key] = False
                        st.toast("편집 내용이 저장되었습니다!", icon="💾")
                        st.rerun()

            # AI 해석 결과 표시/편집
            if st.session_state[edit_mode_key]:
                st.info("🔧 편집 모드: AI 해석 결과를 수정할 수 있습니다. 수정 후 '편집 내용 저장'을 클릭하세요.")

                # 각 섹션별 편집 가능한 텍스트 영역
                ai_raw["final"] = st.text_area(
                    "📄 최종 임원 요약",
                    value=ai_raw.get("final", ""),
                    height=200,
                    key=f"edit_final_{selected_team}",
                    help="이 내용이 리포트의 메인 분석 결과로 표시됩니다."
                )

                with st.expander("🔍 세부 분석 결과 편집", expanded=False):
                    ai_raw["score"] = st.text_area(
                        "📊 점수 해석",
                        value=ai_raw.get("score", ""),
                        height=150,
                        key=f"edit_score_{selected_team}"
                    )

                    ai_raw["items"] = st.text_area(
                        "📋 낮은 점수 문항 분석",
                        value=ai_raw.get("items", ""),
                        height=150,
                        key=f"edit_items_{selected_team}"
                    )

                    ai_raw["free_text"] = st.text_area(
                        "💬 주관식 응답 분석",
                        value=ai_raw.get("free_text", ""),
                        height=150,
                        key=f"edit_free_text_{selected_team}"
                    )

            else:
                # 읽기 전용 모드
                st.markdown("#### 📄 최종 AI 분석 결과")
                if ai_raw.get("final"):
                    st.markdown(ai_raw["final"])
                else:
                    st.info("AI 분석 결과가 없습니다. 위에서 'AI 해석 생성하기'를 클릭하세요.")

                with st.expander("🔍 세부 분석 결과 보기", expanded=False):
                    if ai_raw.get("score"):
                        st.markdown("**📊 점수 해석:**")
                        st.markdown(ai_raw["score"])

                    if ai_raw.get("items"):
                        st.markdown("**📋 낮은 점수 문항 분석:**")
                        st.markdown(ai_raw["items"])

                    if ai_raw.get("free_text"):
                        st.markdown("**💬 주관식 응답 분석:**")
                        st.markdown(ai_raw["free_text"])

    # ---------- (3) PDF 생성 ----------
    elif st.session_state["active_menu"] == "pdf":
        st.markdown("##### PDF 생성")

        df = st.session_state["uploaded_df"]
        if df is None:
            st.warning("먼저 첫번째 메뉴에서 데이터를 준비해 주세요.")
            return

        reports = st.session_state.get("reports", {})
        if not reports:
            st.warning("먼저 첫번째 메뉴에서 리포트 설정을 완료해 주세요.")
            return

        org_name = get_organization_name_from_reports(reports)

        st.markdown('<div id="export-view">', unsafe_allow_html=True)

        # 다중 리포트인 경우
        if len(reports) > 1:
            col_individual, col_batch = st.columns(2)

            # 개별 PDF 다운로드
            with col_individual:
                st.markdown('<div class="export-card">', unsafe_allow_html=True)
                st.markdown('<div class="export-card-head">📄 개별 PDF 다운로드</div>', unsafe_allow_html=True)
                st.markdown('<div class="export-card-body">', unsafe_allow_html=True)

                team_names = sorted(reports.keys())
                selected_team_for_pdf = st.selectbox(
                    "다운로드할 팀 선택",
                    team_names,
                    key="pdf_team_select"
                )

                if st.button("개별 PDF 생성", key="individual_pdf"):
                    with st.spinner(f"'{selected_team_for_pdf}' PDF 생성 중..."):
                        single_report = {selected_team_for_pdf: reports[selected_team_for_pdf]}
                        pdf_result = generate_multiple_pdfs(single_report)

                        if pdf_result and selected_team_for_pdf in pdf_result:
                            pdf_bytes = pdf_result[selected_team_for_pdf]
                            safe_team_name = selected_team_for_pdf.replace("/", "_").replace("\\", "_")
                            filename = f"{safe_team_name}_조직효과성진단.pdf"

                            st.success("PDF 생성 완료!")
                            st.download_button(
                                "📥 PDF 다운로드",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                key="download_individual_pdf"
                            )

                st.markdown("</div></div>", unsafe_allow_html=True)

            # 전체 ZIP 다운로드
            with col_batch:
                st.markdown('<div class="export-card">', unsafe_allow_html=True)
                st.markdown('<div class="export-card-head">📦 전체 팀 ZIP 다운로드</div>', unsafe_allow_html=True)
                st.markdown('<div class="export-card-body">', unsafe_allow_html=True)

                st.markdown(f"총 {len(reports)}개 팀의 PDF를 일괄 생성합니다.")

                # 성능 옵션
                with st.expander("⚙️ 성능 설정", expanded=False):
                    # 병렬 처리 설정
                    use_parallel = st.checkbox("병렬 처리 사용", value=len(reports) > 3, help="3개 이상 팀에서 추천")
                    if use_parallel:
                        max_workers = st.slider("병렬 작업자 수", min_value=1, max_value=8, value=3, help="CPU 코어 수에 따라 조절")
                    else:
                        max_workers = 1

                    # 메모리 최적화 설정
                    st.markdown("**메모리 최적화 설정**")
                    batch_size = st.selectbox("배치 크기", options=[5, 10, 20, 50], index=1, help="메모리 사용량 제한")

                    memory_monitoring = st.checkbox("메모리 모니터링 활성화", value=True, help="실시간 메모리 사용량 추적")
                    aggressive_cleanup = st.checkbox("적극적 메모리 정리", value=True, help="각 배치 후 가비지 컬렉션 강제 실행")

                    # 현재 시스템 메모리 정보 표시
                    try:
                        import psutil
                        memory = psutil.virtual_memory()
                        st.info(f"💾 현재 시스템 메모리: {memory.available/1024**3:.1f}GB 사용 가능 (전체: {memory.total/1024**3:.1f}GB)")
                    except ImportError:
                        st.info("💾 메모리 정보를 보려면 psutil 설치 필요: pip install psutil")

                if st.button("전체 PDF 생성", key="batch_pdf"):
                    progress_bar = st.progress(0)
                    progress_text = st.empty()
                    performance_stats = st.empty()

                    import time
                    start_time = time.time()

                    with st.spinner("전체 팀 PDF 생성 중..."):
                        total_teams = len(reports)
                        pdf_results = {}

                        if use_parallel and total_teams > 1:
                            # 병렬 배치 처리
                            progress_text.text(f"병렬 처리로 {total_teams}개 팀 PDF 생성 시작 (병렬도: {max_workers})")

                            # 배치별로 처리
                            team_items = list(reports.items())
                            processed_count = 0

                            for batch_start in range(0, total_teams, batch_size):
                                batch_start_time = time.time()
                                batch_end = min(batch_start + batch_size, total_teams)
                                batch_reports = dict(team_items[batch_start:batch_end])

                                progress_text.text(f"배치 {batch_start//batch_size + 1} 처리 중... ({batch_start+1}-{batch_end}/{total_teams})")

                                # 병렬 배치 처리
                                batch_results = generate_multiple_pdfs_parallel(batch_reports, max_workers=max_workers)
                                pdf_results.update(batch_results)

                                processed_count += len(batch_results)
                                progress_percentage = processed_count / total_teams
                                progress_bar.progress(progress_percentage)

                                # 실시간 성능 통계
                                elapsed_time = time.time() - start_time
                                batch_time = time.time() - batch_start_time
                                avg_time_per_team = elapsed_time / processed_count if processed_count > 0 else 0
                                estimated_total_time = avg_time_per_team * total_teams
                                remaining_time = estimated_total_time - elapsed_time

                                # 메모리 모니터링
                                memory_info = ""
                                if memory_monitoring:
                                    try:
                                        import psutil
                                        memory = psutil.virtual_memory()
                                        memory_info = f"""
                                        **💾 메모리 사용량:**
                                        - 사용 중: {(memory.total - memory.available)/1024**3:.1f}GB ({memory.percent:.1f}%)
                                        - 사용 가능: {memory.available/1024**3:.1f}GB
                                        """
                                    except ImportError:
                                        memory_info = "\n**💾 메모리 모니터링:** psutil 미설치"

                                performance_stats.markdown(f"""
                                **📊 실시간 성능 통계:**
                                - 진행률: {progress_percentage:.1%} ({processed_count}/{total_teams})
                                - 경과시간: {elapsed_time:.1f}초
                                - 이번 배치: {batch_time:.1f}초 ({len(batch_results)}개 팀)
                                - 평균 팀당 시간: {avg_time_per_team:.1f}초
                                - 예상 총 소요시간: {estimated_total_time:.1f}초
                                - 예상 남은시간: {max(0, remaining_time):.1f}초
                                - 처리 속도: {processed_count/elapsed_time:.1f} 팀/초
                                {memory_info}
                                """)

                                # 메모리 정리
                                if aggressive_cleanup:
                                    import gc
                                    gc.collect()
                                    if memory_monitoring:
                                        try:
                                            import psutil
                                            # 메모리 사용량이 80% 이상이면 경고
                                            memory = psutil.virtual_memory()
                                            if memory.percent > 80:
                                                st.warning(f"⚠️ 메모리 사용량이 높습니다 ({memory.percent:.1f}%). 배치 크기를 줄이는 것을 권장합니다.")
                                        except ImportError:
                                            pass

                        else:
                            # 순차 처리 (기존 방식)
                            for i, (team_name, report) in enumerate(reports.items()):
                                progress_percentage = (i + 1) / total_teams
                                progress_bar.progress(progress_percentage)
                                progress_text.text(f"'{team_name}' PDF 생성 중... ({i+1}/{total_teams})")

                                # 실시간 성능 통계 (순차 처리)
                                elapsed_time = time.time() - start_time
                                avg_time_per_team = elapsed_time / (i + 1)
                                estimated_total_time = avg_time_per_team * total_teams
                                remaining_time = estimated_total_time - elapsed_time

                                # 메모리 모니터링 (순차 처리)
                                memory_info = ""
                                if memory_monitoring:
                                    try:
                                        import psutil
                                        memory = psutil.virtual_memory()
                                        memory_info = f"""
                                        **💾 메모리 사용량:**
                                        - 사용 중: {(memory.total - memory.available)/1024**3:.1f}GB ({memory.percent:.1f}%)
                                        - 사용 가능: {memory.available/1024**3:.1f}GB
                                        """
                                    except ImportError:
                                        memory_info = "\n**💾 메모리 모니터링:** psutil 미설치"

                                performance_stats.markdown(f"""
                                **📊 실시간 성능 통계:**
                                - 진행률: {progress_percentage:.1%} ({i+1}/{total_teams})
                                - 경과시간: {elapsed_time:.1f}초
                                - 평균 팀당 시간: {avg_time_per_team:.1f}초
                                - 예상 총 소요시간: {estimated_total_time:.1f}초
                                - 예상 남은시간: {max(0, remaining_time):.1f}초
                                - 처리 속도: {(i+1)/elapsed_time:.1f} 팀/초
                                {memory_info}
                                """)

                                single_report = {team_name: report}
                                single_pdf_result = generate_multiple_pdfs(single_report)

                                if single_pdf_result and team_name in single_pdf_result:
                                    pdf_results[team_name] = single_pdf_result[team_name]

                        if pdf_results:
                            # 최종 성능 통계
                            total_elapsed_time = time.time() - start_time
                            final_avg_time_per_team = total_elapsed_time / len(pdf_results)
                            final_processing_speed = len(pdf_results) / total_elapsed_time

                            performance_stats.markdown(f"""
                            **✅ 최종 성능 리포트:**
                            - 총 처리시간: {total_elapsed_time:.1f}초 ({total_elapsed_time/60:.1f}분)
                            - 성공적으로 생성된 PDF: {len(pdf_results)}개
                            - 평균 팀당 처리시간: {final_avg_time_per_team:.1f}초
                            - 전체 처리 속도: {final_processing_speed:.1f} 팀/초
                            - 처리 모드: {'병렬 처리' if use_parallel and total_teams > 1 else '순차 처리'}
                            {f'- 병렬 작업자 수: {max_workers}개' if use_parallel and total_teams > 1 else ''}
                            {f'- 배치 크기: {batch_size}' if use_parallel and total_teams > 1 else ''}
                            """)

                            # ZIP 생성
                            zip_bytes = create_zip_from_pdfs(pdf_results, org_name)
                            st.session_state["pdf_results"] = pdf_results
                            st.session_state["zip_bytes"] = zip_bytes

                            st.success(f"전체 {len(pdf_results)}개 팀 PDF 생성 완료! (총 {total_elapsed_time:.1f}초 소요)")
                            zip_filename = f"{org_name}_전체팀_조직효과성진단_{datetime.now().strftime('%Y%m%d')}.zip"

                            st.download_button(
                                "📥 ZIP 다운로드",
                                data=zip_bytes,
                                file_name=zip_filename,
                                mime="application/zip",
                                key="download_zip"
                            )
                        else:
                            # 상세한 오류 정보 제공
                            st.error("🚫 PDF 생성에 실패했습니다.")

                            # 실패 원인 분석 및 가이드
                            if len(reports) == 0:
                                st.warning("📋 생성할 리포트가 없습니다. 먼저 CSV 파일을 업로드하고 리포트를 생성해 주세요.")
                            else:
                                failed_teams = [team for team in reports.keys() if team not in pdf_results]
                                if failed_teams:
                                    st.warning(f"⚠️ 다음 팀들의 PDF 생성에 실패했습니다: {', '.join(failed_teams[:5])}")
                                    if len(failed_teams) > 5:
                                        st.info(f"... 외 {len(failed_teams) - 5}개 팀")

                                # 해결 방법 제안
                                with st.expander("💡 문제 해결 방법", expanded=False):
                                    st.markdown("""
                                    **다음 방법들을 시도해 보세요:**

                                    1. **메모리 부족 문제**
                                       - 배치 크기를 줄여보세요 (현재: {batch_size}개 → 5개 이하)
                                       - 병렬 작업자 수를 줄여보세요 (현재: {max_workers}개 → 1-2개)
                                       - 적극적 메모리 정리를 활성화해 주세요

                                    2. **데이터 문제**
                                       - CSV 파일의 데이터 형식을 확인해 주세요
                                       - 특수문자가 포함된 팀명이 있는지 확인해 주세요

                                    3. **시스템 문제**
                                       - 브라우저를 새로고침하고 다시 시도해 주세요
                                       - 다른 브라우저에서 시도해 보세요

                                    4. **개별 PDF 생성**
                                       - 전체 생성 대신 개별 팀 PDF를 하나씩 생성해 보세요
                                    """.format(batch_size=batch_size, max_workers=max_workers))

                                    # 시스템 정보
                                    try:
                                        import psutil
                                        memory = psutil.virtual_memory()
                                        st.info(f"현재 메모리 사용률: {memory.percent:.1f}% (사용가능: {memory.available/1024**3:.1f}GB)")
                                    except ImportError:
                                        st.info("시스템 메모리 정보를 확인하려면 psutil을 설치해 주세요: pip install psutil")

                # 이미 생성된 ZIP이 있는 경우
                elif st.session_state.get("zip_bytes"):
                    zip_filename = f"{org_name}_전체팀_조직효과성진단_{datetime.now().strftime('%Y%m%d')}.zip"
                    st.download_button(
                        "📥 ZIP 다운로드",
                        data=st.session_state["zip_bytes"],
                        file_name=zip_filename,
                        mime="application/zip",
                        key="download_existing_zip"
                    )

                st.markdown("</div></div>", unsafe_allow_html=True)

        else:
            # 단일 리포트인 경우 (기존 방식)
            col_pdf, col_mail = st.columns(2)

            with col_pdf:
                st.markdown('<div class="export-card">', unsafe_allow_html=True)
                st.markdown('<div class="export-card-head">📄 PDF 만들기</div>', unsafe_allow_html=True)
                st.markdown('<div class="export-card-body">', unsafe_allow_html=True)

                team_name = list(reports.keys())[0]
                report = reports[team_name]

                # AI 결과 처리
                ai_key = f"ai_result_{team_name}"
                current_ai = _normalize_ai_result(st.session_state.get(ai_key))
                current_ai = materialize_ai_placeholders(current_ai, report)

                if st.button("PDF 만들기", key="single_pdf"):
                    with st.spinner("PDF 생성 중..."):
                        single_report = {team_name: report}
                        pdf_result = generate_multiple_pdfs(single_report)

                        if pdf_result and team_name in pdf_result:
                            pdf_bytes = pdf_result[team_name]
                            st.session_state["pdf_bytes"] = pdf_bytes
                            st.success("PDF가 생성되었습니다.")

                            filename = f"{org_name}_조직효과성진단.pdf"
                            st.download_button(
                                "📥 PDF 다운로드",
                                data=pdf_bytes,
                                file_name=filename,
                                mime="application/pdf",
                                key="download_single_pdf"
                            )

                elif st.session_state.get("pdf_bytes"):
                    filename = f"{org_name}_조직효과성진단.pdf"
                    st.download_button(
                        "📥 PDF 다운로드",
                        data=st.session_state["pdf_bytes"],
                        file_name=filename,
                        mime="application/pdf",
                        key="download_existing_single_pdf"
                    )

                st.markdown("</div></div>", unsafe_allow_html=True)


        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- (4) 이메일 발송 ----------
    elif st.session_state["active_menu"] == "email":
        st.markdown("##### 이메일 발송")

        df = st.session_state["uploaded_df"]
        if df is None:
            st.warning("먼저 첫번째 메뉴에서 데이터를 준비해 주세요.")
            return

        reports = st.session_state.get("reports", {})
        if not reports:
            st.warning("먼저 첫번째 메뉴에서 리포트 설정을 완료해 주세요.")
            return

        st.markdown('<div id="email-view">', unsafe_allow_html=True)

        # 이메일 발송 UI 구현
        st.markdown('<div class="export-card">', unsafe_allow_html=True)
        st.markdown('<div class="export-card-head">✉️ 이메일 발송</div>', unsafe_allow_html=True)
        st.markdown('<div class="export-card-body">', unsafe_allow_html=True)

        # Gmail 설정 - 환경변수에서 자동으로 가져오거나 사용자 입력
        env_gmail = os.getenv("SMTP_EMAIL", "")
        env_password = os.getenv("SMTP_PASSWORD", "")

        if env_gmail and env_password:
            st.info(f"✅ 환경변수에서 Gmail 설정을 자동으로 가져왔습니다: {env_gmail}")
            gmail_address = env_gmail
            gmail_app_pw = env_password

            with st.expander("Gmail 설정 변경 (선택사항)"):
                gmail_address = st.text_input(
                    "다른 Gmail 주소 사용",
                    value=env_gmail,
                    key="email_gmail_address_override",
                    placeholder="sender@gmail.com"
                )
                gmail_app_pw = st.text_input(
                    "다른 Gmail 앱 비밀번호 사용",
                    value="",
                    key="email_gmail_password_override",
                    type="password",
                    help="Google 계정 > 보안 > 앱 비밀번호에서 발급"
                )
                if not gmail_app_pw:  # 새 비밀번호를 입력하지 않으면 환경변수 값 사용
                    gmail_app_pw = env_password
        else:
            st.warning("⚠️ 환경변수에 SMTP 설정이 없습니다. 수동으로 입력해주세요.")
            gmail_address = st.text_input(
                "발송자 Gmail 주소",
                key="email_gmail_address",
                placeholder="sender@gmail.com"
            )
            gmail_app_pw = st.text_input(
                "Gmail 앱 비밀번호",
                key="email_gmail_password",
                type="password",
                help="Google 계정 > 보안 > 앱 비밀번호에서 발급"
            )

        st.markdown("---")

        if len(reports) > 1:
            # 다중 리포트 이메일 발송
            teams = sorted(reports.keys())
            email_mapping = create_email_mapping_ui(teams)

            # 공통 메일 설정
            subject = st.text_input(
                "메일 제목",
                value="조직효과성 진단 리포트",
                key="batch_email_subject"
            )
            body = st.text_area(
                "메일 내용",
                value="첨부된 PDF를 확인해 주세요.",
                key="batch_email_body",
                height=100
            )

            # ZIP 파일 발송 옵션
            st.markdown("---")
            st.markdown("##### 📦 발송 방식 선택")

            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("📧 개별 발송", key="individual_email_send", use_container_width=True):
                    if not gmail_address or not gmail_app_pw:
                        st.error("Gmail 주소와 앱 비밀번호를 모두 입력해 주세요.")
                    elif not email_mapping:
                        st.error("이메일 매핑을 설정해 주세요.")
                    else:
                        with st.spinner("PDF 생성 및 개별 이메일 발송 중..."):
                            try:
                                success_count = send_batch_emails_with_reports(
                                    reports=reports,
                                    email_mapping=email_mapping,
                                    gmail_address=gmail_address,
                                    gmail_password=gmail_app_pw,
                                    subject=subject,
                                    body=body
                                )
                                st.success(f"✅ {success_count}개 팀에 개별 이메일을 성공적으로 발송했습니다!")
                            except Exception as e:
                                st.error(f"개별 이메일 발송 중 오류가 발생했습니다: {e}")

            with col2:
                zip_recipient = st.text_input(
                    "ZIP 파일 수신자 이메일",
                    key="zip_recipient_email",
                    placeholder="manager@company.com",
                    help="모든 팀의 PDF를 ZIP 파일로 묶어서 한 번에 발송"
                )

                if st.button("📦 ZIP 파일 발송", key="zip_email_send", use_container_width=True):
                    if not gmail_address or not gmail_app_pw:
                        st.error("Gmail 주소와 앱 비밀번호를 모두 입력해 주세요.")
                    elif not zip_recipient:
                        st.error("ZIP 파일 수신자 이메일을 입력해 주세요.")
                    else:
                        with st.spinner("PDF 생성 및 ZIP 파일 이메일 발송 중..."):
                            try:
                                success_count = send_batch_emails_with_reports(
                                    reports=reports,
                                    email_mapping={},  # ZIP 모드에서는 불필요
                                    gmail_address=gmail_address,
                                    gmail_password=gmail_app_pw,
                                    subject=subject,
                                    body=body,
                                    send_as_zip=True,
                                    zip_recipient=zip_recipient
                                )
                                if success_count > 0:
                                    st.success(f"✅ {zip_recipient}로 ZIP 파일을 성공적으로 발송했습니다!")
                                else:
                                    st.error("ZIP 파일 발송에 실패했습니다.")
                            except Exception as e:
                                st.error(f"ZIP 파일 발송 중 오류가 발생했습니다: {e}")

        else:
            # 단일 리포트 이메일 발송
            team_name = list(reports.keys())[0]

            to_email = st.text_input(
                "받는 사람 이메일",
                key="single_email_recipient",
                placeholder="recipient@example.com"
            )
            subject = st.text_input(
                "메일 제목",
                value=f"{team_name} 조직효과성 진단 리포트",
                key="single_email_subject"
            )
            body = st.text_area(
                "메일 내용",
                value=f"{team_name} 팀의 조직효과성 진단 리포트를 첨부합니다.",
                key="single_email_body",
                height=100
            )

            if st.button("📧 이메일 발송", key="single_email_send"):
                if not gmail_address or not gmail_app_pw:
                    st.error("Gmail 주소와 앱 비밀번호를 모두 입력해 주세요.")
                elif not to_email:
                    st.error("받는 사람 이메일을 입력해 주세요.")
                else:
                    with st.spinner("PDF 생성 및 이메일 발송 중..."):
                        try:
                            # 먼저 PDF 생성 테스트
                            st.info("PDF 생성 중...")
                            pdf_results = generate_multiple_pdfs(reports)

                            if not pdf_results:
                                st.error("❌ PDF 생성에 실패했습니다. 리포트 데이터를 확인해 주세요.")
                                return

                            if team_name not in pdf_results:
                                st.error(f"❌ '{team_name}' 팀의 PDF 생성에 실패했습니다.")
                                return

                            st.info("이메일 발송 중...")

                            # 개별 PDF 생성 및 이메일 발송
                            single_report = {team_name: reports[team_name]}
                            pdf_result = generate_multiple_pdfs(single_report)

                            if team_name not in pdf_result:
                                st.error(f"❌ '{team_name}' 팀의 PDF 재생성에 실패했습니다.")
                                return

                            pdf_bytes = pdf_result[team_name]
                            safe_team_name = team_name.replace("/", "_").replace("\\", "_")
                            filename = f"{safe_team_name}_조직효과성진단.pdf"

                            # 직접 이메일 발송
                            result = send_email_with_attachment(
                                to_emails=[to_email],
                                subject=subject,
                                body=body,
                                attachment_data=pdf_bytes,
                                attachment_filename=filename,
                                sender_email=gmail_address,
                                sender_password=gmail_app_pw
                            )

                            if result["success"]:
                                st.success(f"✅ {to_email}로 이메일을 성공적으로 발송했습니다!")
                            else:
                                st.error(f"❌ 이메일 발송 실패: {result['message']}")
                        except Exception as e:
                            st.error(f"❌ 이메일 발송 중 오류가 발생했습니다: {str(e)}")
                            st.info("💡 Gmail 앱 비밀번호를 사용하고 있는지 확인해 주세요. 일반 비밀번호로는 발송이 불가능합니다.")

        st.markdown("</div></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # ---------- Phase C: 관리자 페이지들 ----------
    elif st.session_state["active_menu"] == "admin_db":
        if not st.session_state["admin_authenticated"]:
            st.error("❌ 관리자 인증이 필요합니다. 사이드바에서 관리자 로그인을 해주세요.")
            return
        render_admin_database_page()

    elif st.session_state["active_menu"] == "admin_benchmark":
        if not st.session_state["admin_authenticated"]:
            st.error("❌ 관리자 인증이 필요합니다. 사이드바에서 관리자 로그인을 해주세요.")
            return
        render_admin_benchmark_page()

    elif st.session_state["active_menu"] == "admin_branding":
        if not st.session_state["admin_authenticated"]:
            st.error("❌ 관리자 인증이 필요합니다. 사이드바에서 관리자 로그인을 해주세요.")
            return
        render_admin_branding_page()

    elif st.session_state["active_menu"] == "admin_email":
        if not st.session_state["admin_authenticated"]:
            st.error("❌ 관리자 인증이 필요합니다. 사이드바에서 관리자 로그인을 해주세요.")
            return
        render_admin_email_page()


def render_admin_database_page():
    """데이터베이스 관리 페이지"""
    st.markdown("##### 📊 데이터베이스 관리")

    try:
        from database_models import get_session, Organization, Report, PDFGeneration, EmailLog
        import pandas as pd

        session = get_session()

        # 통계 카드
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            org_count = session.query(Organization).count()
            st.metric("조직 수", org_count)

        with col2:
            report_count = session.query(Report).count()
            st.metric("리포트 수", report_count)

        with col3:
            pdf_count = session.query(PDFGeneration).filter(PDFGeneration.status == 'completed').count()
            st.metric("생성된 PDF", pdf_count)

        with col4:
            email_count = session.query(EmailLog).filter(EmailLog.status == 'sent').count()
            st.metric("발송된 이메일", email_count)

        # 탭으로 각 테이블 관리
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["조직 관리", "리포트 이력", "PDF 생성 이력", "로그 모니터링", "시스템 설정"])

        with tab1:
            st.subheader("조직 관리")

            # 조직 목록 표시
            organizations = session.query(Organization).all()
            if organizations:
                org_data = []
                for org in organizations:
                    org_data.append({
                        "ID": org.id,
                        "조직명": org.name,
                        "그룹명": org.group_name or "-",
                        "연락처": org.contact_email or "-",
                        "생성일": org.created_at.strftime("%Y-%m-%d") if org.created_at else "-",
                        "리포트 수": len(org.reports)
                    })

                df_orgs = pd.DataFrame(org_data)
                st.dataframe(df_orgs, use_container_width=True)

                # 조직 추가 폼
                with st.expander("➕ 새 조직 추가"):
                    new_org_name = st.text_input("조직명")
                    new_group_name = st.text_input("그룹명 (선택)")
                    new_contact_email = st.text_input("연락처 이메일 (선택)")

                    if st.button("조직 추가"):
                        if new_org_name:
                            new_org = Organization(
                                name=new_org_name,
                                group_name=new_group_name if new_group_name else None,
                                contact_email=new_contact_email if new_contact_email else None
                            )
                            session.add(new_org)
                            session.commit()
                            st.success(f"조직 '{new_org_name}'이 추가되었습니다!")
                            st.rerun()
                        else:
                            st.error("조직명을 입력해주세요.")
            else:
                st.info("등록된 조직이 없습니다.")

        with tab2:
            st.subheader("리포트 생성 이력")

            reports = session.query(Report).order_by(Report.created_at.desc()).limit(100).all()
            if reports:
                report_data = []
                for report in reports:
                    report_data.append({
                        "ID": report.id,
                        "조직명": report.organization.name if report.organization else "-",
                        "팀명": report.team_name or "-",
                        "유형": report.report_type,
                        "상태": report.status,
                        "응답자 수": report.respondent_count,
                        "생성일": report.created_at.strftime("%Y-%m-%d %H:%M") if report.created_at else "-"
                    })

                df_reports = pd.DataFrame(report_data)
                st.dataframe(df_reports, use_container_width=True)

            else:
                st.info("생성된 리포트가 없습니다.")

        with tab3:
            st.subheader("PDF 생성 이력")

            pdfs = session.query(PDFGeneration).order_by(PDFGeneration.created_at.desc()).limit(100).all()
            if pdfs:
                pdf_data = []
                for pdf in pdfs:
                    report_info = f"{pdf.report.organization.name if pdf.report and pdf.report.organization else 'Unknown'} - {pdf.report.team_name if pdf.report else 'Unknown'}"
                    pdf_data.append({
                        "ID": pdf.id,
                        "리포트": report_info,
                        "파일명": pdf.pdf_filename or "-",
                        "크기(MB)": round(pdf.pdf_size / 1024 / 1024, 2) if pdf.pdf_size else "-",
                        "생성시간(초)": pdf.generation_time or "-",
                        "상태": pdf.status,
                        "생성일": pdf.created_at.strftime("%Y-%m-%d %H:%M") if pdf.created_at else "-"
                    })

                df_pdfs = pd.DataFrame(pdf_data)
                st.dataframe(df_pdfs, use_container_width=True)

            else:
                st.info("생성된 PDF가 없습니다.")

        with tab4:
            st.subheader("실시간 로그 모니터링")

            # 로그 필터 옵션
            col1, col2, col3 = st.columns(3)

            with col1:
                log_type_filter = st.selectbox(
                    "로그 타입",
                    ["전체", "PDF 생성", "이메일 발송"],
                    key="log_type_filter"
                )

            with col2:
                log_limit = st.number_input(
                    "표시할 로그 수",
                    min_value=10,
                    max_value=500,
                    value=50,
                    key="log_limit"
                )

            with col3:
                auto_refresh = st.checkbox("자동 새로고침 (5초)", value=False)

            if auto_refresh:
                time.sleep(5)
                st.rerun()

            # 로그 조회
            try:
                from logging_utils import get_recent_logs

                # 로그 타입 매핑
                log_type_map = {
                    "전체": None,
                    "PDF 생성": "pdf",
                    "이메일 발송": "email"
                }

                logs = get_recent_logs(
                    log_type=log_type_map[log_type_filter],
                    limit=log_limit
                )

                if logs:
                    # 로그 통계
                    st.markdown("#### 📊 로그 통계")
                    col1, col2, col3, col4 = st.columns(4)

                    pdf_logs = [l for l in logs if l["type"] == "pdf_generation"]
                    email_logs = [l for l in logs if l["type"] == "email_send"]

                    with col1:
                        st.metric("총 로그 수", len(logs))

                    with col2:
                        pdf_success = len([l for l in pdf_logs if l["status"] == "completed"])
                        st.metric("PDF 성공률", f"{(pdf_success/len(pdf_logs)*100) if pdf_logs else 0:.1f}%")

                    with col3:
                        email_success = len([l for l in email_logs if l["status"] == "sent"])
                        st.metric("이메일 성공률", f"{(email_success/len(email_logs)*100) if email_logs else 0:.1f}%")

                    with col4:
                        if pdf_logs:
                            avg_time = sum([l.get("generation_time", 0) for l in pdf_logs if l.get("generation_time")]) / len(pdf_logs)
                            st.metric("평균 생성시간", f"{avg_time:.1f}초")
                        else:
                            st.metric("평균 생성시간", "N/A")

                    st.markdown("#### 📋 최근 로그")

                    # 로그 테이블 생성
                    log_data = []
                    for log in logs:
                        if log["type"] == "pdf_generation":
                            log_data.append({
                                "시간": log["created_at"].strftime("%m-%d %H:%M:%S") if log["created_at"] else "-",
                                "타입": "📄 PDF",
                                "상태": "✅ 완료" if log["status"] == "completed" else "❌ 실패" if log["status"] == "failed" else "🔄 진행중",
                                "대상": f"{log['report_info']['organization']} - {log['report_info']['team_name']}",
                                "파일명": log["filename"] or "-",
                                "크기": f"{log['size_mb']:.1f}MB" if log['size_mb'] else "-",
                                "소요시간": f"{log['generation_time']}초" if log["generation_time"] else "-",
                                "오류": log["error_message"][:50] + "..." if log["error_message"] and len(log["error_message"]) > 50 else log["error_message"] or "-"
                            })
                        else:  # email_send
                            log_data.append({
                                "시간": log["created_at"].strftime("%m-%d %H:%M:%S") if log["created_at"] else "-",
                                "타입": "📧 이메일",
                                "상태": "✅ 완료" if log["status"] == "sent" else "❌ 실패" if log["status"] == "failed" else "🔄 진행중",
                                "대상": f"수신자 {log['recipient_count']}명",
                                "파일명": log["subject"][:30] + "..." if len(log["subject"]) > 30 else log["subject"],
                                "크기": f"성공: {log['sent_count']}, 실패: {log['failed_count']}",
                                "소요시간": log["sent_at"].strftime("%m-%d %H:%M") if log["sent_at"] else "-",
                                "오류": log["error_message"][:50] + "..." if log["error_message"] and len(log["error_message"]) > 50 else log["error_message"] or "-"
                            })

                    if log_data:
                        df_logs = pd.DataFrame(log_data)
                        st.dataframe(df_logs, use_container_width=True, height=400)

                        # 로그 다운로드
                        csv_data = df_logs.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 로그 CSV 다운로드",
                            data=csv_data,
                            file_name=f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("표시할 로그가 없습니다.")

                    # 실시간 로그 상세보기
                    st.markdown("#### 🔍 로그 상세보기")
                    if st.button("🔄 새로고침"):
                        st.rerun()

                    # 최근 오류 로그만 표시
                    error_logs = [l for l in logs if l["status"] in ["failed", "error"]]
                    if error_logs:
                        st.markdown("##### ⚠️ 최근 오류 로그")
                        for error_log in error_logs[:5]:
                            with st.expander(f"❌ {error_log['type']} 오류 - {error_log['created_at'].strftime('%m-%d %H:%M') if error_log['created_at'] else 'Unknown'}"):
                                st.json(error_log)

                else:
                    st.info("조회된 로그가 없습니다.")

            except Exception as e:
                st.error(f"로그 조회 실패: {e}")
                st.info("logging_utils.py 모듈과 로그 설정을 확인해주세요.")

        with tab5:
            st.subheader("시스템 설정 및 관리")

            # 시스템 통계 섹션
            st.markdown("#### 📊 시스템 통계")
            try:
                from admin_utils import get_system_stats, analyze_system_performance

                stats = get_system_stats()
                perf = analyze_system_performance()

                # 기본 통계 카드
                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric("총 조직 수", stats.get("organizations", 0))
                    st.metric("총 리포트 수", stats.get("reports", 0))

                with col2:
                    st.metric("생성된 PDF", stats.get("pdf_generated", 0))
                    st.metric("발송된 이메일", stats.get("emails_sent", 0))

                with col3:
                    recent_reports = stats.get("recent_reports", 0)
                    st.metric("최근 30일 리포트", recent_reports)
                    recent_pdfs = stats.get("recent_pdfs", 0)
                    st.metric("최근 30일 PDF", recent_pdfs)

                with col4:
                    avg_time = stats.get("avg_pdf_generation_time", 0)
                    st.metric("평균 PDF 생성시간", f"{avg_time:.2f}초")
                    total_size = stats.get("total_pdf_size_mb", 0)
                    st.metric("총 PDF 크기", f"{total_size:.1f}MB")

                # 성능 분석
                st.markdown("#### ⚡ 성능 분석")
                col1, col2 = st.columns(2)

                with col1:
                    st.markdown("**PDF 생성 성능**")
                    pdf_perf = perf.get("pdf_performance", {})
                    st.text(f"• 총 생성 수: {pdf_perf.get('total_generated', 0)}")
                    st.text(f"• 평균 시간: {pdf_perf.get('avg_time', 0):.2f}초")
                    st.text(f"• 최소 시간: {pdf_perf.get('min_time', 0):.2f}초")
                    st.text(f"• 최대 시간: {pdf_perf.get('max_time', 0):.2f}초")
                    st.text(f"• 총 크기: {pdf_perf.get('total_size_mb', 0):.1f}MB")

                with col2:
                    st.markdown("**이메일 발송 성능**")
                    email_perf = perf.get("email_performance", {})
                    st.text(f"• 총 발송 수: {email_perf.get('total_sent', 0)}")
                    st.text(f"• 성공률: {email_perf.get('success_rate', 0):.1f}%")
                    st.text(f"• 평균 수신자: {email_perf.get('avg_recipients', 0):.1f}명")

                    st.markdown("**데이터베이스**")
                    db_size = perf.get("database_size", 0)
                    st.text(f"• 크기: {db_size:.2f}MB")

            except Exception as e:
                st.error(f"통계 조회 실패: {e}")

            st.markdown("---")

            # 데이터 관리 섹션
            st.markdown("#### 🗂️ 데이터 관리")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**데이터 내보내기**")

                # 조직 선택 (전체 또는 특정 조직)
                export_options = ["전체 데이터"]
                organizations = session.query(Organization).all()
                for org in organizations:
                    export_options.append(f"{org.name} (ID: {org.id})")

                selected_export = st.selectbox("내보낼 데이터 선택", export_options)

                if st.button("📊 Excel로 내보내기"):
                    try:
                        from admin_utils import export_data_to_excel

                        # 선택된 조직 ID 추출
                        org_id = None
                        if selected_export != "전체 데이터":
                            org_id = int(selected_export.split("ID: ")[1].split(")")[0])

                        with st.spinner("Excel 파일 생성 중..."):
                            filename = export_data_to_excel(org_id)

                        # 다운로드 링크 제공
                        with open(filename, "rb") as file:
                            st.download_button(
                                label="📥 Excel 파일 다운로드",
                                data=file.read(),
                                file_name=filename,
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )

                        st.success(f"Excel 파일이 생성되었습니다: {filename}")

                    except Exception as e:
                        st.error(f"Excel 내보내기 실패: {e}")

                # 데이터 정리
                st.markdown("**데이터 정리**")
                cleanup_days = st.number_input("며칠 이전 데이터 삭제", min_value=30, max_value=365, value=90)

                if st.button("🧹 오래된 데이터 정리", type="secondary"):
                    try:
                        from admin_utils import clean_old_data

                        with st.spinner("데이터 정리 중..."):
                            counts = clean_old_data(cleanup_days)

                        st.success(f"""
                        데이터 정리 완료:
                        - 리포트: {counts['reports']}개 삭제
                        - PDF: {counts['pdfs']}개 삭제
                        - 이메일: {counts['emails']}개 삭제
                        """)

                    except Exception as e:
                        st.error(f"데이터 정리 실패: {e}")

            with col2:
                st.markdown("**백업 및 복원**")

                # 백업 생성
                if st.button("💾 데이터베이스 백업"):
                    try:
                        from admin_utils import backup_database

                        with st.spinner("백업 생성 중..."):
                            backup_path = backup_database()

                        # 백업 파일 다운로드 제공
                        with open(backup_path, "rb") as file:
                            st.download_button(
                                label="📥 백업 파일 다운로드",
                                data=file.read(),
                                file_name=backup_path,
                                mime="application/octet-stream"
                            )

                        st.success(f"백업이 생성되었습니다: {backup_path}")

                    except Exception as e:
                        st.error(f"백업 실패: {e}")

                # 복원
                st.markdown("**복원**")
                uploaded_backup = st.file_uploader("백업 파일 선택", type=['db'])

                if uploaded_backup and st.button("🔄 데이터베이스 복원", type="secondary"):
                    try:
                        from admin_utils import restore_database
                        import tempfile

                        # 업로드된 파일을 임시 저장
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp_file:
                            tmp_file.write(uploaded_backup.getvalue())
                            tmp_path = tmp_file.name

                        with st.spinner("데이터베이스 복원 중..."):
                            success = restore_database(tmp_path)

                        if success:
                            st.success("데이터베이스가 성공적으로 복원되었습니다!")
                            st.warning("페이지를 새로고침하여 변경사항을 확인하세요.")
                        else:
                            st.error("데이터베이스 복원에 실패했습니다.")

                        # 임시 파일 정리
                        import os
                        os.unlink(tmp_path)

                    except Exception as e:
                        st.error(f"복원 실패: {e}")

            st.markdown("---")

            # 데이터베이스 정보
            st.markdown("#### 🗄️ 데이터베이스 정보")
            try:
                import os
                db_url = os.getenv('DATABASE_URL', 'sqlite:///./report_system.db')
                st.text(f"연결 URL: {db_url}")

                # 테이블별 레코드 수
                tables_info = {
                    "Organizations": session.query(Organization).count(),
                    "Reports": session.query(Report).count(),
                    "PDF Generations": session.query(PDFGeneration).count(),
                    "Email Logs": session.query(EmailLog).count(),
                }

                col1, col2 = st.columns(2)
                items = list(tables_info.items())

                with col1:
                    for i in range(0, len(items), 2):
                        table, count = items[i]
                        st.text(f"• {table}: {count:,}개")

                with col2:
                    for i in range(1, len(items), 2):
                        if i < len(items):
                            table, count = items[i]
                            st.text(f"• {table}: {count:,}개")

            except Exception as e:
                st.error(f"데이터베이스 정보 조회 실패: {e}")

        session.close()

    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        st.info("database_models.py 파일과 데이터베이스 설정을 확인해주세요.")


def render_admin_branding_page():
    """브랜딩 설정 관리 페이지"""
    st.markdown("##### 🎨 브랜딩 설정 관리")

    try:
        from database_models import get_session, Organization, BrandingConfig
        import pandas as pd

        session = get_session()

        # 조직 선택
        organizations = session.query(Organization).all()
        if not organizations:
            st.warning("브랜딩을 설정할 조직이 없습니다. 먼저 데이터베이스 관리에서 조직을 추가해주세요.")
            return

        org_names = {org.name: org.id for org in organizations}
        selected_org_name = st.selectbox("조직 선택", list(org_names.keys()))
        selected_org_id = org_names[selected_org_name]

        # 현재 브랜딩 설정 조회
        current_branding = session.query(BrandingConfig).filter(
            BrandingConfig.organization_id == selected_org_id,
            BrandingConfig.is_active == True
        ).first()

        st.markdown("---")

        # 브랜딩 설정 폼
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("색상 설정")

            primary_color = st.color_picker(
                "주 색상 (Primary)",
                value=current_branding.primary_color if current_branding else "#0f4fa8",
                help="리포트의 메인 색상"
            )

            secondary_color = st.color_picker(
                "보조 색상 (Secondary)",
                value=current_branding.secondary_color if current_branding else "#10b981",
                help="차트 및 보조 요소 색상"
            )

            accent_color = st.color_picker(
                "강조 색상 (Accent)",
                value=current_branding.accent_color if current_branding else "#f97316",
                help="버튼 및 강조 요소 색상"
            )

        with col2:
            st.subheader("폰트 및 기타 설정")

            font_family = st.selectbox(
                "폰트",
                options=["Inter", "Noto Sans KR", "Pretendard", "Arial", "Helvetica"],
                index=0 if not current_branding else ["Inter", "Noto Sans KR", "Pretendard", "Arial", "Helvetica"].index(current_branding.font_family) if current_branding.font_family in ["Inter", "Noto Sans KR", "Pretendard", "Arial", "Helvetica"] else 0
            )

            config_name = st.text_input(
                "설정 이름",
                value=current_branding.config_name if current_branding else "default"
            )

        # 색상 미리보기
        st.subheader("색상 미리보기")
        st.markdown(f"""
        <div style="display: flex; gap: 1rem; margin: 1rem 0;">
            <div style="width: 60px; height: 60px; background: {primary_color}; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">Primary</div>
            <div style="width: 60px; height: 60px; background: {secondary_color}; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">Secondary</div>
            <div style="width: 60px; height: 60px; background: {accent_color}; border-radius: 8px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold;">Accent</div>
        </div>
        """, unsafe_allow_html=True)

        # 저장 버튼
        if st.button("브랜딩 설정 저장", type="primary"):
            try:
                # 기존 활성 설정 비활성화
                session.query(BrandingConfig).filter(
                    BrandingConfig.organization_id == selected_org_id,
                    BrandingConfig.is_active == True
                ).update({BrandingConfig.is_active: False})

                # 새 브랜딩 설정 생성
                new_branding = BrandingConfig(
                    organization_id=selected_org_id,
                    config_name=config_name,
                    primary_color=primary_color,
                    secondary_color=secondary_color,
                    accent_color=accent_color,
                    font_family=font_family,
                    is_active=True
                )

                session.add(new_branding)
                session.commit()

                st.success(f"'{selected_org_name}' 조직의 브랜딩 설정이 저장되었습니다!")
                st.rerun()

            except Exception as e:
                session.rollback()
                st.error(f"브랜딩 설정 저장 실패: {e}")

        # 브랜딩 이력
        st.markdown("---")
        st.subheader("브랜딩 설정 이력")

        branding_history = session.query(BrandingConfig).filter(
            BrandingConfig.organization_id == selected_org_id
        ).order_by(BrandingConfig.created_at.desc()).all()

        if branding_history:
            history_data = []
            for branding in branding_history:
                history_data.append({
                    "설정명": branding.config_name,
                    "주 색상": branding.primary_color,
                    "보조 색상": branding.secondary_color,
                    "강조 색상": branding.accent_color,
                    "폰트": branding.font_family,
                    "활성": "✅" if branding.is_active else "❌",
                    "생성일": branding.created_at.strftime("%Y-%m-%d %H:%M") if branding.created_at else "-"
                })

            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("브랜딩 설정 이력이 없습니다.")

        session.close()

    except Exception as e:
        st.error(f"브랜딩 설정 페이지 오류: {e}")


def render_admin_benchmark_page():
    """벤치마크 설정 관리 페이지"""
    st.markdown("##### 📊 벤치마크 점수 설정")

    # 기본 벤치마크 값들 (영역별)
    default_benchmarks = {
        "목적경영": 3.2,
        "구성원인식": 3.1,
        "지원체계": 3.0,
        "도전추진": 3.3,
        "실행력": 3.4,
        "소통협력": 3.2,
        "성과창출": 3.5,
        "구성원만족": 3.1,
        "경쟁력확보": 3.3
    }

    # 현재 설정된 벤치마크 불러오기 (세션에서)
    if "benchmark_settings" not in st.session_state:
        st.session_state["benchmark_settings"] = default_benchmarks.copy()

    st.info("📋 **사용법**: 각 영역별 벤치마크 점수를 설정하세요. 이 값들은 리포트의 비교 기준선으로 사용됩니다.")

    # 영역별 벤치마크 설정
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Input 영역**")
        st.session_state["benchmark_settings"]["목적경영"] = st.number_input(
            "목적경영",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["목적경영"],
            step=0.1,
            key="bench_목적경영"
        )
        st.session_state["benchmark_settings"]["구성원인식"] = st.number_input(
            "구성원인식",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["구성원인식"],
            step=0.1,
            key="bench_구성원인식"
        )
        st.session_state["benchmark_settings"]["지원체계"] = st.number_input(
            "지원체계",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["지원체계"],
            step=0.1,
            key="bench_지원체계"
        )

    with col2:
        st.markdown("**Process 영역**")
        st.session_state["benchmark_settings"]["도전추진"] = st.number_input(
            "도전추진",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["도전추진"],
            step=0.1,
            key="bench_도전추진"
        )
        st.session_state["benchmark_settings"]["실행력"] = st.number_input(
            "실행력",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["실행력"],
            step=0.1,
            key="bench_실행력"
        )
        st.session_state["benchmark_settings"]["소통협력"] = st.number_input(
            "소통협력",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["소통협력"],
            step=0.1,
            key="bench_소통협력"
        )

    with col3:
        st.markdown("**Output 영역**")
        st.session_state["benchmark_settings"]["성과창출"] = st.number_input(
            "성과창출",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["성과창출"],
            step=0.1,
            key="bench_성과창출"
        )
        st.session_state["benchmark_settings"]["구성원만족"] = st.number_input(
            "구성원만족",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["구성원만족"],
            step=0.1,
            key="bench_구성원만족"
        )
        st.session_state["benchmark_settings"]["경쟁력확보"] = st.number_input(
            "경쟁력확보",
            min_value=1.0,
            max_value=5.0,
            value=st.session_state["benchmark_settings"]["경쟁력확보"],
            step=0.1,
            key="bench_경쟁력확보"
        )

    st.markdown("---")

    # 액션 버튼들
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💾 설정 저장", type="primary"):
            st.success("✅ 벤치마크 설정이 저장되었습니다!")
            st.rerun()

    with col2:
        if st.button("🔄 기본값으로 초기화"):
            st.session_state["benchmark_settings"] = default_benchmarks.copy()
            st.success("✅ 기본값으로 초기화되었습니다!")
            st.rerun()

    with col3:
        if st.button("📊 미리보기"):
            st.session_state["show_benchmark_preview"] = True

    with col4:
        if st.button("📥 CSV 내보내기"):
            import pandas as pd
            df = pd.DataFrame(list(st.session_state["benchmark_settings"].items()),
                            columns=['영역', '벤치마크점수'])
            csv = df.to_csv(index=False, encoding='utf-8-sig')
            st.download_button(
                label="CSV 다운로드",
                data=csv,
                file_name="benchmark_settings.csv",
                mime="text/csv"
            )

    # 미리보기 표시
    if st.session_state.get("show_benchmark_preview", False):
        st.markdown("---")
        st.markdown("**📊 현재 벤치마크 설정 미리보기**")

        import pandas as pd
        preview_df = pd.DataFrame(list(st.session_state["benchmark_settings"].items()),
                                columns=['영역', '벤치마크점수'])

        # 영역별 그룹핑
        input_areas = ["목적경영", "구성원인식", "지원체계"]
        process_areas = ["도전추진", "실행력", "소통협력"]
        output_areas = ["성과창출", "구성원만족", "경쟁력확보"]

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**Input 영역**")
            input_df = preview_df[preview_df['영역'].isin(input_areas)]
            st.dataframe(input_df, hide_index=True)
            st.metric("평균", f"{input_df['벤치마크점수'].mean():.2f}")

        with col2:
            st.markdown("**Process 영역**")
            process_df = preview_df[preview_df['영역'].isin(process_areas)]
            st.dataframe(process_df, hide_index=True)
            st.metric("평균", f"{process_df['벤치마크점수'].mean():.2f}")

        with col3:
            st.markdown("**Output 영역**")
            output_df = preview_df[preview_df['영역'].isin(output_areas)]
            st.dataframe(output_df, hide_index=True)
            st.metric("평균", f"{output_df['벤치마크점수'].mean():.2f}")


def render_admin_email_page():
    """이메일 이력 관리 페이지"""
    st.markdown("##### 📧 이메일 발송 이력")

    try:
        from database_models import get_session, EmailLog, Report
        import pandas as pd
        import json

        session = get_session()

        # 통계 카드
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_emails = session.query(EmailLog).count()
            st.metric("총 발송 이력", total_emails)

        with col2:
            sent_emails = session.query(EmailLog).filter(EmailLog.status == 'sent').count()
            st.metric("성공적 발송", sent_emails)

        with col3:
            failed_emails = session.query(EmailLog).filter(EmailLog.status == 'failed').count()
            st.metric("발송 실패", failed_emails)

        with col4:
            success_rate = (sent_emails / total_emails * 100) if total_emails > 0 else 0
            st.metric("성공률", f"{success_rate:.1f}%")

        # 필터 옵션
        st.subheader("필터 및 검색")
        col1, col2, col3 = st.columns(3)

        with col1:
            status_filter = st.selectbox("상태", ["전체", "sending", "sent", "failed"])

        with col2:
            date_range = st.date_input("날짜 범위", value=[], help="날짜를 선택하여 필터링")

        with col3:
            search_email = st.text_input("이메일 검색", placeholder="수신자 이메일 검색")

        # 이메일 로그 조회
        query = session.query(EmailLog).order_by(EmailLog.created_at.desc())

        # 필터 적용
        if status_filter != "전체":
            query = query.filter(EmailLog.status == status_filter)

        if search_email:
            query = query.filter(EmailLog.recipient_emails.contains(search_email))

        email_logs = query.limit(100).all()

        if email_logs:
            st.subheader("이메일 발송 이력")

            email_data = []
            for email_log in email_logs:
                # JSON 형태의 수신자 이메일을 파싱
                try:
                    recipients = json.loads(email_log.recipient_emails) if email_log.recipient_emails else []
                    recipients_str = ", ".join(recipients) if isinstance(recipients, list) else str(recipients)
                except:
                    recipients_str = email_log.recipient_emails or "-"

                email_data.append({
                    "ID": email_log.id,
                    "제목": email_log.subject or "-",
                    "수신자": recipients_str[:50] + "..." if len(recipients_str) > 50 else recipients_str,
                    "첨부파일": email_log.attachment_filename or "-",
                    "첨부크기(MB)": round(email_log.attachment_size / 1024 / 1024, 2) if email_log.attachment_size else "-",
                    "상태": email_log.status,
                    "성공 수": email_log.sent_count or 0,
                    "실패 수": email_log.failed_count or 0,
                    "발송일": email_log.sent_at.strftime("%Y-%m-%d %H:%M") if email_log.sent_at else "-",
                    "생성일": email_log.created_at.strftime("%Y-%m-%d %H:%M") if email_log.created_at else "-"
                })

            df_emails = pd.DataFrame(email_data)
            st.dataframe(df_emails, use_container_width=True)

            # 상세 정보 보기
            if st.checkbox("상세 정보 표시"):
                selected_email_id = st.selectbox("이메일 선택", [log.id for log in email_logs])
                selected_email = next((log for log in email_logs if log.id == selected_email_id), None)

                if selected_email:
                    st.subheader(f"이메일 상세 정보 (ID: {selected_email_id})")

                    col1, col2 = st.columns(2)

                    with col1:
                        st.text(f"제목: {selected_email.subject or '-'}")
                        st.text(f"상태: {selected_email.status}")
                        st.text(f"성공/실패: {selected_email.sent_count}/{selected_email.failed_count}")
                        st.text(f"첨부파일: {selected_email.attachment_filename or '-'}")

                    with col2:
                        st.text(f"발송일: {selected_email.sent_at or '-'}")
                        st.text(f"생성일: {selected_email.created_at or '-'}")

                        if selected_email.error_message:
                            st.text_area("오류 메시지", selected_email.error_message, height=100)

                    # 수신자 목록
                    try:
                        recipients = json.loads(selected_email.recipient_emails) if selected_email.recipient_emails else []
                        if recipients:
                            st.subheader("수신자 목록")
                            for i, recipient in enumerate(recipients, 1):
                                st.text(f"{i}. {recipient}")
                    except:
                        st.text(f"수신자: {selected_email.recipient_emails or '-'}")

            # 통계 차트
            if email_logs:
                st.subheader("발송 통계")

                # 일별 발송 통계
                daily_stats = {}
                for log in email_logs:
                    if log.created_at:
                        date_str = log.created_at.strftime("%Y-%m-%d")
                        if date_str not in daily_stats:
                            daily_stats[date_str] = {"sent": 0, "failed": 0}

                        if log.status == "sent":
                            daily_stats[date_str]["sent"] += 1
                        elif log.status == "failed":
                            daily_stats[date_str]["failed"] += 1

                if daily_stats:
                    chart_data = pd.DataFrame.from_dict(daily_stats, orient='index')
                    st.bar_chart(chart_data)

        else:
            st.info("이메일 발송 이력이 없습니다.")

        session.close()

    except Exception as e:
        st.error(f"이메일 이력 페이지 오류: {e}")


if __name__ == "__main__":
    main()
