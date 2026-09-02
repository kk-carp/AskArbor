from dataclasses import dataclass

from app.schemas import SourceItem

MISS_ANSWER = "知识库中没有足够依据回答这个问题。"


@dataclass(frozen=True)
class AskResult:
    answer: str
    hit: bool
    sources: list[SourceItem]


def answer_question(role: str, question: str) -> AskResult:
    """Answer from the role's allowed spaces, or refuse without calling DeepSeek.

    Flow: role → allowed spaces → query vector → isolated search → hit check.
    Miss: return MISS_ANSWER, hit=false, empty sources. Hit: generate, then
    build at most 3 deduplicated sources from retrieved records.
    """
    raise NotImplementedError
