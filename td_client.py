import asyncio
import json
import uuid
from ws_server import WSServer
from logger import logger

class TDWSManager:
    def __init__(self, host="127.0.0.1", port=9989,hb=None,body_callback=None):
        self.server = WSServer(host=host, port=port,path='/td')
        self._last_response = {} # {request_id: response_json}
        self.server.on_message = self.on_td_message
        self.hb = hb
        self.body_message_callback = body_callback

    async def start(self):
        await self.server.start()

    def stop(self):
        self.server.stop_threadsafe()

    def get_clients(self):
        """返回TD客户端快照（client_id -> ip:port）"""
        return self.server.get_clients()

    # def get_logs(self):
    #     """获取日志列表"""
    #     return list(self._logs)


    def on_debug_message(self, message):
        # 允许传 str 或 dict，都兜住
        if not isinstance(message, dict):
            try:
                message = json.loads(message)
            except Exception:
                return

        text = None
        # 标准形态：{"topic":"DEBUG","lines":"..."}
        if message.get("topic") == "DEBUG":
            text = message.get("lines", "")
        # 兼容你贴的这种：{"DEBUG": "..."} 也支持
        elif "DEBUG" in message and isinstance(message["DEBUG"], str):
            text = message["DEBUG"]

        if text:
            logger.info(f"\n{text}")   # 只传字符串，\n 就会是实际换行

        

    def on_body_message(self, message):
        #body信息,需要回调
        if isinstance(message, dict) and message.get("topic") == "body_status":
            self.body_message_callback(message.get("items", []))
        else:
            return

    def get_last_response(self, request_id):
        return self._last_response.get(request_id)

    # def clear_logs(self):
    #     self._logs.clear()

    def on_td_message(self, client_id, message):
        """TD返回消息的回调，自动存日志、存最后一次响应"""
        try:
            data = json.loads(message)
        except Exception:
            data = message
        self.hb.bump_td()
        # logger.info({"from": client_id, "message": data})
        # 自动记录回包，供set/get等方法等待
        self.on_body_message(data)
        self.on_debug_message(data)
        if isinstance(data, dict) and "request_id" in data:
            self._last_response[data["request_id"]] = data

    async def wait_client(self, timeout=30):
        """等待TD客户端上线"""
        for _ in range(int(timeout * 10)):
            clients = self.get_clients()
            if clients:
                logger.info(f'{clients}:已连接')
                return next(iter(clients.keys()))
            await asyncio.sleep(0.1)
        raise TimeoutError("TD客户端未连接")

    async def set_params(self, params: dict, request_id=None, timeout=3):
        """设置TD的constant1参数 —— 返回一个瘦身后的ACK结果"""
        client_id = await self.wait_client()
        request_id = request_id or str(uuid.uuid4())
        msg = {"action": "set_params", "request_id": request_id, "params": params}
        await self.server.send_to(client_id, json.dumps(msg, ensure_ascii=False))

        for _ in range(int(timeout * 10)):
            raw = self.get_last_response(request_id)
            if raw:
                logger.info(f"TD返回结果:{raw.get('current') or {}}")
                # ---- 规范化/瘦身返回 ----
                ok = (raw.get("status") == "ok")
                # 有些TD会把当前值也回给你；没有就给空
                current = raw.get("current") or {}
                # 只返回这三个键，前端更好用
                return {"ok": ok, "params": current, "rid": request_id}
            await asyncio.sleep(0.1)
        raise TimeoutError("等待TD ACK超时")

    async def get_params(self, request_id=None, timeout=3):
        """获取TD的constant1所有参数 —— 返回一个瘦身后的snapshot"""
        client_id = await self.wait_client()
        request_id = request_id or str(uuid.uuid4())
        msg = {"action": "get_params", "request_id": request_id}
        await self.server.send_to(client_id, json.dumps(msg, ensure_ascii=False))

        for _ in range(int(timeout * 10)):
            raw = self.get_last_response(request_id)
            if raw:
                logger.info(f"TD返回结果:{raw.get('current') or {}}")
                # ---- 规范化/瘦身返回 ----
                ok = (raw.get("status") == "ok")
                current = raw.get("current") or {}
                return {"ok": ok, "params": current, "rid": request_id}
            await asyncio.sleep(0.1)
        raise TimeoutError("等待TD snapshot超时")
