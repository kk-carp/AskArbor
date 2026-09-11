from backend.domain.followup import expand_followup_query, is_followup_question, last_user_question
from backend.services.conversation_service import HistoryMessage


def test_last_user_question_takes_nearest_user_turn() -> None:
    history = [
        HistoryMessage(role="user", content="课程作业怎么交"),
        HistoryMessage(role="assistant", content="在平台提交。"),
        ("user", "格式要求"),
        ("assistant", "按模板。"),
    ]
    assert last_user_question(history) == "格式要求"
    assert last_user_question([]) is None
    assert last_user_question(None) is None


def test_expand_followup_query_prepends_previous_on_short_or_marked_ask() -> None:
    previous = "课程作业怎么交"
    assert expand_followup_query("那截止日期呢", previous) == "课程作业怎么交 那截止日期呢"
    assert expand_followup_query("截止日期呢", previous) == "课程作业怎么交 截止日期呢"
    assert expand_followup_query("具体流程", previous) == "课程作业怎么交 具体流程"


def test_expand_followup_query_skips_complete_question_and_missing_history() -> None:
    previous = "入职要看哪些资料"
    assert expand_followup_query("课程作业怎么交", previous) == "课程作业怎么交"
    assert expand_followup_query("差旅报销标准是什么", previous) == "差旅报销标准是什么"
    assert expand_followup_query("那截止日期呢", None) == "那截止日期呢"
    assert expand_followup_query("那截止日期呢", "") == "那截止日期呢"


def test_expand_followup_query_skips_when_current_already_contains_previous() -> None:
    previous = "课程作业怎么交"
    current = "课程作业怎么交的截止日期呢"
    assert expand_followup_query(current, previous) == current
    assert is_followup_question(current, previous) is False
