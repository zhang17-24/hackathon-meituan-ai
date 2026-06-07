#!/usr/bin/env python3
"""Crawl high-quality nail knowledge pages and export chunked JSONL records.

Outputs:
- data/knowledge/crawled_nail_knowledge.jsonl
- data/knowledge/crawled_nail_knowledge_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from nailflow.utils.readability import ReadabilityExtractor


BASE_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BASE_DIR / "data" / "knowledge"


@dataclass(frozen=True)
class KnowledgeSource:
    doc_id: str
    topic: str
    title: str
    source_site: str
    source_url: str
    tags: tuple[str, ...]


SOURCE_REGISTRY: list[KnowledgeSource] = [
    KnowledgeSource(
        doc_id="essie_prep",
        topic="nail_anatomy_and_prep",
        title="Essie - Nail Prep Guide",
        source_site="essie",
        source_url="https://www.essie.com/inspiration/tips-and-trends/how-to-prep-nail-for-manicure",
        tags=("prep", "adhesion", "cuticle"),
    ),
    KnowledgeSource(
        doc_id="essie_shapes",
        topic="nail_shapes",
        title="Essie - Nail Shapes",
        source_site="essie",
        source_url="https://www.essie.com/inspiration/nail-shapes",
        tags=("shape", "oval", "round", "square"),
    ),
    KnowledgeSource(
        doc_id="opi_shapes",
        topic="nail_shapes",
        title="OPI - How to Shape Nails",
        source_site="opi",
        source_url="https://www.opi.com/professionals/how-to-shape-nails",
        tags=("shape", "filing", "almond", "ballerina"),
    ),
    KnowledgeSource(
        doc_id="osha_chemical_hazards",
        topic="salon_safety_chemicals",
        title="OSHA - Chemical Hazards in Nail Salons",
        source_site="osha",
        source_url="https://www.osha.gov/nail-salons/chemical-hazards",
        tags=("safety", "chemicals", "osha", "ventilation"),
    ),
    KnowledgeSource(
        doc_id="osha_biological_hazards",
        topic="biohazard_disinfection",
        title="OSHA - Biological Hazards in Nail Salons",
        source_site="osha",
        source_url="https://www.osha.gov/nail-salons/biological-hazards",
        tags=("disinfection", "biohazard", "hygiene"),
    ),
    KnowledgeSource(
        doc_id="cdc_nail_technicians",
        topic="salon_safety_chemicals",
        title="CDC/NIOSH - Nail Technicians Workplace Safety",
        source_site="cdc",
        source_url="https://www.cdc.gov/niosh/nail-technicians/about/index.html",
        tags=("safety", "niosh", "ventilation", "ppe"),
    ),
]


def _fetch_html(url: str, timeout: int = 30) -> str:
    context = ssl.create_default_context()
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "nailflowKnowledgeCrawler/1.0"},
    )
    with urllib.request.urlopen(req, context=context, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _clean_markdown(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", " ", text)
    text = re.sub(r"[*_>#`~-]", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _split_paragraphs(text: str) -> list[str]:
    cleaned = _clean_markdown(text)
    paras = []
    for block in cleaned.split("\n\n"):
        block = " ".join(line.strip() for line in block.splitlines() if line.strip())
        block = re.sub(r"\s{2,}", " ", block).strip()
        if len(block) >= 80:
            paras.append(block)
    return paras


def _chunk_paragraphs(paragraphs: list[str], min_len: int = 140, max_len: int = 420) -> list[str]:
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = para if not current else f"{current}\n{para}"
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            chunks.append(current.strip())
        if len(para) <= max_len:
            current = para
            continue

        sentences = re.split(r"(?<=[。！？.!?])\s+", para)
        current = ""
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            candidate = sentence if not current else f"{current} {sentence}"
            if len(candidate) <= max_len:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence
        if current and len(current) >= min_len:
            chunks.append(current.strip())
            current = ""

    if current:
        chunks.append(current.strip())

    normalized = [chunk for chunk in chunks if len(chunk) >= min_len]
    return normalized or paragraphs[:1]


def crawl_sources(limit: int = 0) -> dict:
    extractor = ReadabilityExtractor()
    selected_sources = SOURCE_REGISTRY[:limit] if limit > 0 else SOURCE_REGISTRY

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = OUTPUT_DIR / "crawled_nail_knowledge.jsonl"
    report_path = OUTPUT_DIR / "crawled_nail_knowledge_report.json"

    records = []
    report_rows = []

    for source in selected_sources:
        result = {
            "doc_id": source.doc_id,
            "source_url": source.source_url,
            "source_site": source.source_site,
            "topic": source.topic,
            "status": "ok",
            "chunk_count": 0,
        }
        try:
            html = _fetch_html(source.source_url)
            article = extractor.extract_article(html)
            markdown = article.to_markdown(including_title=False)
            paragraphs = _split_paragraphs(markdown)
            chunks = _chunk_paragraphs(paragraphs)
            for idx, chunk in enumerate(chunks):
                records.append({
                    "doc_id": source.doc_id,
                    "chunk_id": f"{source.doc_id}#{idx}",
                    "chunk_index": idx,
                    "title": article.title or source.title,
                    "source_title": source.title,
                    "source_site": source.source_site,
                    "source_url": source.source_url,
                    "topic": source.topic,
                    "tags": list(source.tags),
                    "chunk_text": chunk,
                })
            result["chunk_count"] = len(chunks)
            result["resolved_title"] = article.title or source.title
        except Exception as exc:  # noqa: BLE001
            result["status"] = "error"
            result["error"] = str(exc)
        report_rows.append(result)

    with jsonl_path.open("w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    report = {
        "version": "2026-06-02",
        "source_count": len(selected_sources),
        "chunk_count": len(records),
        "report": report_rows,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "jsonl_path": str(jsonl_path),
        "report_path": str(report_path),
        "chunk_count": len(records),
        "source_count": len(selected_sources),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="抓取高质量美甲知识网页并切分为 JSONL chunks")
    parser.add_argument("--limit", type=int, default=0, help="仅抓取前 N 个 source，0 表示全部")
    args = parser.parse_args()

    result = crawl_sources(limit=args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
