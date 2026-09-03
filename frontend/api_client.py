"""Streamlit 侧调用 FastAPI 的 HTTP 客户端（服务端带 Cookie，不依赖浏览器跨域）。"""

from __future__ import annotations

from typing import Any

import httpx
import streamlit as st

DEFAULT_API_BASE = "http://127.0.0.1:8000"


def get_api_base() -> str:
    return str(st.session_state.get("api_base") or DEFAULT_API_BASE).rstrip("/")


def get_client() -> httpx.Client:
    """复用同一 Client，以便登录后的 Session Cookie 在各页面共享。

    trust_env=False：忽略系统 HTTP_PROXY，避免本地 127.0.0.1 被代理成虚假 502。
    """
    base = get_api_base()
    client: httpx.Client | None = st.session_state.get("http_client")
    cached_base = st.session_state.get("http_client_base")
    # 版本号用于强制重建旧 Client（例如此前误走系统代理）
    client_version = 2
    if (
        client is None
        or cached_base != base
        or st.session_state.get("http_client_v") != client_version
    ):
        if client is not None:
            client.close()
        client = httpx.Client(base_url=base, timeout=120.0, trust_env=False)
        st.session_state.http_client = client
        st.session_state.http_client_base = base
        st.session_state.http_client_v = client_version
    return client


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text or f"HTTP {response.status_code}"
    if isinstance(payload, dict) and "detail" in payload:
        detail = payload["detail"]
        if isinstance(detail, str):
            return detail
        return str(detail)
    return str(payload)


def login(username: str, password: str) -> dict[str, Any]:
    response = get_client().post("/login", json={"username": username, "password": password})
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    data = response.json()
    st.session_state.user = data
    return data


def logout() -> None:
    try:
        get_client().post("/logout")
    finally:
        st.session_state.user = None


def fetch_me() -> dict[str, Any] | None:
    response = get_client().get("/me")
    if response.status_code == 401:
        st.session_state.user = None
        return None
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    data = response.json()
    st.session_state.user = data
    return data


def require_login() -> dict[str, Any]:
    user = st.session_state.get("user")
    if user:
        return user
    me = fetch_me()
    if me is None:
        st.warning("请先登录。")
        st.switch_page("pages/1_登录.py")
        st.stop()
    return me


def list_documents() -> list[dict[str, Any]]:
    response = get_client().get("/documents")
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    return response.json()


def upload_document(space: str, filename: str, content: bytes) -> dict[str, Any]:
    files = {"file": (filename, content)}
    data = {"space": space}
    response = get_client().post("/documents", data=data, files=files)
    if response.status_code not in (200, 201):
        raise RuntimeError(_detail(response))
    return response.json()


def offline_document(document_id: str) -> dict[str, Any]:
    response = get_client().post(f"/documents/{document_id}/offline")
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    return response.json()


def ask_question(question: str, conversation_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"question": question}
    if conversation_id:
        payload["conversation_id"] = conversation_id
    response = get_client().post("/ask", json=payload)
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    return response.json()


def list_conversations() -> list[dict[str, Any]]:
    response = get_client().get("/conversations")
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    return response.json()


def list_messages(conversation_id: str) -> list[dict[str, Any]]:
    response = get_client().get(f"/conversations/{conversation_id}/messages")
    if response.status_code != 200:
        raise RuntimeError(_detail(response))
    return response.json()
