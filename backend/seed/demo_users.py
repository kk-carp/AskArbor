from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.domain.membership import expected_spaces
from backend.models import SpaceMember, User
from backend.services.auth_service import hash_password

DEMO_STUDENT_USERNAME = "student_demo"
DEMO_EMPLOYEE_USERNAME = "employee_demo"
DEMO_TEACHING_USERNAME = "teaching_demo"


@dataclass(frozen=True)
class DemoAccount:
    username: str
    role: str
    is_teaching: bool


DEMO_ACCOUNTS = (
    DemoAccount(username=DEMO_STUDENT_USERNAME, role="student", is_teaching=False),
    DemoAccount(username=DEMO_EMPLOYEE_USERNAME, role="employee", is_teaching=False),
    DemoAccount(username=DEMO_TEACHING_USERNAME, role="employee", is_teaching=True),
)


def bind_demo_student_advisor(session: Session) -> None:
    """将 student_demo 的班主任绑定到 teaching_demo。"""
    teaching = session.scalar(select(User).where(User.username == DEMO_TEACHING_USERNAME))
    student = session.scalar(select(User).where(User.username == DEMO_STUDENT_USERNAME))
    if teaching is not None and student is not None:
        student.advisor_id = teaching.id


def seed_demo_users(session: Session) -> None:
    """幂等写入三个演示账号及其空间成员关系，并为学员绑定班主任。"""
    password_hash = hash_password(settings.demo_password)
    for account in DEMO_ACCOUNTS:
        user = session.scalar(select(User).where(User.username == account.username))
        if user is None:
            user = User(
                username=account.username,
                password_hash=password_hash,
                role=account.role,
                is_teaching=account.is_teaching,
            )
            session.add(user)
            session.flush()
        else:
            user.password_hash = password_hash
            user.role = account.role
            user.is_teaching = account.is_teaching

        # 成员关系只由服务端写入；问答不得信任客户端 role
        desired_spaces = set(expected_spaces(role=account.role, is_teaching=account.is_teaching))
        existing_spaces = set(
            session.scalars(select(SpaceMember.space_id).where(SpaceMember.user_id == user.id)).all()
        )
        for space_id in desired_spaces - existing_spaces:
            session.add(SpaceMember(user_id=user.id, space_id=space_id))
        for space_id in existing_spaces - desired_spaces:
            member = session.get(SpaceMember, (user.id, space_id))
            if member is not None:
                session.delete(member)

    bind_demo_student_advisor(session)
