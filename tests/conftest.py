from pathlib import Path

import pytest
import yaml

DROP = object()  # write_doc 에서 머리말 필드를 뺄 때

BASE = {
    "title_ko": "시험 문서",
    "title_en": "Test doc",
    "scope": "ticket",
    "source_url": "https://example.invalid/guide",
    "source_kind": "official",
    "verified_at": "2026-10-22",
    "verified_by": "test",
}


def write_doc(directory: Path, doc_id: str, ko: str = "본문", en: str = "body", **meta) -> Path:
    fields = {k: v for k, v in {"doc_id": doc_id, **BASE, **meta}.items() if v is not DROP}
    path = directory / f"{doc_id}.md"
    path.write_text(f"---\n{yaml.safe_dump(fields, allow_unicode=True)}---\n\n## ko\n\n{ko}\n\n## en\n\n{en}\n")
    return path


@pytest.fixture
def fixture_docs(tmp_path) -> Path:
    """실제 문서와 별개인 시험용 문서 (요금 문서 포함: 실제 knowledge/ 에는 요금 문서가 없다)."""
    write_doc(tmp_path, "doc-common", "공항철도 열차 종류 안내", "AREX train types", title_ko="열차 종류")
    write_doc(
        tmp_path,
        "doc-exp",
        "직통열차 승차권 사는 곳",
        "Express ticket office",
        train_type="express",
        title_ko="직통열차 승차권",
        title_en="Express ticket",
    )
    write_doc(
        tmp_path,
        "doc-all",
        "일반열차 승차권 사는 곳",
        "All-stop ticket machine",
        train_type="allstop",
        title_ko="일반열차 승차권",
        title_en="All-stop ticket",
    )
    write_doc(
        tmp_path,
        "doc-fare",
        "직통열차 요금 시험 문서",
        "Express fare test doc",
        scope="fare",
        priced=["직통열차"],
        title_ko="직통열차 요금",
        title_en="Express fare",
    )
    return tmp_path
