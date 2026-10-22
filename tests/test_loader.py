import pytest
from conftest import DROP, write_doc

from hangil_rag.loader import chunks, load_docs, parse

DEMO_IDS = {"doc-arex-train-types", "doc-express-ticket", "doc-allstop-ticket", "doc-deposit-refund"}


def test_real_knowledge_loads_with_backend_demo_ids():
    docs = load_docs()
    assert {d.doc_id for d in docs} == DEMO_IDS
    assert {d.doc_id: d.train_type for d in docs if d.train_type} == {
        "doc-express-ticket": "express",
        "doc-allstop-ticket": "allstop",
    }


def test_real_knowledge_hides_todo_comments():
    for d in load_docs():
        for text in (d.body_ko, d.body_en):
            assert "TODO" not in text and "<!--" not in text, d.doc_id


@pytest.mark.parametrize(
    ("meta", "message"),
    [
        ({"verified_at": DROP}, "verified_at"),
        ({"scope": "price"}, "scope"),
        ({"train_type": "ktx"}, "train_type"),
        ({"source_url": None}, "source_url 필수"),  # official 인데 URL 없음
        ({"source_url": DROP}, "source_url"),  # 키 자체는 필수 (field_check 면 null)
        ({"verified_at": "어제"}, "verified_at"),
        ({"keywords": ["x"]}, "keywords"),  # 정하지 않은 필드
    ],
)
def test_invalid_front_matter_is_rejected(tmp_path, meta, message):
    path = write_doc(tmp_path, "doc-bad", **meta)
    with pytest.raises(ValueError, match=message):
        parse(path)


def test_field_check_doc_may_have_no_url(tmp_path):
    doc = parse(write_doc(tmp_path, "doc-field", source_kind="field_check", source_url=None))
    assert doc.source_url is None and doc.verified_at.isoformat() == "2026-10-22"


def test_duplicate_id_is_rejected(tmp_path):
    write_doc(tmp_path, "doc-a")
    (tmp_path / "copy.md").write_text((tmp_path / "doc-a.md").read_text())
    with pytest.raises(ValueError, match="doc_id 중복"):
        load_docs(tmp_path)


@pytest.mark.parametrize(
    "body",
    [
        "## ko\n\n본문\n",  # en 없음
        "## ko\n\n본문\n\n## en\n\nbody\n\n## ja\n\n本文\n",  # 정하지 않은 절
        "앞 글\n\n## ko\n\n본문\n\n## en\n\nbody\n",
        "## ko\n\n<!-- TODO -->\n\n## en\n\nbody\n",  # 주석만 있으면 빈 절
    ],
)
def test_sections_must_be_ko_and_en(tmp_path, body):
    path = write_doc(tmp_path, "doc-x")
    head = path.read_text().split("## ko")[0]
    path.write_text(head + body)
    with pytest.raises(ValueError):
        parse(path)


def test_missing_front_matter(tmp_path):
    (tmp_path / "doc-x.md").write_text("## ko\n\n본문\n\n## en\n\nbody\n")
    with pytest.raises(ValueError, match="머리말"):
        load_docs(tmp_path)


def test_chunks_split_by_heading(tmp_path):
    ko = "들어가는 말\n\n### 사는 곳\n\n지하 2층\n\n<!-- TODO(R3): 확인 -->\n\n### 결제\n\n확인 필요"
    doc = parse(write_doc(tmp_path, "doc-c", ko=ko, en="intro only", title_en="Doc C"))
    got = [(c.lang, c.heading, c.text) for c in chunks(doc)]
    assert got == [
        ("ko", "시험 문서", "들어가는 말"),
        ("ko", "사는 곳", "지하 2층"),
        ("ko", "결제", "확인 필요"),
        ("en", "Doc C", "intro only"),
    ]
