import json

# 常量定义
ALLOWED_KEYS = {
    "MinStableFrames", "MovingMaxFrames", "UnlockFrames", "SwitchDelta",
    "TriggerRatio", "LR_thresh", "Dis_Min", "Dis_Max"
}
INT_KEYS = {"MinStableFrames", "MovingMaxFrames", "UnlockFrames", "SwitchDelta"}

# 🟢 接收文本消息（JSON）
def onReceiveText(dat, rowIndex, message):
    try:
        data = json.loads(message)
    except Exception as e:
        return sendAck(dat, None, {
            "action": "ack", "request_id": None,
            "status": "error", "message": f"JSON parse error: {e}"
        })

    action = data.get("action")
    rid = data.get("request_id")

    if action == "get_params":
        # 快照当前 constant1 CHOP
        c = op('constant1')
        current = {ch.name: float(ch.eval()) for ch in c.chans()}
        return sendAck(dat, None, {
            "action": "ack", "request_id": rid,
            "status": "ok", "current": current, "message": "snapshot"
        })

    if action != "set_params":
        return sendAck(dat, None, {
            "action": "ack", "request_id": rid,
            "status": "error", "message": f"unsupported action: {action}"
        })

    params = data.get("params", {})
    if not isinstance(params, dict):
        return sendAck(dat, None, {
            "action": "ack", "request_id": rid,
            "status": "error", "message": "params must be object"
        })

    c = op('constant1')
    name_to_idx = {ch.name: i for i, ch in enumerate(c.chans())}

    applied, mismatch, skipped, errors = {}, {}, [], []

    for key, val in params.items():
        if key not in ALLOWED_KEYS or key not in name_to_idx:
            skipped.append(key)
            continue
        try:
            idx = name_to_idx[key]
            par = getattr(c.par, f'value{idx}', None)
            if par is None:
                skipped.append(key)
                continue

            # 类型转换
            val = int(val) if key in INT_KEYS else float(val)
            par.val = val
            cur_val = float(c[key][0])

            # 回读验证
            if key in INT_KEYS:
                if int(round(cur_val)) != int(val):
                    mismatch[key] = {"sent": val, "current": cur_val}
            else:
                if abs(cur_val - val) > 1e-6:
                    mismatch[key] = {"sent": val, "current": cur_val}

            applied[key] = val

        except Exception as e:
            errors.append(f"{key}: {e}")

    status = "ok"
    if errors:
        status = "error"
    elif mismatch or skipped:
        status = "partial"

    msg = f"{len(applied)} applied"
    if mismatch: msg += f", {len(mismatch)} mismatch"
    if skipped:  msg += f", {len(skipped)} skipped"
    if errors:   msg += f", {len(errors)} errors"

    return sendAck(dat, None, {
        "action": "ack", "request_id": rid, "status": status,
        "applied": applied, "mismatch": mismatch,
        "skipped": skipped, "errors": errors,
        "message": msg
    })

# 🟢 应答函数：回发 JSON 消息
def sendAck(dat, peer, payload: dict):
    msg = json.dumps(payload)
    if hasattr(peer, 'sendText'):
        peer.sendText(msg)
    elif hasattr(dat, 'sendText'):
        dat.sendText(msg)
    return

# ✅ 其他函数保持原样占位：
def onConnect(dat): return
def onDisconnect(dat): return
def onReceiveBinary(dat, contents): return
def onReceivePing(dat, contents): dat.sendPong(contents); return
def onReceivePong(dat, contents): return
def onMonitorMessage(dat, message): return