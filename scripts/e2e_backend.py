"""백엔드 API 로 R2 Agent + R3 RAG 연결을 끝까지 확인한다 (QA INT-07 의 R3 부분).

README "백엔드 연결" 과 같은 조립(같은 Vision 을 Agent · create_app 양쪽에)을 백엔드 create_app 에 꽂고,
/sessions → /messages · /localizations 를 실제 HTTP 경로(TestClient)로 부른다. LLM 은 FakeLLM (API 키 · 비용 없음).
백엔드 저장소는 읽기만 한다. DB 는 일회용 데이터베이스를 만들어 마이그레이션한다.

    uv run --project ../oneload-backend --with langgraph==1.2.16 --with python-dotenv==1.2.4 --with ../oneload-rag \\
      python scripts/e2e_backend.py
    # DB: E2E_DATABASE_URL (기본 postgresql+psycopg://hangil:hangil@localhost:54329/hangil_rag_e2e, 백엔드 compose DB)
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def find(env: str, name: str) -> Path:
    for p in (os.environ.get(env), ROOT / name, ROOT / f"{name}-main"):
        if p and Path(p).is_dir():
            return Path(p)
    sys.exit(f"옆 레포 없음: {name} ({env} 로 지정)")


BACKEND, AGENT, DATA = (
    find("RAG_BACKEND_DIR", "oneload-backend"),
    find("RAG_AGENT_DIR", "oneload_agent"),
    find("RAG_DATA_DIR", "oneload-data"),
)
DB_URL = os.environ.get("E2E_DATABASE_URL") or "postgresql+psycopg://hangil:hangil@localhost:54329/hangil_rag_e2e"
os.environ["DATABASE_URL"] = DB_URL  # 백엔드 모듈이 엔진을 만들기 전에
os.environ["MAP_DIR"] = str(DATA / "maps")
os.environ.pop("RAG_INCLUDE_COMMUNITY", None)  # 공식 문서만
sys.path[:0] = [str(BACKEND), str(AGENT)]

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from app.ai.rule_agent import RuleAgent  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hangil_r2 import FakeLLM, LLMAgent, LLMVision  # noqa: E402
from sqlalchemy import create_engine, make_url, text  # noqa: E402

from hangil_rag import search_knowledge  # noqa: E402

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


class CountingLLM(FakeLLM):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.scene_calls = 0

    def read_scene(self, image):
        self.scene_calls += 1
        return super().read_scene(image)


def migrate() -> None:
    url = make_url(DB_URL)
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": url.database}).first():
            conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    cwd = Path.cwd()
    os.chdir(BACKEND)  # alembic.ini 의 script_location 이 백엔드 폴더 기준
    try:
        command.upgrade(Config(str(BACKEND / "alembic.ini")), "head")
    finally:
        os.chdir(cwd)


class Client:
    def __init__(self, http: TestClient, language: str):
        self.http = http
        r = self._post(
            "/api/v1/sessions",
            {"language": language, "map_id": "seoul-station", "client": {"platform": "web", "app_version": "e2e"}},
            auth=False,
        )
        self.sid, self.token, self.map_version = r["session_id"], r["session_token"], r["map_version"]

    def _headers(self, auth: bool = True) -> dict:
        h = {"Idempotency-Key": str(uuid.uuid4())}
        return {**h, "Authorization": f"Bearer {self.token}"} if auth else h

    def _post(self, url: str, json=None, *, auth: bool = True, **kw) -> dict:
        r = self.http.post(url, json=json, headers=self._headers(auth), **kw)
        assert r.status_code in (200, 201), f"{url} {r.status_code} {r.text[:300]}"
        return r.json()

    def say(self, message: str) -> dict:
        return self._post(f"/api/v1/sessions/{self.sid}/messages", {"message": message})

    def say_with_photo(self, message: str) -> dict:
        return self._post(
            f"/api/v1/sessions/{self.sid}/messages",
            data={"message": message},
            files={"image": ("machine.jpg", JPEG, "image/jpeg")},
        )

    def localize(self):
        return self.http.post(
            f"/api/v1/sessions/{self.sid}/localizations",
            data={"map_version": self.map_version},
            files={"image": ("sign.jpg", JPEG, "image/jpeg")},
            headers=self._headers(),
        )


def ids(body: dict) -> list[str]:
    return [s["document_id"] for s in body.get("sources", [])]


def main() -> int:
    migrate()
    llm = CountingLLM(scene={"image_quality": "usable", "facilities": ["ticket_machine"]})
    vision = LLMVision(llm)  # README 와 같은 조립
    agent = LLMAgent(llm, search_knowledge=search_knowledge, vision=vision, fallback=RuleAgent())
    results: list[tuple[str, bool, str]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        results.append((name, ok, detail))

    with TestClient(create_app(agent=agent, vision=vision)) as http:
        ko = Client(http, "ko")
        r = ko.say("보증금 환급은 어떻게 해?")
        src = r["sources"][0] if r.get("sources") else {}
        check(
            "이용 질문 → RAG 근거",
            r["status"] == "answered"
            and ids(r)[:1] == ["doc-deposit-refund"]
            and (src.get("source_url") or "").startswith("http")
            and bool(src.get("verified_at")),
            f"{r['status']} {ids(r)} {src.get('verified_at')}",
        )

        fare = Client(http, "ko")
        fare.say("직통열차")
        r = fare.say("직통열차 요금 얼마야?")
        check(
            "요금 질문 → 요금 문서만",
            r["status"] == "answered" and ids(r) == ["doc-fare-arex-express"] and "13,000" in r["assistant_message"],
            f"{r['status']} {ids(r)}",
        )

        allstop = Client(http, "ko")
        allstop.say("공항 가는 티켓 어디서 사?")
        allstop.say("일반열차")
        r = allstop.say("없어요")
        check(
            "일반열차 흐름에 직통 문서 없음 (A-21)",
            (r.get("destination") or {}).get("poi_id") == "poi-allstop-tickets"
            and "doc-allstop-ticket" in ids(r)
            and "doc-express-ticket" not in ids(r),
            f"{r['status']} {ids(r)}",
        )

        en = Client(http, "en")
        r = en.say("How do I get my deposit back?")
        title = r["sources"][0]["title"] if r.get("sources") else ""
        check(
            "영어 세션 → 영어 제목",
            r["status"] == "answered" and title == "Getting the single-journey ticket deposit back",
            f"{r['status']} {title}",
        )

        photo = Client(http, "ko")
        photo.say("직통열차")
        before = llm.scene_calls
        r = photo.say_with_photo("이거 뭐 눌러?")
        check(
            "/messages 첨부 사진을 Agent 가 읽음",
            llm.scene_calls == before + 1 and r["status"] == "answered",
            f"read_scene {llm.scene_calls - before}회, {r['status']} {ids(r)}",
        )

        loc = Client(http, "ko")
        loc.say("직통열차")
        before = llm.scene_calls
        resp = loc.localize()
        check(
            "/localizations 가 같은 Vision 사용",
            resp.status_code == 200 and llm.scene_calls == before + 1,
            f"HTTP {resp.status_code}, read_scene {llm.scene_calls - before}회, {resp.json().get('status')}",
        )

    print("| 확인 | 결과 | 내용 |\n|---|---|---|")
    for name, ok, detail in results:
        print(f"| {name} | {'✅' if ok else '❌'} | {detail} |")
    print(f"\n{sum(ok for _, ok, _ in results)}/{len(results)} 통과 · DB {make_url(DB_URL).database}")
    return 0 if all(ok for _, ok, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
