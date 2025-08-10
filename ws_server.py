# ws_server.py
import asyncio
import json
import signal
import uuid
from typing import Callable, Dict, Optional

import websockets
from websockets.server import WebSocketServerProtocol
from logger import logger

# --- 基础日志 ---
logger.info("WS服务器加载中…………")


class WSServer:
    """
    一个工程化的 WebSocket 服务器封装：
    - start()/stop() 生命周期管理
    - on_connect/on_message/on_disconnect 回调
    - broadcast() & send_to() 发送接口
    - 自动清理断开连接，处理异常
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8888,
        path: str = "/",
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        max_size: int = 2**20,  # 1 MiB
    ):
        self.host = host
        self.port = port
        self.path = path
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.max_size = max_size
        self._stopping = False


        self._server: Optional[websockets.server.Serve] = None
        self._clients: Dict[str, WebSocketServerProtocol] = {}
        self._clients_lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._stop_event = asyncio.Event()

        # 用户回调（可在外部赋值）
        self.on_connect: Optional[Callable[[str, WebSocketServerProtocol], None]] = None
        self.on_message: Optional[Callable[[str, str], None]] = None
        self.on_disconnect: Optional[Callable[[str], None]] = None

    # ---------- 生命周期 ----------
    async def start(self):
        if self._server is not None:
            logger.warning("注意，已经有一个WS服务器启动了")
            return
        # 重置停止事件与标志（很关键）
        self._stop_event = asyncio.Event()
        self._stopping = False

        self._loop = asyncio.get_running_loop()
        logger.info(f"启动WS服务器 {self.host}:{self.port}{self.path}")
        self._server = await websockets.serve(
            ws_handler=self._handler,
            host=self.host,
            port=self.port,
            ping_interval=self.ping_interval,
            ping_timeout=self.ping_timeout,
            max_size=self.max_size,
            process_request=self._process_request,
        )
        logger.info("WS服务器启动成功")

    async def serve_forever(self):
        """
        便捷方法：启动后阻塞直到 stop() 被调用或收到终止信号。
        """
        await self.start()
        try:
            await self._stop_event.wait()
        finally:
            await self.stop()

    async def stop(self):
            # 幂等
            if getattr(self, "_stopping", False):
                return
            self._stopping = True
            try:
                if self._server is None:
                    return

                logger.info("Stopping WebSocket server...")

                # 1) 停止接受新连接
                try:
                    self._server.close()
                    await self._server.wait_closed()
                except Exception as e:
                    logger.debug(f"Server wait_closed error: {e}")
                finally:
                    self._server = None

                # 2) 并发关闭所有现有连接（吞异常）
                async with self._clients_lock:
                    to_close = list(self._clients.items())
                    self._clients.clear()

                async def _close_one(cid, ws):
                    try:
                        await ws.close(code=1001, reason="Server shutdown")
                    except Exception as e:
                        logger.debug(f"Close client {cid} error: {e}")

                if to_close:
                    await asyncio.gather(*(_close_one(cid, ws) for cid, ws in to_close),
                                        return_exceptions=True)

                # 3) 让 windows 的 accept/IOCP 有机会完成取消
                await asyncio.sleep(0)
                await asyncio.sleep(0)  # 多让一拍；避免 pending accept 残留

                # 4) 通知 serve_forever 退出
                if hasattr(self, "_stop_event"):
                    self._stop_event.set()

                logger.info("WebSocket server stopped")
            finally:
                self._stopping = False

    def stop_threadsafe(self):
        """
        从非事件循环线程调用。不要 await 我！
        """
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        def _dispatch():
            asyncio.create_task(self.stop())
        try:
            loop.call_soon_threadsafe(_dispatch)
        except Exception as e:
            logger.debug(f"stop_threadsafe dispatch error: {e}")

    # ---------- 对外 API ----------
    async def broadcast(self, message: str):
        """
        向所有客户端发送文本消息。
        """
        # 复制快照，避免持锁发送
        async with self._clients_lock:
            targets = list(self._clients.items())
        if not targets:
            return
        for cid, ws in targets:
            await self._safe_send(cid, ws, message)

    async def send_to(self, client_id: str, message: str) -> bool:
        """
        向指定客户端发送消息。返回是否成功。
        """
        async with self._clients_lock:
            ws = self._clients.get(client_id)
        if ws is None:
            return False
        return await self._safe_send(client_id, ws, message)

    def get_clients(self) -> Dict[str, str]:
        """
        获取当前连接的快照：client_id -> 'ip:port'
        """
        snap = {}
        for cid, ws in list(self._clients.items()):
            try:
                peer = f"{ws.remote_address[0]}:{ws.remote_address[1]}"
            except Exception:
                peer = "unknown"
            snap[cid] = peer
        return snap

    # ---------- 内部实现 ----------
    async def _process_request(self, path, request_headers):
        # 简单路径过滤（只允许 self.path）
        if self.path and self.path != "/":
            if path != self.path:
                return (403, [], b"Forbidden\n")
        return None  # 继续握手

    async def _handler(self, websocket: WebSocketServerProtocol, path: str):
        # 分配客户端 ID
        client_id = uuid.uuid4().hex[:8]
        async with self._clients_lock:
            self._clients[client_id] = websocket

        # 连接回调
        if self.on_connect:
            try:
                self.on_connect(client_id, websocket)
            except Exception as e:
                logger.exception(f"on_connect error: {e}")

        peer = f"{getattr(websocket, 'remote_address', ['?','?'])[0]}:{getattr(websocket, 'remote_address', ['?','?'])[1]}"
        logger.info(f"[{client_id}] connected from {peer}")

        try:
            async for msg in websocket:
                # 仅处理文本；TD WebSocket DAT 默认发送文本
                if isinstance(msg, str):
                    if self.on_message:
                        try:
                            self.on_message(client_id, msg)
                        except Exception as e:
                            logger.exception(f"on_message error: {e}")
                else:
                    logger.debug(f"[{client_id}] non-text message ignored")
        except websockets.ConnectionClosed as e:
            logger.info(f"[{client_id}] 用户断开链接: 代码={e.code} 理由={e.reason}")
        except Exception as e:
            logger.exception(f"[{client_id}] handler error: {e}")
        finally:
            # 从注册表移除并触发断开回调
            async with self._clients_lock:
                self._clients.pop(client_id, None)
            if self.on_disconnect:
                try:
                    self.on_disconnect(client_id)
                except Exception as e:
                    logger.exception(f"on_disconnect error: {e}")

    async def _safe_send(self, client_id: str, ws: WebSocketServerProtocol, message: str) -> bool:
        try:
            await ws.send(message)
            return True
        except websockets.ConnectionClosed:
            logger.info(f"[{client_id}] send failed: connection closed")
        except Exception as e:
            logger.warning(f"[{client_id}] send error: {e}")
        # 清理失效连接
        async with self._clients_lock:
            self._clients.pop(client_id, None)
        return False


# ---------- 便捷：JSON 编解码 ----------
def to_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def from_json(s: str):
    return json.loads(s)