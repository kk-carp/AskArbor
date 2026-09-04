"""工单页：学员查看自己的单；班主任回复；回复不入库。"""

from __future__ import annotations

import streamlit as st

from api_client import create_ticket, list_tickets, reply_ticket, require_login

st.set_page_config(page_title="工单 · 统一知识助手", layout="centered")
st.title("学员工单")
st.caption("仅学员可建单；处理人默认班主任（advisor_id）；回复不写入知识库。")

user = require_login()
role = user.get("role")
is_teaching = bool(user.get("is_teaching"))
can_manage = bool(user.get("can_manage_documents"))

st.info(
    f"当前用户：`{user.get('username')}`｜角色：`{role}`"
    + (f"｜班主任：`{user.get('advisor_id')}`" if user.get("advisor_id") else "｜未绑定班主任")
)

if role == "student":
    st.subheader("显式转人工")
    question = st.text_area("问题", height=100, placeholder="知识库未覆盖时，可在此提交给班主任")
    if st.button("创建工单", type="primary"):
        text = (question or "").strip()
        if not text:
            st.error("问题不能为空。")
        else:
            try:
                ticket = create_ticket(text)
            except Exception as exc:
                st.error(f"建单失败：{exc}")
            else:
                st.success(f"已建单：`{ticket.get('id')}` → 处理人 `{ticket.get('assignee_id')}`")

st.subheader("工单列表")
if st.button("刷新列表"):
    st.rerun()

try:
    tickets = list_tickets()
except Exception as exc:
    tickets = []
    st.warning(f"无法加载工单：{exc}")

if not tickets:
    st.write("暂无可见工单。")
else:
    for item in tickets:
        with st.expander(
            f"[{item.get('status')}] {str(item.get('question') or '')[:40]} · `{str(item.get('id') or '')[:8]}…`"
        ):
            st.write(f"**问题：** {item.get('question')}")
            st.write(f"**学员：** `{item.get('student_id')}`")
            st.write(f"**处理人：** `{item.get('assignee_id')}`")
            st.write(f"**状态：** `{item.get('status')}`")
            if item.get("reply"):
                st.write(f"**回复：** {item.get('reply')}")
            can_reply = item.get("assignee_id") == user.get("id") or can_manage or is_teaching
            # 仅处理人或教学岗/admin 显示回复框；实际权限由 API 校验
            if can_reply and item.get("status") != "replied":
                reply_text = st.text_area(
                    "回复内容",
                    key=f"reply-{item.get('id')}",
                    height=80,
                )
                if st.button("提交回复", key=f"btn-{item.get('id')}"):
                    text = (reply_text or "").strip()
                    if not text:
                        st.error("回复不能为空。")
                    else:
                        try:
                            updated = reply_ticket(str(item.get("id")), text)
                        except Exception as exc:
                            st.error(f"回复失败：{exc}")
                        else:
                            st.success(f"已回复，状态：`{updated.get('status')}`")
                            st.rerun()
            elif role == "student" and not item.get("reply"):
                st.caption("等待班主任回复。")
