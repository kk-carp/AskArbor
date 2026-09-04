"""问答页：同一会话追问；消息不入库为知识库文档。"""

from __future__ import annotations

import streamlit as st

from api_client import ask_question, list_conversations, list_messages, require_login

st.set_page_config(page_title="问答 · 统一知识助手", layout="centered")
st.title("问答")
st.caption(
    "客户端不得指定 space_ids；未命中返回固定拒答且不调用 DeepSeek。"
    "同一会话可追问；对话不进入向量索引。"
    "员工未命中时展示主题负责人（来自配置表，非模型生成）。"
)

user = require_login()
spaces = ", ".join(user.get("allowed_spaces") or []) or "无"
st.info(f"当前用户：`{user.get('username')}`｜可检索空间：{spaces}")

if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = None

if st.button("开启新会话"):
    st.session_state.conversation_id = None
    st.rerun()

NEW_CONVERSATION = "__new__"

try:
    conversations = list_conversations()
except Exception as exc:
    conversations = []
    st.warning(f"无法加载会话列表：{exc}")

if conversations:
    id_to_label = {
        item["id"]: (
            f"{item['id'][:8]}… · {item.get('message_count', 0)} 条 · "
            f"{str(item.get('updated_at') or '')[:19]}"
        )
        for item in conversations
    }
    option_ids = [NEW_CONVERSATION] + [item["id"] for item in conversations]

    def _format(cid: str) -> str:
        if cid == NEW_CONVERSATION:
            return "（当前新会话 / 未选择历史）"
        return id_to_label.get(cid, cid)

    current = st.session_state.conversation_id or NEW_CONVERSATION
    try:
        default_index = option_ids.index(current)
    except ValueError:
        default_index = 0

    chosen = st.selectbox(
        "历史会话",
        options=option_ids,
        index=default_index,
        format_func=_format,
    )
    resolved = None if chosen == NEW_CONVERSATION else chosen
    if resolved != st.session_state.conversation_id:
        st.session_state.conversation_id = resolved
        st.rerun()

conversation_id = st.session_state.conversation_id
if conversation_id:
    st.caption(f"当前会话：`{conversation_id}`")
    try:
        history = list_messages(conversation_id)
    except Exception as exc:
        history = []
        st.warning(f"无法加载消息：{exc}")
    for item in history:
        role = "user" if item.get("role") == "user" else "assistant"
        with st.chat_message(role):
            st.write(item.get("content") or "")
    meta = st.session_state.get("last_miss_meta") or {}
    if meta.get("conversation_id") == conversation_id and meta.get("hit") is False:
        ticket_id = meta.get("ticket_id")
        if ticket_id:
            st.info(f"已自动创建学员工单：`{ticket_id}`（可在「工单」页查看）")
        owner = meta.get("owner")
        if owner is not None:
            if owner.get("configured"):
                st.info(
                    f"主题负责人：{owner.get('name')}（{owner.get('topic_name')}）｜"
                    f"联系方式：{owner.get('contact')}"
                )
            else:
                st.info("该问题未配置主题负责人。")
else:
    st.caption("当前为新会话；首次提问后会返回并保存 conversation_id。")

question = st.text_area("问题", height=120, placeholder="例如：课程作业提交截止时间是什么时候？")
ask = st.button("提问", type="primary")

if ask:
    text = (question or "").strip()
    if not text:
        st.error("问题不能为空。")
    else:
        with st.spinner("检索与作答中…"):
            try:
                result = ask_question(text, conversation_id=st.session_state.conversation_id)
            except Exception as exc:
                st.error(f"提问失败：{exc}")
            else:
                new_cid = result.get("conversation_id")
                if new_cid:
                    st.session_state.conversation_id = new_cid
                hit = bool(result.get("hit"))
                st.session_state.last_miss_meta = {
                    "conversation_id": new_cid,
                    "hit": hit,
                    "ticket_id": result.get("ticket_id"),
                    "owner": result.get("owner"),
                }
                if hit:
                    st.success("命中知识库")
                else:
                    st.warning("未命中知识库（已拒答）")
                    ticket_id = result.get("ticket_id")
                    if ticket_id:
                        st.info(f"已自动创建学员工单：`{ticket_id}`（可在「工单」页查看）")
                    owner = result.get("owner")
                    if owner is not None:
                        if owner.get("configured"):
                            st.info(
                                f"主题负责人：{owner.get('name')}（{owner.get('topic_name')}）｜"
                                f"联系方式：{owner.get('contact')}"
                            )
                        else:
                            st.info("该问题未配置主题负责人。")
                st.subheader("答案")
                st.write(result.get("answer") or "")
                st.subheader("来源")
                sources = result.get("sources") or []
                if not sources:
                    st.write("无来源")
                else:
                    for source in sources:
                        st.markdown(
                            f"- **{source.get('title')}**（`{source.get('space_id')}`）"
                            f" · `{source.get('document_id')}`"
                        )
                st.caption(f"conversation_id：`{st.session_state.conversation_id}`")
                st.rerun()
