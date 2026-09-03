"""统一知识助手 · Streamlit 前端入口。"""

from __future__ import annotations

import streamlit as st

from api_client import DEFAULT_API_BASE, fetch_me

st.set_page_config(
    page_title="统一知识助手",
    page_icon="📚",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("统一知识助手")
st.caption("登录后按空间成员隔离检索；可检索空间由服务端计算，前端不决定权限。")

# 允许覆盖后端地址，便于本机联调
api_base = st.sidebar.text_input("API 地址", value=st.session_state.get("api_base", DEFAULT_API_BASE))
st.session_state.api_base = api_base.rstrip("/")

user = st.session_state.get("user")
if user is None:
    try:
        user = fetch_me()
    except Exception as exc:
        st.sidebar.warning(f"无法连接 API：{exc}")

if user:
    spaces = ", ".join(user.get("allowed_spaces") or []) or "无"
    manage = "可管理文档" if user.get("can_manage_documents") else "不可管理文档"
    st.success(
        f"已登录：{user.get('username')}（{user.get('role')}）｜空间：{spaces}｜{manage}"
    )
    st.markdown(
        """
请从左侧进入页面：

1. **登录** — 切换账号或退出  
2. **上传与文档管理** — 教学岗上传 / 列表 / 下线  
3. **问答** — 按当前账号允许空间提问  
"""
    )
else:
    st.info("当前未登录。请打开左侧「登录」页，使用演示账号进入。")
    st.markdown(
        """
演示账号（密码见 `.env` 的 `DEMO_PASSWORD`，默认 `demo1234`）：

| 用户名 | 说明 |
| --- | --- |
| `student_demo` | 学员，仅 student 空间 |
| `employee_demo` | 员工，仅 company 空间 |
| `teaching_demo` | 教学岗，两空间 + 文档管理 |
"""
    )
