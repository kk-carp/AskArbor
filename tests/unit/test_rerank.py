from uuid import uuid4

from backend.infra.retrieve import RetrievedChunk
from backend.infra import rerank as rerank_mod


def test_rerank_orders_by_score(monkeypatch) -> None:
    chunks = [
        RetrievedChunk("a", 0.1, uuid4(), "t1", "student"),
        RetrievedChunk("b", 0.1, uuid4(), "t2", "student"),
    ]

    class _Model:
        def predict(self, pairs):
            assert len(pairs) == 2
            return [0.2, 0.9]

    monkeypatch.setattr(rerank_mod, "_reranker", _Model())
    out = rerank_mod.rerank("问题", chunks, top_k=1)
    assert len(out) == 1
    assert out[0].content == "b"
    assert out[0].score == 0.9


def test_rerank_empty_inputs(monkeypatch) -> None:
    monkeypatch.setattr(rerank_mod, "_reranker", object())
    assert rerank_mod.rerank("q", [], 5) == []
    assert rerank_mod.rerank("", [RetrievedChunk("a", 1.0, uuid4(), "t", "s")], 5) == []
