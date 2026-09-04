from uuid import uuid4

from backend.infra import retrieve


def test_search_chunks_builds_space_filtered_sql_and_maps_result(monkeypatch) -> None:
    captured: dict[str, object] = {}
    doc_id = uuid4()

    class _Result:
        def mappings(self):
            return [
                {
                    "content": "课程作业请通过平台提交",
                    "score": 0.88,
                    "document_id": str(doc_id),
                    "title": "课程说明.md",
                    "space_id": "student",
                }
            ]

    class _Session:
        def execute(self, statement, params):
            captured["sql"] = str(statement)
            captured["params"] = params
            return _Result()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(retrieve.db, "init_engine", lambda: None)
    monkeypatch.setattr(retrieve.db, "SessionLocal", lambda: _Session())

    rows = retrieve.search_chunks([0.1, 0.2], ["student"], 5)

    assert len(rows) == 1
    assert rows[0].document_id == doc_id
    assert rows[0].space_id == "student"
    assert "WHERE chunks.space_id = ANY" in captured["sql"]
    assert "documents.status = 'ready'" in captured["sql"]
    assert captured["params"]["allowed_spaces"] == "{student}"
    assert captured["params"]["top_k"] == 5


def test_search_chunks_returns_empty_when_no_allowed_space(monkeypatch) -> None:
    monkeypatch.setattr(retrieve.db, "init_engine", lambda: None)
    assert retrieve.search_chunks([0.1, 0.2], [], 5) == []
