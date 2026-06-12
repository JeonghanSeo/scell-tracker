"""논문에 Method / Disease / Protocol 태그를 자동 부여합니다."""

import json

SYSTEM_PROMPT = """You are a single-cell biology expert. Given a paper title and abstract, extract structured metadata.

Return ONLY valid JSON with this exact structure:
{
  "methods": ["list of methods used"],
  "diseases": ["list of diseases or cancer types"],
  "protocols": {
    "tissue_source": "tissue or cell source",
    "dissociation": "dissociation method if mentioned",
    "isolation": "cell/nuclei isolation method",
    "platform": "sequencing platform",
    "fixation": "fixation/preservation method if mentioned",
    "cell_count": "approximate cell number if mentioned"
  },
  "summary_ko": "3-4 sentences Korean summary: background, method, key findings, significance",
  "keywords": ["up to 5 key biological terms"]
}

METHOD options (use exact terms): scRNA-seq, snRNA-seq, spatial transcriptomics, Visium, Xenium, MERFISH, scATAC-seq, snATAC-seq, Multiome, CITE-seq, scTCR-seq, scBCR-seq, trajectory analysis, cell-cell communication, pseudotime, integration, deconvolution, other

DISEASE options: lung cancer, breast cancer, colorectal cancer, liver cancer, pancreatic cancer, prostate cancer, ovarian cancer, glioblastoma, AML, ALL, CLL, lymphoma, melanoma, kidney cancer, bladder cancer, Alzheimer, Parkinson, IBD, Crohn, ulcerative colitis, rheumatoid arthritis, COVID-19, normal tissue, development, other

If information is not mentioned, use empty string or empty list."""


def tag_paper(paper: dict, client) -> dict:
    prompt = f"Title: {paper['title']}\n\nAbstract: {paper['abstract']}"
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        tags = json.loads(text)
    except Exception as e:
        tags = {
            "methods": [], "diseases": [], "protocols": {},
            "summary_ko": f"태깅 실패: {e}", "keywords": [],
        }
    return {**paper, **tags}
