import time
import threading
from pythonosc import dispatcher, osc_server

class HeartbeatManager:
    def __init__(self, td_timeout=3.0, ue_timeout=3.0, ue_osc_port=9002):
        """
        :param td_timeout: TD 超时时间（秒）
        :param ue_timeout: UE 超时时间（秒）
        :param ue_osc_port: 本地 OSC 服务器监听端口（UE 心跳发到这个端口）
        """
        self.td_timeout = td_timeout
        self.ue_timeout = ue_timeout
        self.last_td_ts = 0.0
        self.last_ue_ts = 0.0

        # 启动 OSC Server 接收 UE 心跳
        self._start_osc_server(ue_osc_port)

    # ===== TD 心跳相关 =====
    def bump_td(self):
        """收到任意 TD 消息时调用"""
        self.last_td_ts = time.time()

    def is_td_alive(self):
        """TD 是否在线"""
        return (time.time() - self.last_td_ts) <= self.td_timeout

    # ===== UE 心跳相关（直接OSC接收） =====
    def _ue_heartbeat_handler(self, addr, *args):
        self.last_ue_ts = time.time()
        # 这里可以打调试日志
        # print(f"[UE] Heartbeat {addr} {args}")

    def _start_osc_server(self, port):
        disp = dispatcher.Dispatcher()
        disp.map("/ue/heartbeat", self._ue_heartbeat_handler)

        def _run():
            server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", port), disp)
            # print(f"[Heartbeat] OSC Server listening on 0.0.0.0:{port} for UE heartbeats")
            server.serve_forever()

        t = threading.Thread(target=_run, daemon=True)
        t.start()

    def is_ue_alive(self):
        """UE 是否在线"""
        return (time.time() - self.last_ue_ts) <= self.ue_timeout
