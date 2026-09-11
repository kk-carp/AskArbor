from backend.domain.general_assist import should_general_assist


def test_student_concept_and_practice_can_assist() -> None:
    assert should_general_assist(user_role="student", question="动态规划是什么") is True
    assert should_general_assist(user_role="student", question="这段 traceback 怎么修") is True


def test_student_transactional_isolation_facility_do_not_assist() -> None:
    assert should_general_assist(user_role="student", question="课程作业怎么交") is False
    assert should_general_assist(user_role="student", question="POLICY-CN-2026 是什么？") is False
    assert should_general_assist(user_role="student", question="远程访问内部系统前需要满足什么条件？") is False
    assert should_general_assist(user_role="student", question="火星基地食堂几点开门？") is False


def test_non_student_never_assists() -> None:
    assert should_general_assist(user_role="employee", question="动态规划是什么") is False
    assert should_general_assist(user_role="teaching", question="动态规划是什么") is False
    assert should_general_assist(user_role=None, question="动态规划是什么") is False
