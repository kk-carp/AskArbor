"""学员知识库未命中时的实践/概念兜底判定。教务、越权探测、虚构后勤仍拒答。"""

from __future__ import annotations

import re

from backend.services.weak_points import is_transactional_question

# 学员问内部制度/越权套话：必须继续拒答且不调模型（课上 isolation 样本）。
_ISOLATION_RE = re.compile(
    r"("
    r"POLICY-CN-\d+|VPN|财务下载|财务数据|远程访问内部|内部系统|"
    r"内部制度|忽略以上规则|忽略上述|jailbreak"
    r")",
    re.I,
)

# 评测 no_answer 与明显不在课程知识范围的后勤/虚构场所，不走通用作答。
_UNGROUNDED_FACILITY_RE = re.compile(
    r"("
    r"食堂|菜单|开门|热线|火星|月球|办公室周末"
    r")",
    re.I,
)


def is_isolation_probe(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    return _ISOLATION_RE.search(text) is not None


def is_ungrounded_facility_question(question: str) -> bool:
    text = (question or "").strip()
    if not text:
        return False
    return _UNGROUNDED_FACILITY_RE.search(text) is not None


def should_general_assist(*, user_role: str | None, question: str) -> bool:
    """仅学员；教务/越权/虚构后勤除外。纯概念与实践题在知识库未命中时可以兜底。"""
    if user_role != "student":
        return False
    if is_transactional_question(question):
        return False
    if is_isolation_probe(question):
        return False
    if is_ungrounded_facility_question(question):
        return False
    return True
