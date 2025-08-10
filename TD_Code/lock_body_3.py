# ======= Module 级变量初始化 =======
#新老结合的版本，老版本剔除逻辑+新的计分系统

bodies = ['p1','p2','p3','p4']
track_counts = {b: 0 for b in bodies}   # 连续“稳定(Tracked 且 mv==0)”的帧数
move_counts  = {b: 0 for b in bodies}   # 连续“移动(mv==1)”的帧数

MIN_STABLE_FRAMES   = 20    # 稳定帧门槛（仍用于强过滤）
MOVING_MAX_FRAMES   = 10    # 稳定/移动分母与移动阈值
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
    # 距离归一化（极小值保护）
    Dmax = max((LR_thresh**2 + dis_max**2)**0.5, 1e-6)

    candidates = []
    debug_info = []

    # —— 收集候选并打分 ——
    for b in bodies:
        try:
            tr = op('select_sklen_filter')[f'{b}:tracked'][0]
            mv = op('select_sklen_filter')[f'{b}:moving'][0]
            tx = op('select_sklen_filter')[f'{b}/body/pelvis:tx'][0]
            tz = op('select_sklen_filter')[f'{b}/body/pelvis:tz'][0]

            # 先做空值/零值检查，避免 abs(None)
            if tx is None or tz is None or tx == 0 or tz == 0:
                debug_info.append(f"{b}: ❌ Invalid position tx={tx}, tz={tz}")
                continue

            is_in_zone = (abs(tx) < LR_thresh) and (dis_min < abs(tz) < dis_max)

            # 更新稳定/移动计数
            if tr and mv == 0:
                track_counts[b] = min(track_counts[b] + 1, MOVING_MAX_FRAMES)
            else:
                track_counts[b] = 0

            if mv == 1:
                move_counts[b] = min(move_counts[b] + 1, MOVING_MAX_FRAMES)
            else:
                move_counts[b] = 0

            # —— 强过滤（保留老版稳感）——
            if not tr:
                debug_info.append(f"{b}: ❌ Not tracked")
                continue

            # 连续多帧移动则排除（非锁定者会被排除，锁定者稍后以罚分体现）
            if b != locked_body and move_counts[b] >= MOVING_MAX_FRAMES:
                debug_info.append(f"{b}: ⚠️ Moving for {move_counts[b]} frames, skip")
                continue

            if not is_in_zone:
                debug_info.append(f"{b}: ❌ Out of range tx={tx:.2f}, tz={tz:.2f}")
                continue

            # —— 计分机制（新）——
            # 稳定度分：固定分母，抗抖（0~5分）
            stable_frames = track_counts[b]
            stability_score = (stable_frames / float(MOVING_MAX_FRAMES)) * 5.0

            # 距离分：中心更高（0~3分）
            d = (tx**2 + tz**2)**0.5
            dist_score = max(0.0, (1.0 - d / Dmax)) * 3.0

            # 锁定奖励：粘性（+5）
            lock_bonus = 5.0 if b == locked_body else 0.0

            # 移动罚分（仅锁定者）：允许轻微移动但小扣分（最多 -2）
            move_penalty = 0.0
            if b == locked_body and mv == 1:
                move_penalty = -min(2.0, 0.5 + 1.5 * (move_counts[b] / float(MOVING_MAX_FRAMES)))

            # 额外：若你仍想保留“达到 MIN_STABLE_FRAMES 再给一点奖励”，可以加：
            bonus_after_gate = 0.0
            if track_counts[b] >= MIN_STABLE_FRAMES:
                bonus_after_gate = 0.5  # 比原来的 +2 温和很多

            score = stability_score + dist_score + lock_bonus + move_penalty + bonus_after_gate

            candidates.append((b, score))
            debug_info.append(
                f"{b}: score={score:.2f} "
                f"[stable={stable_frames}, movingCnt={move_counts[b]}, dist={d:.2f}, locked={b==locked_body}, pen={move_penalty:.1f}]"
            )

        except Exception as e:
            debug_info.append(f"{b}: ⚠️ Exception: {e}")

    # —— 排序并选出最佳候选 —— 
    candidates.sort(key=lambda x: -x[1])  # 高分优先
    best_body, best_score = (candidates[0] if candidates else (None, -1))
    # 当前锁定者的分数
    current_score = next((s for bb, s in candidates if bb == locked_body), -1)

    # —— 锁定/切换逻辑（保留老版迟滞风格）—— 
    if best_body:
        if locked_body is None or best_score > current_score + SWITCH_DELTA:
            locked_body = best_body
            lock_counter = 0
            debug_info.append(f"🔒 New lock: {locked_body} (score={best_score:.2f})")
        else:
            debug_info.append(f"✅ Keep lock: {locked_body} (score={current_score:.2f})")
    else:
        debug_info.append("⚠️ No valid candidates")

    # —— 解锁检测（保留老版体验）—— 
    if locked_body:
        tr = op('select_sklen_filter')[f'{locked_body}:tracked'][0]
        mv = op('select_sklen_filter')[f'{locked_body}:moving'][0]

        # 锁定者连续“移动到阈值” -> 立即解锁（允许轻微动，不会立刻掉）
        if move_counts[locked_body] >= MOVING_MAX_FRAMES:
            debug_info.append(f"🔓 Unlock {locked_body}: moved {move_counts[locked_body]} frames")
            locked_body = None
            lock_counter = 0

        # 普通失稳计时（掉跟踪 或 当前帧在动）
        elif not tr or mv == 1:
            lock_counter += 1
            debug_info.append(f"⚠️ {locked_body} unstable, lock_counter={lock_counter}")
            if lock_counter >= UNLOCK_FRAMES:  # 用 >= 更直观
                debug_info.append(f"🔓 Unlock {locked_body}: timeout")
                locked_body = None
                lock_counter = 0
        else:
            lock_counter = 0

    # —— 输出 & 调试日志 —— 
    op('body_selector_table')[0,0] = f'{locked_body}*' if locked_body else '<invalid>'
    print("\n".join(debug_info))
