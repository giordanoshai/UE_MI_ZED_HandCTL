# ======= Module 级变量初始化 =======

#比较老的版本，有点小BUG

bodies = ['p1','p2','p3','p4']
track_counts = {b: 0 for b in bodies}
move_counts  = {b: 0 for b in bodies}

MIN_STABLE_FRAMES   = 20    # 稳定帧门槛
MOVING_MAX_FRAMES   = 10    # 连续多少帧 moving==1 就排除
UNLOCK_FRAMES       = 45    # 失稳多少帧才解锁
SWITCH_DELTA        = 1     # 切换锁定所需比分差

locked_body = None
lock_counter = 0


def onFrameStart(frame):
    global track_counts, move_counts, locked_body, lock_counter

    # 读取参数
    LR_thresh = op('constant1')['LR_thresh'][0]
    dis_min   = op('constant1')['Dis_Min'][0]
    dis_max   = op('constant1')['Dis_Max'][0]
    # 用于距离归一化
    Dmax = (LR_thresh**2 + dis_max**2)**0.5

    candidates = []
    debug_info = []

    # —— 收集候选并打分 —— 
    for b in bodies:
        try:
            tr = op('select_sklen_filter')[f'{b}:tracked'][0]
            mv = op('select_sklen_filter')[f'{b}:moving'][0]
            tx = op('select_sklen_filter')[f'{b}/body/pelvis:tx'][0]
            tz = op('select_sklen_filter')[f'{b}/body/pelvis:tz'][0]
            is_in_zone = abs(tx) < LR_thresh and dis_min < abs(tz) < dis_max
            # 更新稳定帧计数
            if tr and mv == 0:
                track_counts[b] = min(track_counts[b] + 1, MIN_STABLE_FRAMES)
            else:
                track_counts[b] = 0

            # 更新连续移动帧计数
            if mv == 1:
                move_counts[b] = min(move_counts[b] + 1, MOVING_MAX_FRAMES)
            else:
                move_counts[b] = 0

            # —— 强过滤 —— 
            if not tr:
                debug_info.append(f"{b}: ❌ Not tracked")
                continue

            # 连续多帧移动则排除
            if move_counts[b] >= MOVING_MAX_FRAMES:
                debug_info.append(f"{b}: ⚠️ Moving for {move_counts[b]} frames, skip")
                continue

            if tx is None or tz is None or tx == 0 or tz == 0:
                debug_info.append(f"{b}: ❌ Invalid position tx={tx}, tz={tz}")
                continue

            if not is_in_zone:
                debug_info.append(f"{b}: ❌ Out of range tx={tx:.2f}, tz={tz:.2f}")
                continue

            # —— 计算得分 —— 
            # 稳定加分、锁定加分、距离归一化加分
            score = 0
            if track_counts[b] >= MIN_STABLE_FRAMES:
                score += 2
            if b == locked_body:
                score += 5
            d = (tx**2 + tz**2)**0.5
            dist_score = max(0, (1 - d / Dmax)) * 3
            score += dist_score

            candidates.append((b, score))
            debug_info.append(
                f"{b}: score={score:.2f} "
                f"[stable={track_counts[b]}, movingCnt={move_counts[b]}, dist={d:.2f}, locked={b==locked_body}]"
            )

        except Exception as e:
            debug_info.append(f"{b}: ⚠️ Exception: {e}")

    # —— 排序并选出最佳候选 —— 
    candidates.sort(key=lambda x: -x[1])  # 高分优先
    best_body, best_score = (candidates[0] if candidates else (None, -1))
    # 当前锁定者的分数
    current_score = next((s for b, s in candidates if b == locked_body), -1)

    # —— 锁定/切换逻辑 —— 
    if best_body:
        if locked_body is None or best_score > current_score + SWITCH_DELTA:
            locked_body = best_body
            lock_counter = 0
            debug_info.append(f"🔒 New lock: {locked_body} (score={best_score:.2f})")
        else:
            debug_info.append(f"✅ Keep lock: {locked_body} (score={current_score:.2f})")
    else:
        debug_info.append("⚠️ No valid candidates")

    # —— 解锁检测 —— 
    if locked_body:
        tr = op('select_sklen_filter')[f'{locked_body}:tracked'][0]
        mv = op('select_sklen_filter')[f'{locked_body}:moving'][0]

        # 锁定者连续移动到达阈值，强制解锁
        if move_counts[locked_body] >= MOVING_MAX_FRAMES:
            debug_info.append(f"🔓 Unlock {locked_body}: moved {move_counts[locked_body]} frames")
            locked_body = None
            lock_counter = 0

        # 普通失稳解锁
        elif not tr or mv == 1:
            lock_counter += 1
            debug_info.append(f"⚠️ {locked_body} unstable, lock_counter={lock_counter}")
            if lock_counter > UNLOCK_FRAMES:
                debug_info.append(f"🔓 Unlock {locked_body}: timeout")
                locked_body = None
                lock_counter = 0
        else:
            lock_counter = 0

    # —— 输出 & 调试日志 —— 
    op('body_selector_table')[0,0] = f'{locked_body}*' if locked_body else '<invalid>'
    print("\n".join(debug_info))
