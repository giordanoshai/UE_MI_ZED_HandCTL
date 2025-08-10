# 放在 OSC In DAT 的回调脚本里（Callback DAT）
# 依赖：一个 WebSocket DAT，命名为 ws_client（已连接到你的 Python 服务器）
#      （可选）一个 OSC Out DAT，命名为 osc_out，用于 /ping

import time, json

# 反抖：最多每 5s 向前端上报一次，避免刷屏
HEARTBEAT_REPORT_INTERVAL = 5

def onReceiveOSC(dat, rowIndex, message, byteData, timeStamp, address, args, peer):
    """
    address: 例如 '/ue/heartbeat' 或 '/pong'
    args:    OSC 参数列表
    peer:    (ip, port) 发送方信息
    """
    # 1) 只关心 UE 的心跳地址
    if address in ('/ue/heartbeat', '/pong'):
        # 更新本地最近心跳时间
        parent().store('last_ue_heartbeat', time.time())

        # 节流：避免过于频繁地通过 WS 上报
        last_report = parent().fetch('last_report_ts', 0.0)
        now = time.time()
        if now - last_report >= HEARTBEAT_REPORT_INTERVAL:
            parent().store('last_report_ts', now)
            payload = {
                "type": "ue_heartbeat",
                "ts": now,
                "addr": address,
                "peer": {"ip": peer[0], "port": peer[1]},
                "args": args  # 有需要就带上
            }
            try:
                op('ws_client').sendText(json.dumps(payload))
            except Exception as e:
                debug('WS send failed:', e)

        return

    # 2) 其他业务 OSC，按你原逻辑处理
    # ... your other OSC handling ...
    return
