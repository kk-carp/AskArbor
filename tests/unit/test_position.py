from backend.domain.position import (
    boost_retrieval_query,
    is_onboarding_question,
    position_label,
)


def test_position_label_known_and_unknown() -> None:
    assert position_label("algo_engineer") == "算法工程师"
    assert position_label(None) is None
    assert position_label("unknown_role") is None
    assert position_label("  ") is None


def test_is_onboarding_question_markers() -> None:
    assert is_onboarding_question("入职要看哪些资料") is True
    assert is_onboarding_question("新人报到流程") is True
    assert is_onboarding_question("课程作业怎么交") is False


def test_boost_retrieval_query_appends_label_once() -> None:
    q = boost_retrieval_query("入职要看哪些资料", "algo_engineer")
    assert q == "入职要看哪些资料 算法工程师"
    assert boost_retrieval_query(q, "algo_engineer") == q


def test_boost_skips_when_not_onboarding_or_no_label() -> None:
    assert boost_retrieval_query("报销怎么走", "algo_engineer") == "报销怎么走"
    assert boost_retrieval_query("入职要看什么", None) == "入职要看什么"
    assert boost_retrieval_query("入职要看什么", "nope") == "入职要看什么"
