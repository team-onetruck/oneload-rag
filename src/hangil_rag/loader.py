"""knowledge/*.md 읽기 · 검증 · 분할.

문서 1건 = Markdown 1개: YAML 머리말 + `## ko` / `## en` 두 절 (규칙은 knowledge/README.md).
`<!-- ... -->` 주석(TODO 등)은 검색 · 발췌에서 뺀다. 오류는 파일 이름과 함께 ValueError 로 올린다.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Lang = Literal["ko", "en"]
LANGS: tuple[Lang, ...] = ("ko", "en")
TRAIN_TYPES = ("express", "allstop")

_PACKAGED = Path(__file__).resolve().parent / "knowledge"  # 휠 설치 (pyproject force-include)
_REPO = Path(__file__).resolve().parents[2] / "knowledge"  # 저장소 checkout · editable 설치

_FRONT = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
_SECTION = re.compile(r"^## +(\S+) *$", re.M)
_SUBHEADING = re.compile(r"^### +(.+?) *$", re.M)
_COMMENT = re.compile(r"<!--.*?-->", re.S)


class Doc(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(pattern=r"^doc-[a-z0-9]+(-[a-z0-9]+)*$")
    title_ko: str = Field(min_length=1)
    title_en: str = Field(min_length=1)
    scope: Literal["ticket", "card", "fare", "help", "transit"]  # help: 도움받을 곳 · transit: 대중교통 이용 일반
    train_type: Literal["express", "allstop"] | None = None  # 그 열차 전용 문서만
    source_url: str | None  # 키는 필수, 값은 field_check 일 때 null
    # community: 이용자 후기 기반 (초기 개발용, 기본 검색에서 제외). field_check: 현장 · 전화 확인
    source_kind: Literal["official", "field_check", "community"]
    other_sources: list[str] = []
    verified_at: date
    verified_by: str = Field(min_length=1)
    body_ko: str = Field(min_length=1)
    body_en: str = Field(min_length=1)

    @model_validator(mode="after")
    def _official_has_url(self) -> Doc:
        if self.source_kind != "field_check" and not self.source_url:
            raise ValueError(f"source_kind={self.source_kind} 이면 source_url 필수")
        return self

    def title(self, lang: str) -> str:
        return self.title_en if lang == "en" else self.title_ko

    def body(self, lang: str) -> str:
        return self.body_en if lang == "en" else self.body_ko

    def allowed(self, train_type: str | None) -> bool:
        """A-21: 슬롯이 express · allstop 이면 다른 열차 전용 문서는 뺀다. 공통 문서는 항상 통과."""
        return train_type not in TRAIN_TYPES or self.train_type in (None, train_type)


@dataclass(frozen=True)
class Chunk:
    doc: Doc
    lang: Lang
    heading: str
    text: str


def knowledge_dir() -> Path:
    env = os.environ.get("RAG_KNOWLEDGE_DIR")
    if env:
        return Path(env)
    return _PACKAGED if _PACKAGED.is_dir() else _REPO


def load_docs(directory: Path | None = None, include_community: bool | None = None) -> list[Doc]:
    """모든 문서를 검증하고, community 문서는 include_community(기본: RAG_INCLUDE_COMMUNITY=1)일 때만 돌려준다."""
    if include_community is None:
        include_community = os.environ.get("RAG_INCLUDE_COMMUNITY") == "1"
    return [d for d in _load_all(directory) if include_community or d.source_kind != "community"]


def _load_all(directory: Path | None) -> list[Doc]:
    directory = directory or knowledge_dir()
    paths = sorted(p for p in directory.glob("*.md") if p.name.lower() != "readme.md")
    if not paths:
        raise ValueError(f"지식 문서 없음: {directory}")
    docs, seen = [], {}
    for path in paths:
        doc = parse(path)
        if doc.doc_id in seen:
            raise ValueError(f"{path.name}: doc_id 중복 {doc.doc_id} (이미 {seen[doc.doc_id]})")
        seen[doc.doc_id] = path.name
        docs.append(doc)
    return docs


def parse(path: Path) -> Doc:
    m = _FRONT.match(path.read_text(encoding="utf-8").replace("\r\n", "\n"))
    if not m:
        raise ValueError(f"{path.name}: '---' 로 감싼 YAML 머리말이 없음")
    try:
        meta = yaml.safe_load(m.group(1))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name}: 머리말 YAML 오류 {exc}") from exc
    if not isinstance(meta, dict):
        raise ValueError(f"{path.name}: 머리말이 key: value 형식이 아님")
    sections = _sections(path, m.group(2))
    try:
        return Doc(**meta, body_ko=sections["ko"], body_en=sections["en"])
    except ValidationError as exc:
        raise ValueError(f"{path.name}: {exc}") from exc


def chunks(doc: Doc) -> list[Chunk]:
    """헤딩 단위 분할: 언어 절마다, 그 안의 `###` 소제목마다 1개. 소제목 앞 글은 제목을 헤딩으로 쓴다."""
    out = []
    for lang in LANGS:
        parts = _SUBHEADING.split(doc.body(lang))  # [앞 글, 소제목1, 본문1, 소제목2, 본문2, ...]
        pairs = [(doc.title(lang), parts[0])] + list(zip(parts[1::2], parts[2::2], strict=True))
        out += [Chunk(doc, lang, h, _clean(t)) for h, t in pairs if _clean(t)]
    return out


def _sections(path: Path, body: str) -> dict[str, str]:
    parts = _SECTION.split(_COMMENT.sub("", body))  # [앞 글, 이름1, 본문1, ...]
    if parts[0].strip():
        raise ValueError(f"{path.name}: 첫 '## ko' 앞에 글이 있음")
    names = parts[1::2]
    if sorted(names) != sorted(LANGS):
        raise ValueError(f"{path.name}: 본문 절은 '## ko' 와 '## en' 하나씩이어야 함 (지금: {names})")
    return {name: text.strip() for name, text in zip(names, parts[2::2], strict=True)}


def _clean(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip()
