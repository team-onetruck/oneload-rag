"""출처 재확인 주기: 확인일(verified_at)이 오래된 문서가 있으면 실패해서 다시 확인하게 한다 (설계서 3.2).

제안값: 요금(scope=fare) 90일, 그 밖 180일. 다시 확인했으면 문서 머리말의 verified_at · verified_by 를 고친다.
"""

from datetime import date

from hangil_rag.loader import load_docs

MAX_AGE_DAYS = {"fare": 90}
DEFAULT_MAX_AGE_DAYS = 180


def stale(docs, today: date) -> list[str]:
    return [
        f"{d.doc_id}: {d.verified_at} 확인, {(today - d.verified_at).days}일 지남"
        for d in docs
        if (today - d.verified_at).days > MAX_AGE_DAYS.get(d.scope, DEFAULT_MAX_AGE_DAYS)
    ]


def test_no_stale_docs():
    assert stale(load_docs(include_community=True), date.today()) == [], (
        "출처를 다시 열어 확인하고 verified_at 을 고칠 것"
    )


def test_stale_rule():
    docs = load_docs(include_community=True)
    later = date(2027, 2, 1)  # 2026-10-22 확인 기준 약 100일 뒤: 요금 문서만 걸린다
    assert stale(docs, later) and all(s.startswith("doc-fare-") for s in stale(docs, later))
