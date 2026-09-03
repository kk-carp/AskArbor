"""登录页：账号密码登录 / 退出。"""

from __future__ import annotations

import streamlit as st

from api_client import fetch_me, login, logout

st.set_page_config(page_title="登录 · 统一知识助手", layout="centered")
st.title("登录")
st.caption("Session Cookie 由后端签发；可检索空间只来自 space_members。")

try:
    current = st.session_state.get("user") or fetch_me()
except Exception as exc:
    st.error(f"连接后端失败：{exc}")
    current = None

if current:
    st.info(
        f"当前用户：`{current.get('username')}`｜角色：`{current.get('role')}`｜"
        f"教学岗：{current.get('is_teaching')}｜"
        f"空间：{', '.join(current.get('allowed_spaces') or []) or '无'}"
    )
    if st.button("退出登录", type="secondary"):
        logout()
        st.success("已退出。")
        st.rerun()
else:
    st.write("尚未登录。")

st.divider()

with st.form("login_form"):
    username = st.text_input("用户名", placeholder="teaching_demo")
    password = st.text_input("密码", type="password", placeholder="demo1234")
    submitted = st.form_submit_button("登录", type="primary")

if submitted:
    if not username.strip() or not password:
        st.error("请输入用户名和密码。")
    else:
        try:
            user = login(username.strip(), password)
            st.success(f"登录成功：{user.get('username')}")
            st.rerun()
        except Exception as exc:
            st.error(f"登录失败：{exc}")

st.markdown(
    """
**演示账号**

- `student_demo`：学员  
- `employee_demo`：内部员工  
- `teaching_demo`：教学岗（可上传/下线文档）  
"""
)
