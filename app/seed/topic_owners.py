"""演示用主题负责人。清单为样例（需求中第一批主题仍待确认），联系方式非真实人员。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import TopicOwner


@dataclass(frozen=True)
class DemoTopicOwner:
    topic_key: str
    topic_name: str
    keywords: str
    owner_name: str
    contact: str


# 样例主题，仅供本地演示匹配；勿写入真实内部联系方式
DEMO_TOPIC_OWNERS = (
    DemoTopicOwner(
        topic_key="leave",
        topic_name="请假休假",
        keywords="请假,休假,年假,调休,病假",
        owner_name="人力演示",
        contact="hr-demo@example.local",
    ),
    DemoTopicOwner(
        topic_key="reimbursement",
        topic_name="报销",
        keywords="报销,发票,差旅,费用",
        owner_name="财务演示",
        contact="finance-demo@example.local",
    ),
    DemoTopicOwner(
        topic_key="it",
        topic_name="IT支持",
        keywords="VPN,电脑,账号,邮箱打不开",
        owner_name="IT演示",
        contact="it-demo@example.local",
    ),
    DemoTopicOwner(
        topic_key="attendance",
        topic_name="考勤",
        keywords="考勤,打卡,迟到,加班",
        owner_name="行政演示",
        contact="admin-demo@example.local",
    ),
)


def seed_topic_owners(session: Session) -> None:
    """幂等插入缺失的样例主题；已有记录不覆盖，以便管理接口修改能保留。"""
    existing = {
        row.topic_key for row in session.scalars(select(TopicOwner)).all()
    }
    for item in DEMO_TOPIC_OWNERS:
        if item.topic_key in existing:
            continue
        session.add(
            TopicOwner(
                topic_key=item.topic_key,
                topic_name=item.topic_name,
                keywords=item.keywords,
                owner_name=item.owner_name,
                contact=item.contact,
            )
        )
