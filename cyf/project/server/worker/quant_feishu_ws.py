#!/usr/bin/env python3
"""飞书 WebSocket 长连接客户端。

在独立的后台线程中与飞书服务端维持 WebSocket 长连接，
替代 HTTP 回调模式，接收 im.message.receive_v1 等事件。

启动方式：
    from worker.quant_feishu_ws import start_feishu_ws_client
    start_feishu_ws_client()
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Optional

logger = logging.getLogger("quant.feishu_ws")

_FEISHU_WS_THREAD: Optional[threading.Thread] = None
_FEISHU_WS_STOP_FLAG = threading.Event()


def _get_shared_event_handler():
    """获取全局唯一的 EventDispatcherHandler（由 im_service 统一管理）。"""
    from service.quant.im_service import get_feishu_event_handler
    handler = get_feishu_event_handler()
    if handler is None:
        raise RuntimeError("EventDispatcherHandler 未初始化（缺少飞书配置）")
    return handler


def _build_ws_client(event_handler) -> Optional["lark_oapi.ws.Client"]:
    """构建飞书 WebSocket 客户端。"""
    from conf.settings import settings
    from lark_oapi import LogLevel
    from lark_oapi.ws import Client as WsClient

    app_id = (settings.quant_feishu_app_id or "").strip()
    app_secret = (settings.quant_feishu_app_secret or "").strip()
    if not app_id or not app_secret:
        logger.error("[feishu-ws] 飞书 app_id/app_secret 未配置，无法启动 WebSocket 客户端")
        return None

    client = WsClient(
        app_id=app_id,
        app_secret=app_secret,
        log_level=LogLevel.INFO,
        event_handler=event_handler,
        auto_reconnect=True,
        source="quant-ws",
    )
    logger.info(
        "[feishu-ws] WebSocket 客户端已创建 | app_id=%s*** | auto_reconnect=True",
        app_id[:8] if len(app_id) > 8 else "***",
    )
    return client


def _run_ws_loop():
    """在独立线程中运行 asyncio 事件循环，维持 WebSocket 长连接。"""
    from conf.settings import settings

    event_handler = _get_shared_event_handler()
    client = _build_ws_client(event_handler)
    if client is None:
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # SDK 内部持有一个模块级 loop 引用，需替换为当前线程的 loop
    import lark_oapi.ws.client as _ws_client_module
    _ws_client_module.loop = loop

    logger.info("[feishu-ws] 开始建立 WebSocket 长连接...")
    try:
        client.start()
    except Exception as exc:
        logger.exception("[feishu-ws] WebSocket 连接异常退出 | error=%s", exc)
    except KeyboardInterrupt:
        logger.info("[feishu-ws] 收到中断信号，正在关闭...")
    finally:
        logger.info("[feishu-ws] WebSocket 客户端已停止")
        loop.close()
        logger.info("[feishu-ws] 事件循环已关闭")


def start_feishu_ws_client() -> bool:
    """启动飞书 WebSocket 客户端（后台 daemon 线程）。

    Returns:
        True: 启动成功
        False: 已运行或配置缺失
    """
    global _FEISHU_WS_THREAD

    if _FEISHU_WS_THREAD is not None and _FEISHU_WS_THREAD.is_alive():
        logger.warning("[feishu-ws] WebSocket 客户端已在运行中，跳过重复启动")
        return False

    from conf.settings import settings

    app_id = (settings.quant_feishu_app_id or "").strip()
    app_secret = (settings.quant_feishu_app_secret or "").strip()
    if not app_id or not app_secret:
        logger.info("[feishu-ws] 飞书 app_id/app_secret 未配置，跳过 WebSocket 启动")
        return False

    _FEISHU_WS_THREAD = threading.Thread(
        target=_run_ws_loop,
        name="feishu-ws-client",
        daemon=True,
    )
    _FEISHU_WS_THREAD.start()
    logger.info("[feishu-ws] WebSocket 客户端线程已启动 | thread=%s", _FEISHU_WS_THREAD.name)
    return True


def stop_feishu_ws_client():
    """停止飞书 WebSocket 客户端。"""
    global _FEISHU_WS_THREAD
    _FEISHU_WS_STOP_FLAG.set()
    if _FEISHU_WS_THREAD is not None and _FEISHU_WS_THREAD.is_alive():
        logger.info("[feishu-ws] 正在等待 WebSocket 客户端线程退出...")
        _FEISHU_WS_THREAD.join(timeout=10)
        logger.info("[feishu-ws] WebSocket 客户端线程已退出")
    _FEISHU_WS_THREAD = None
