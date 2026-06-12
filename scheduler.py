"""자동 논문 수집 스케줄러 — 별도 터미널에서 실행"""

import os
import time
import logging
import schedule
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

from fetcher import fetch_pubmed, DEFAULT_QUERY
from tagger import tag_paper
from store import upsert_papers, count_papers

load_dotenv()
GROQ_KEY = os.getenv("GROQ_API_KEY", "")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def collect_new_papers(days_back: int = 8, max_results: int = 50):
    """PubMed에서 새 논문 수집 후 DB에 저장."""
    log.info("=== 자동 수집 시작 ===")
    if not GROQ_KEY:
        log.error("GROQ_API_KEY 없음. .env 확인 필요")
        return

    client = Groq(api_key=GROQ_KEY)

    try:
        papers = fetch_pubmed(DEFAULT_QUERY, days_back=days_back, max_results=max_results)
        log.info(f"PubMed 수집: {len(papers)}편")

        tagged = []
        for i, paper in enumerate(papers):
            tagged.append(tag_paper(paper, client))
            if (i + 1) % 10 == 0:
                log.info(f"  태깅 중... {i+1}/{len(papers)}")
            time.sleep(4)  # free tier: 15 RPM 제한

        saved = upsert_papers(tagged)
        total = count_papers()
        log.info(f"신규 저장: {saved}편 | DB 누적: {total}편")

    except Exception as e:
        log.error(f"수집 실패: {e}")

    log.info("=== 자동 수집 완료 ===\n")


# ── 스케줄 설정 ──────────────────────────────────────────────
# 매주 월요일 오전 6시
schedule.every().monday.at("06:00").do(collect_new_papers)

# 매일 수집 원하면 아래 줄 주석 해제 (위 줄은 주석 처리)
# schedule.every().day.at("06:00").do(collect_new_papers)

if __name__ == "__main__":
    log.info("스케줄러 시작 — 매주 월요일 06:00 자동 수집")
    log.info(f"다음 실행: {schedule.next_run()}")

    while True:
        schedule.run_pending()
        time.sleep(60)
