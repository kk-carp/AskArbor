from uuid import uuid4

from backend.infra import retrieve
from backend.infra.retrieve import RetrievedChunk


def test_search_dense_builds_space_filtered_sql_and_maps_result(monkeypatch) -> None:
    captured: dict[str, object] = {}
    doc_id = uuid4()
    chunk_id = uuid4()

    class _Result:
        def mappings(self):
            return [
                {
                    "chunk_id": str(chunk_id),
                    "content": "课程作业请通过平台提交",
                    "score": 0.88,
                    "document_id": str(doc_id),
                    "title": "课程说明.md",
                    "space_id": "student",
                    "path": "labs/sort.py",
                    "language": "python",
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

    rows = retrieve.search_dense([0.1, 0.2], ["student"], 5)

    assert len(rows) == 1
    assert rows[0].document_id == doc_id
    assert rows[0].chunk_id == chunk_id
    assert rows[0].space_id == "student"
    assert rows[0].path == "labs/sort.py"
    assert rows[0].language == "python"
    assert rows[0].dense_score == 0.88
    assert "WHERE chunks.space_id = ANY" in captured["sql"]
    assert "documents.status = 'ready'" in captured["sql"]
    assert "chunks.path AS path" in captured["sql"]
    assert captured["params"]["allowed_spaces"] == "{student}"
    assert captured["params"]["top_k"] == 5


def test_search_chunks_returns_empty_when_no_allowed_space(monkeypatch) -> None:
    monkeypatch.setattr(retrieve.db, "init_engine", lambda: None)
    assert retrieve.search_chunks([0.1, 0.2], [], 5) == []


def test_search_lexical_builds_tsv_sql(monkeypatch) -> None:
    captured: dict[str, object] = {}
    doc_id = uuid4()

    class _Result:
        def mappings(self):
            return [
                {
                    "chunk_id": str(uuid4()),
                    "content": "课程作业",
                    "score": 0.12,
                    "document_id": str(doc_id),
                    "title": "说明.md",
                    "space_id": "student",
                    "path": None,
                    "language": None,
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
    monkeypatch.setattr(retrieve, "to_search_text", lambda _t: "课程 作业")

    rows = retrieve.search_lexical("课程作业", ["student"], 10)

    assert len(rows) == 1
    assert "content_tsv @@ query" in captured["sql"]
    assert "documents.status = 'ready'" in captured["sql"]
    assert captured["params"]["search_text"] == "课程 作业"


def test_fuse_rrf_prefers_shared_hits() -> None:
    a = uuid4()
    b = uuid4()
    c = uuid4()
    dense = [
        RetrievedChunk("a", 0.9, uuid4(), "t", "student", chunk_id=a, dense_score=0.9),
        RetrievedChunk("b", 0.8, uuid4(), "t", "student", chunk_id=b, dense_score=0.8),
    ]
    lexical = [
        RetrievedChunk("b", 0.5, uuid4(), "t", "student", chunk_id=b),
        RetrievedChunk("c", 0.4, uuid4(), "t", "student", chunk_id=c),
    ]
    fused = retrieve.fuse_rrf([dense, lexical], rrf_k=60)
    assert [item.chunk_id for item in fused][0] == b
    assert fused[0].dense_score == 0.8


def test_run_retrieval_dense_only_gates_on_min_score(monkeypatch) -> None:
    monkeypatch.setattr(retrieve.settings, "retrieve_use_hybrid", False)
    monkeypatch.setattr(retrieve.settings, "retrieve_use_rerank", False)
    monkeypatch.setattr(retrieve.settings, "retrieve_min_score", 0.8)
    monkeypatch.setattr(retrieve.settings, "retrieve_top_k", 5)
    monkeypatch.setattr(
        retrieve,
        "hybrid_search",
        lambda **_k: [
            RetrievedChunk(
                content="x",
                score=0.7,
                document_id=uuid4(),
                title="t",
                space_id="student",
                dense_score=0.7,
            )
        ],
    )
    assert retrieve.run_retrieval("q", [0.1], ["student"]) == []


def test_run_retrieval_rerank_gates_on_rerank_min_score(monkeypatch) -> None:
    monkeypatch.setattr(retrieve.settings, "retrieve_use_hybrid", True)
    monkeypatch.setattr(retrieve.settings, "retrieve_use_rerank", True)
    monkeypatch.setattr(retrieve.settings, "rerank_min_score", 0.5)
    monkeypatch.setattr(retrieve.settings, "rerank_candidates", 20)
    monkeypatch.setattr(retrieve.settings, "retrieve_top_k", 5)
    monkeypatch.setattr(
        retrieve,
        "hybrid_search",
        lambda **_k: [
            RetrievedChunk(
                content="x",
                score=0.1,
                document_id=uuid4(),
                title="t",
                space_id="student",
                dense_score=0.9,
            )
        ],
    )

    def _rerank(query, chunks, top_k):
        return [RetrievedChunk(c.content, 0.2, c.document_id, c.title, c.space_id) for c in chunks][
            :top_k
        ]

    monkeypatch.setattr("backend.infra.rerank.rerank", _rerank)
    assert retrieve.run_retrieval("q", [0.1], ["student"]) == []
