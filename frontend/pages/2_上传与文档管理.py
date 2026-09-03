"""上传与文档管理页：仅教学岗/管理员可操作。"""

from __future__ import annotations

import streamlit as st

from api_client import list_documents, offline_document, require_login, upload_document

st.set_page_config(page_title="文档管理 · 统一知识助手", layout="centered")
st.title("上传与文档管理")
st.caption("上传、查看状态/失败原因、下线。下线后文档不可检索。")

user = require_login()

if not user.get("can_manage_documents"):
    st.error("当前账号无文档管理权限。请使用 `teaching_demo` 登录。")
    st.stop()

st.subheader("上传文档")
space = st.selectbox("知识空间", options=["student", "company"])
uploaded = st.file_uploader("选择文件", type=["md", "txt", "pdf", "docx"])
if st.button("上传入库", type="primary", disabled=uploaded is None):
    assert uploaded is not None
    try:
        result = upload_document(space, uploaded.name, uploaded.getvalue())
        st.success(
            f"上传成功：{result.get('title')}｜状态 {result.get('status')}｜"
            f"切片 {result.get('chunk_count')}"
        )
        st.session_state["_docs_refresh"] = True
    except Exception as exc:
        st.error(f"上传失败：{exc}")

st.divider()
st.subheader("文档列表")

col1, col2 = st.columns([1, 4])
with col1:
    refresh = st.button("刷新列表")
with col2:
    st.caption("状态含 processing / ready / failed / offline")

if refresh or st.session_state.pop("_docs_refresh", False) or "doc_rows" not in st.session_state:
    try:
        st.session_state.doc_rows = list_documents()
    except Exception as exc:
        st.error(f"加载列表失败：{exc}")
        st.session_state.doc_rows = []

rows = st.session_state.get("doc_rows") or []
if not rows:
    st.info("暂无文档。")
else:
    for doc in rows:
        with st.container(border=True):
            left, right = st.columns([4, 1])
            with left:
                err = doc.get("error") or "-"
                st.markdown(
                    f"**{doc.get('title')}**  \n"
                    f"空间：`{doc.get('space_id')}`｜状态：`{doc.get('status')}`｜"
                    f"切片：{doc.get('chunk_count')}｜错误：{err}"
                )
                st.caption(f"ID：{doc.get('id')}")
            with right:
                if doc.get("status") != "offline":
                    if st.button("下线", key=f"offline-{doc.get('id')}"):
                        try:
                            offline_document(str(doc.get("id")))
                            st.success("已下线。")
                            st.session_state.doc_rows = list_documents()
                            st.rerun()
                        except Exception as exc:
                            st.error(f"下线失败：{exc}")
                else:
                    st.write("已下线")
