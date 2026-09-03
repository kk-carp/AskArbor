from types import SimpleNamespace

from app.seed.demo_users import bind_demo_student_advisor


def test_bind_demo_student_advisor_sets_advisor_id() -> None:
    teaching = SimpleNamespace(id="id-teaching")
    student = SimpleNamespace(id="id-student", advisor_id=None)
    returns = [teaching, student]

    class FakeSession:
        def scalar(self, _query):
            return returns.pop(0)

    bind_demo_student_advisor(FakeSession())  # type: ignore[arg-type]
    assert student.advisor_id == teaching.id
