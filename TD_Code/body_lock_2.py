from collections import deque

# 假设 bodies 和 stored 初始化如前
bodies = ['p1', 'p2', 'p3', 'p4']
# track_counts = {b: 0 for b in bodies}
# move_counts = {b: 0 for b in bodies}
stored = {
    'locked_body': None,
    'lock_counter': 0,
    'move_flags': {b: deque(maxlen=20) for b in bodies},
    'last_moving_frames': 20
}

# onFrameStart 函数重构
# onFrameStart 函数最终优化版
def onFrameStart(frame):
    global stored, bodies

    # --- 阶段 0: 读取参数和状态 ---
    param = op('constant1')
    min_stable_frames = int(param['MinStableFrames'][0])
    moving_max_frames = int(param['MovingMaxFrames'][0])
    unlock_frames     = int(param['UnlockFrames'][0])
    switch_delta      = float(param['SwitchDelta'][0]) # 得分是浮点数，delta也应是
    trigger_ratio     = float(param['TriggerRatio'][0])
    LR_thresh         = float(param['LR_thresh'][0])
    dis_min           = float(param['Dis_Min'][0])
    dis_max           = float(param['Dis_Max'][0])
    
    Dmax = max((LR_thresh**2 + dis_max**2)**0.5, 1e-6)

    if min_stable_frames > moving_max_frames:
        min_stable_frames = moving_max_frames

    if moving_max_frames != stored['last_moving_frames']:
        stored['last_moving_frames'] = moving_max_frames
        stored['move_flags'] = {b: deque(maxlen=moving_max_frames) for b in bodies}

    locked_body  = stored['locked_body']
    lock_counter = stored['lock_counter']
    move_flags   = stored['move_flags']
    
    candidates_info = []
    debug_info = []

    # --- 阶段 1: 收集信息并过滤候选者 ---
    for b in bodies:
        try:
            is_tracked = op('select_sklen_filter')[f'{b}:tracked'][0] == 1
            is_moving  = op('select_sklen_filter')[f'{b}:moving'][0] == 1
            
            move_flags[b].append(1 if not is_tracked or is_moving else 0)
            
            # --- 强大的过滤条件 ---
            if not is_tracked:
                debug_info.append(f"{b}: ❌ 未被跟踪")
                continue

            # 1. 使用 trigger_ratio 过滤掉过于活跃的 body
            # <--- 改进点: 重新引入 trigger_ratio
            moving_frames = sum(move_flags[b])
            current_moving_ratio = moving_frames / len(move_flags[b]) if len(move_flags[b]) > 0 else 0
            if current_moving_ratio > trigger_ratio:
                debug_info.append(f"{b}: ⚠️ 移动过于频繁 ({current_moving_ratio:.2f} > {trigger_ratio})")
                continue

            # 2. 使用 min_stable_frames 作为硬性门槛
            # <--- 改进点: 重新引入 min_stable_frames
            stable_frames = len(move_flags[b]) - moving_frames
            if stable_frames < min_stable_frames:
                debug_info.append(f"{b}: ⚠️ 不够稳定 ({stable_frames} < {min_stable_frames} 帧)")
                continue

            tx = op('select_sklen_filter')[f'{b}/body/pelvis:tx'][0]
            tz = op('select_sklen_filter')[f'{b}/body/pelvis:tz'][0]
            if tx is None or tz is None: continue
            
            if not (abs(tx) < LR_thresh and dis_min < abs(tz) < dis_max):
                debug_info.append(f"{b}: ❌ 超出范围 tx={tx:.2f}, tz={tz:.2f}")
                continue

            # --- 计算得分 (只有通过所有过滤的才计算) ---
            stability_score = (stable_frames / moving_max_frames) * 5
            d = (tx**2 + tz**2)**0.5
            dist_score = max(0, (1 - d / Dmax)) * 3
            lock_bonus = 5 if b == locked_body else 0

            total_score = stability_score + dist_score + lock_bonus
            
            candidates_info.append({'body': b, 'score': total_score})
            debug_info.append(f"{b}: ✔️ 合格. 得分={total_score:.2f}")

        except Exception as e:
            debug_info.append(f"{b}: ⚠️ 异常: {e}")
            if b in move_flags: move_flags[b].append(1)

    # --- 阶段 2: 决策 ---
    candidates_info.sort(key=lambda x: x['score'], reverse=True)
    
    best_candidate = candidates_info[0] if candidates_info else None
    
    # <--- 改进点: 用更简洁的方式获取当前锁定者的分数
    current_score = next((c['score'] for c in candidates_info if c['body'] == locked_body), -1)

    new_locked_body = locked_body
    
    if best_candidate:
        if locked_body is None:
            # 情况A: 之前没有锁定，现在有了最佳候选，直接锁定
            new_locked_body = best_candidate['body']
            lock_counter = 0
            debug_info.append(f"🔒 新锁定 -> {new_locked_body} (得分={best_candidate['score']:.2f})")
        elif best_candidate['body'] != locked_body and best_candidate['score'] > current_score + switch_delta:
            # 情况B: 切换锁定 (新来的分数足够高)
            new_locked_body = best_candidate['body']
            lock_counter = 0
            debug_info.append(f"🔄 切换锁定 -> {new_locked_body} (新分 {best_candidate['score']:.2f} > 旧分 {current_score:.2f} + delta)")
        else:
            # 情况C: 保持锁定 (当前锁定者仍然是最佳或优势不大)
            lock_counter = 0 # 保持锁定时，重置解锁计数器
            debug_info.append(f"✅ 保持锁定: {locked_body} (得分={current_score:.2f})")
    
    # 检查解锁条件: 只有在之前有锁定的情况下才需要检查
    if locked_body is not None and current_score == -1:
        # 情况D: 当前锁定者已不再是有效候选人 (current_score为-1说明没在candidates_info里找到)
        lock_counter += 1
        debug_info.append(f"⚠️ {locked_body} 失效, 解锁计数={lock_counter}/{unlock_frames}")
        if lock_counter > unlock_frames:
            debug_info.append(f"🔓 解锁 {locked_body}: 超时")
            new_locked_body = None
            lock_counter = 0
    elif locked_body is None and not best_candidate:
        # 情况E: 本来就没锁定，现在也没候选
        debug_info.append("- 无有效候选，无锁定 -")


    # --- 阶段 3: 输出与状态保存 ---
    op('body_selector_table')[0, 0] = f'{new_locked_body}*' if new_locked_body else '<None>'
    print("\n".join(debug_info))

    stored['locked_body'] = new_locked_body
    stored['lock_counter'] = lock_counter
    
    return