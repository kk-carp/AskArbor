"""集中管理课外搜索工具注册。"""

from __future__ import annotations

import logging

from backend.infra.open_resource.sources import (
    list_search_tools,
    reset_default_search_tools,
)

_logger = logging.getLogger(__name__)


def init_open_resource_search_tools() -> None:
    """应用启动时初始化默认搜索工具注册表。"""
    reset_default_search_tools()
    names = ",".join(tool.name for tool in list_search_tools())
    _logger.info("open-resource tools initialized: %s", names)
