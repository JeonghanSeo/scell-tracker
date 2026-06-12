"""Single-Cell Paper Tracker — Streamlit 메인 앱"""

import os
import json
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

from fetcher import fetch_pubmed, fetch_by_pmid, DEFAULT_QUERY
from tagger import tag_paper
from store import upsert_papers, search_papers, count_papers

load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "")

st.set_page_config(
    page_title="Single-Cell Paper Tracker",
    page_icon="🔬",
    layout="wide",
)

st.title("🔬 Single-Cell Paper Tracker")
st.caption("PubMed 논문 자동 수집 · Method/Disease/Protocol 태깅 · 대화형 검색")

if not GROQ_KEY:
    st.error("⚠️ .env 파일에 GROQ_API_KEY를 입력하세요.")
    st.stop()

_client = Groq(api_key=GROQ_KEY)

# ── 사이드바 ─────────────────────────────────────────────────
with st.sidebar:
    st.header("📥 논문 수집")
    days_back   = st.slider("최근 N일", 7, 180, 30)
    max_results = st.slider("최대 수집 편수", 10, 100, 30)
    custom_query = st.text_area("PubMed 검색어 (선택)", placeholder="기본 쿼리 사용시 비워두세요")

    if st.button("🚀 수집 시작", use_container_width=True):
        query = custom_query.strip() if custom_query.strip() else DEFAULT_QUERY
        with st.spinner("PubMed에서 논문 수집 중..."):
            papers = fetch_pubmed(query, days_back, max_results)
        st.info(f"수집된 논문: {len(papers)}편")

        progress = st.progress(0, text="태깅 중...")
        tagged = []
        for i, paper in enumerate(papers):
            tagged.append(tag_paper(paper, _client))
            progress.progress((i + 1) / len(papers), text=f"태깅 중... {i+1}/{len(papers)}")

        saved = upsert_papers(tagged)
        st.success(f"✅ {saved}편 새로 저장됨")

    st.divider()
    total = count_papers()
    st.metric("DB 저장 논문", f"{total}편")

# ── 필터 ─────────────────────────────────────────────────────
METHOD_OPTIONS = ["전체", "scRNA-seq", "snRNA-seq", "spatial transcriptomics",
                  "Visium", "Xenium", "MERFISH", "scATAC-seq", "Multiome",
                  "CITE-seq", "trajectory analysis", "cell-cell communication", "other"]

DISEASE_OPTIONS = ["전체", "lung cancer", "breast cancer", "colorectal cancer",
                   "liver cancer", "pancreatic cancer", "glioblastoma",
                   "AML", "ALL", "lymphoma", "melanoma",
                   "Alzheimer", "Parkinson", "IBD", "COVID-19",
                   "normal tissue", "development", "other"]

col1, col2 = st.columns(2)
with col1:
    method_filter = st.selectbox("🧬 Method 필터", METHOD_OPTIONS)
with col2:
    disease_filter = st.selectbox("🦠 Disease / Cancer 필터", DISEASE_OPTIONS)

# ── 검색 & 채팅 ───────────────────────────────────────────────
st.divider()
st.subheader("💬 논문 검색 & 질문")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("예: FFPE 샘플로 spatial transcriptomics 한 폐암 논문 알려줘"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("검색 중..."):
            hits = search_papers(
                prompt, n=5,
                method_filter=method_filter if method_filter != "전체" else None,
                disease_filter=disease_filter if disease_filter != "전체" else None,
            )

        if not hits:
            answer = "관련 논문을 찾지 못했습니다. 먼저 사이드바에서 논문을 수집해 주세요."
        else:
            context = "\n\n".join([
                f"[{i+1}] **{h['title']}** ({h['year']}, {h['journal']})\n"
                f"Method: {', '.join(h['methods'])} | Disease: {', '.join(h['diseases'])}\n"
                f"Platform: {h['platform']}\n"
                f"요약: {h['summary_ko']}\n"
                f"URL: {h['url']}"
                for i, h in enumerate(hits)
            ])
            rag_prompt = f"""다음 single-cell 논문들을 참고해서 사용자 질문에 한국어로 답하세요.
논문 목록:
{context}

사용자 질문: {prompt}

답변 지침:
- 관련 논문을 인용하며 답하세요 ([1], [2] 형식)
- 방법론, 질환, 프로토콜 관련 내용을 구체적으로 설명하세요
- 마지막에 참고 논문 링크를 정리해 주세요"""

            response = _client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a helpful research assistant. Respond ONLY in Korean (한국어). Never use Chinese, Japanese, Russian, or any non-Korean characters. Use only Hangul, Arabic numerals, and English technical terms where necessary."},
                    {"role": "user", "content": rag_prompt},
                ],
            )
            answer = response.choices[0].message.content

            answer += "\n\n---\n**📄 검색된 논문**\n"
            for i, h in enumerate(hits):
                tags = " · ".join(h["methods"][:2] + h["diseases"][:2])
                answer += f"\n**[{i+1}]** [{h['title']}]({h['url']})  \n`{tags}` — {h['year']}, {h['journal']}\n"

        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})

