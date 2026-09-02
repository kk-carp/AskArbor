from dataclasses import dataclass

from app.schemas import SourceItem

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]


def answer_question(role: str, question: str) -> AskResult:
    """在角色允许空间内回答问题，未命中时不调用 DeepSeek。

    流程：角色 → 允许空间 → 问题向量 → 隔离检索 → 命中判断。
    未命中：返回固定拒答、hit=false、sources 为空。
    命中：调用生成模块，并基于召回记录去重后返回最多 3 条来源。
    """
    raise NotImplementedError
