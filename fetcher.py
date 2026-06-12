"""PubMed에서 single-cell 관련 논문을 수집합니다."""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

PUBMED_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_FETCH  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

DEFAULT_QUERY = (
    "(single cell[Title/Abstract] OR single-cell[Title/Abstract] OR scRNA-seq[Title/Abstract] "
    "OR snRNA-seq[Title/Abstract] OR spatial transcriptomics[Title/Abstract] "
    "OR scATAC-seq[Title/Abstract] OR CITE-seq[Title/Abstract])"
)


def fetch_pubmed(query: str = DEFAULT_QUERY, days_back: int = 30, max_results: int = 50) -> list[dict]:
    since = (datetime.today() - timedelta(days=days_back)).strftime("%Y/%m/%d")

    # 1) 검색 — PMID 목록
    search_params = {
        "db": "pubmed", "term": query, "retmax": max_results,
        "retmode": "json", "mindate": since, "datetype": "pdat",
    }
    ids = requests.get(PUBMED_SEARCH, params=search_params, timeout=30).json()
    id_list = ids.get("esearchresult", {}).get("idlist", [])
    if not id_list:
        return []

    # 2) 상세 정보 가져오기
    fetch_params = {
        "db": "pubmed", "id": ",".join(id_list),
        "rettype": "abstract", "retmode": "xml",
    }
    xml_text = requests.get(PUBMED_FETCH, params=fetch_params, timeout=60).text
    root = ET.fromstring(xml_text)

    papers = []
    for article in root.findall(".//PubmedArticle"):
        try:
            pmid   = article.findtext(".//PMID", "")
            title  = article.findtext(".//ArticleTitle", "")
            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(p.text or "" for p in abstract_parts if p.text)
            journal = article.findtext(".//Journal/Title", "")
            year    = article.findtext(".//PubDate/Year", "")
            authors_el = article.findall(".//Author")
            authors = [
                f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
                for a in authors_el[:3]
            ]
            papers.append({
                "pmid": pmid, "title": title, "abstract": abstract,
                "journal": journal, "year": year,
                "authors": ", ".join(authors),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        except Exception:
            continue

    return papers


def fetch_by_pmid(pmid_or_url: str) -> dict | None:
    """PMID 또는 PubMed URL로 단일 논문을 가져옵니다."""
    pmid = pmid_or_url.strip().rstrip("/").split("/")[-1]
    if not pmid.isdigit():
        return None

    xml_text = requests.get(PUBMED_FETCH, params={
        "db": "pubmed", "id": pmid, "rettype": "abstract", "retmode": "xml",
    }, timeout=30).text

    root = ET.fromstring(xml_text)
    article = root.find(".//PubmedArticle")
    if article is None:
        return None

    abstract_parts = article.findall(".//AbstractText")
    abstract = " ".join(p.text or "" for p in abstract_parts if p.text)
    authors_el = article.findall(".//Author")
    authors = [
        f"{a.findtext('LastName', '')} {a.findtext('Initials', '')}".strip()
        for a in authors_el[:5]
    ]
    return {
        "pmid":     pmid,
        "title":    article.findtext(".//ArticleTitle", ""),
        "abstract": abstract,
        "journal":  article.findtext(".//Journal/Title", ""),
        "year":     article.findtext(".//PubDate/Year", ""),
        "authors":  ", ".join(authors),
        "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
    }