# ── 논문 직접 요약 ───────────────────────────────────────────
st.divider()
st.subheader("🔍 논문 직접 요약")
st.caption("PubMed URL 또는 PMID를 입력하면 DB 수집 없이 바로 요약합니다.")

pmid_input = st.text_input(
    "PubMed URL 또는 PMID",
    placeholder="예: https://pubmed.ncbi.nlm.nih.gov/38123456/  또는  38123456",
)

if st.button("📄 요약하기", disabled=not pmid_input.strip()):
    with st.spinner("논문 가져오는 중..."):
        paper = fetch_by_pmid(pmid_input.strip())

    if paper is None:
        st.error("논문을 찾을 수 없습니다. PMID 또는 URL을 확인해주세요.")
    else:
        st.markdown(f"### [{paper['title']}]({paper['url']})")
        st.caption(f"{paper['authors']} | {paper['journal']} {paper['year']}")

        with st.spinner("Groq로 요약 중..."):
            summary_prompt = f"""다음 논문을 한국어로 상세히 요약해주세요. 반드시 한글만 사용하고 한자·중국어·일본어·러시아어는 절대 사용하지 마세요.

제목: {paper['title']}

초록:
{paper['abstract']}

아래 항목으로 구조화해서 답하세요:
**연구 배경**: (왜 이 연구가 필요한가)
**사용 방법**: (어떤 기술/방법론을 사용했는가)
**주요 결과**: (핵심 발견 2-3가지)
**의의**: (이 연구의 중요성)"""

            resp = _client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a biomedical research expert. Always respond ONLY in Korean (한국어). Never use Chinese, Japanese, Russian, or any non-Korean characters."},
                    {"role": "user", "content": summary_prompt},
                ],
            )
            summary = resp.choices[0].message.content

        st.markdown(summary)

        if st.button("💾 DB에 저장", key="save_direct"):
            from tagger import tag_paper
            tagged = tag_paper(paper, _client)
            saved = upsert_papers([tagged])
            if saved:
                st.success("DB에 저장됐습니다.")
            else:
                st.info("이미 DB에 있는 논문입니다.")

# ── 최근 논문 브라우저 ────────────────────────────────────────
st.divider()
if st.checkbox("📋 최근 저장 논문 목록 보기"):
    from store import get_collection
    col = get_collection()
    data = col.get(limit=20, include=["metadatas"])
    if data["ids"]:
        for mid, meta in zip(data["ids"], data["metadatas"]):
            with st.expander(f"**{meta['title']}** ({meta.get('year','')})", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**저널:** {meta.get('journal','')}")
                    st.write(f"**저자:** {meta.get('authors','')}")
                    methods = json.loads(meta.get("methods", "[]"))
                    st.write(f"**Method:** {', '.join(methods)}")
                with c2:
                    diseases = json.loads(meta.get("diseases", "[]"))
                    st.write(f"**Disease:** {', '.join(diseases)}")
                    st.write(f"**Platform:** {meta.get('platform','')}")
                    st.markdown(f"[PubMed 링크]({meta.get('url','')})")
                st.write(f"**요약:** {meta.get('summary_ko','')}")
    else:
        st.info("저장된 논문이 없습니다.")
