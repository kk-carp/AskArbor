"""主题负责人：员工未命中时展示；仅教学岗可配置。联系方式不经模型生成。"""

from __future__ import annotations

import streamlit as st

from api_client import list_topic_owners, require_login, upsert_topic_owner

st.set_page_config(page_title="主题负责人 · 统一知识助手", layout="centered")
st.title("主题负责人")
st.caption("配置内部主题关键词与联系方式。员工问答未命中时按关键词匹配；未匹配则显示未配置。")

user = require_login()
if not user.get("can_manage_documents"):
    st.error("当前账号无主题负责人管理权限。请使用 `teaching_demo` 登录。")
    st.stop()

st.subheader("新增 / 更新")
with st.form("upsert_owner"):
    topic_key = st.text_input("主题 key", placeholder="leave")
    topic_name = st.text_input("主题名称", placeholder="请假休假")
    keywords = st.text_input("关键词（逗号分隔）", placeholder="请假,休假,年假")
    name = st.text_input("负责人姓名", placeholder="人力演示")
    contact = st.text_input("联系方式", placeholder="hr-demo@example.local")
    submitted = st.form_submit_button("保存", type="primary")

if submitted:
    if not topic_key.strip() or not topic_name.strip() or not name.strip() or not contact.strip():
        st.error("主题 key、名称、姓名和联系方式不能为空。")
    else:
        try:
            saved = upsert_topic_owner(
                topic_key.strip(),
                topic_name.strip(),
                keywords.strip(),
                name.strip(),
                contact.strip(),
            )
            st.success(f"已保存：`{saved.get('topic_key')}` → {saved.get('name')}")
            st.session_state["_owners_refresh"] = True
        except Exception as exc:
            st.error(f"保存失败：{exc}")

st.divider()
st.subheader("当前配置")
if st.button("刷新列表") or st.session_state.pop("_owners_refresh", False) or "owner_rows" not in st.session_state:
    try:
        st.session_state.owner_rows = list_topic_owners()
    except Exception as exc:
        st.error(f"加载失败：{exc}")
        st.session_state.owner_rows = []

rows = st.session_state.get("owner_rows") or []
if not rows:
    st.info("暂无主题负责人。启动时会写入请假/报销/IT/考勤样例（非真实联系方式）。")
else:
    for item in rows:
        st.markdown(
            f"**{item.get('topic_name')}**（`{item.get('topic_key')}`）  \n"
            f"关键词：{item.get('keywords') or '-'}  \n"
            f"负责人：{item.get('name')}｜联系方式：{item.get('contact')}"
        )
