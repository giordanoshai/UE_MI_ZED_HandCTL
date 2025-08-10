# main.py
import asyncio
import threading

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import scrolledtext
from ttkbootstrap.tooltip import ToolTip
from td_client import TDWSManager
from heartbeat import HeartbeatManager
from logger import get_logs
from appStart import start_app,stop_app,start_ueSettings
# from ws_server import WSServer


# ====== 配置区 ======

PARAMS = [
    {"name": "最小稳定帧", "value": 20,"param":"MinStableFrames","tooltip":"至少要保持多少帧才被判为稳定，并锁定"},
    {"name": "最大移动帧", "value": 10,"param":"MovingMaxFrames","tooltip":"最大移动帧数,超过就解锁"},
    {"name": "触发比例", "value": 0.8,"param":"TriggerRatio","tooltip":"最大移动帧数触发比例，例如最大移动10*0.9就会触发不稳定"},
    {"name": "解锁帧数", "value": 15,"param":"UnlockFrames","tooltip":"解锁帧数，超过就解锁"},
    {"name": "切换增量", "value": 3,"param":"SwitchDelta","tooltip":"多个BODY分数切换，两者之间大于这个值就切换"},
    {"name": "左右阈值", "value": 0.15,"param":"LR_thresh","tooltip":"站定区域，左右阈值"},
    {"name": "最小距离", "value": 0.5,"param":"Dis_Min","tooltip":"站定区域，前后最小距离"},
    {"name": "最大距离", "value": 1.5,"param":"Dis_Max","tooltip":"站定区域，前后最大距离"}
]



# ====== 通信客户端（UI 侧）======

UE_STATUS = "离线"
TD_STATUS = "离线"


class AsyncRunner:
    def __init__(self):
        self.loop = None
        self.thread = None
        self._started = threading.Event()

    def start(self):
        def run():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._started.set()
            self.loop.run_forever()
        self.thread = threading.Thread(target=run, daemon=True)
        self.thread.start()
        self._started.wait(2.0)

    def submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)


# ====== UI 组件与样式 ======

class ControlPanelApp:
    def __init__(self, root):
        self.root = root
        self.root.title("控制面板")
        self.root.geometry("1000x1200")
        self.style = tb.Style("darkly")
        self.param_entries = {}
        self.param_vars = {}
        self.running = False
        self.build_ui()

        self.hb = HeartbeatManager(td_timeout=10.0, ue_timeout=10.0, ue_osc_port=9002)
        self.runner = AsyncRunner()
        self.runner.start()
        self.td = TDWSManager(hb=self.hb, body_callback=self.body_message_callback)
        fut = self.runner.submit(self.td.start())
        try:
            fut.result(timeout=5.0)
            self.log_panel.insert("end", "[WS] 服务器已启动\n")
        except Exception as e:
            self.log_panel.insert("end", f"[ERR] WS服务器启动失败: {e}\n")

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.start_log_polling()
        self._status_tick()
    


    def build_ui(self):
        main_frame = tb.Frame(self.root,padding=10)
        main_frame.pack(fill=BOTH, expand=True)

        top_frame = tb.Frame(main_frame)
        top_frame.pack(fill=X, expand=False)

        # 左侧参数输入区
        param_frame = tb.Labelframe(top_frame, text="参数控制",padding=20)
        param_frame.pack(side=LEFT, fill=BOTH, expand=True,padx=5)

        vcmd_int = (self.root.register(self._numeric_validator(is_float=False)), "%P")
        vcmd_float = (self.root.register(self._numeric_validator(is_float=True)), "%P")

        for i, p in enumerate(PARAMS):
            tb.Label(param_frame, text=p["name"]).grid(row=i, column=0, sticky=W, pady=10)

            v = p["value"]
            if isinstance(v, int):
                var = tb.IntVar(value=v);    vcmd = vcmd_int
            elif isinstance(v, float):
                var = tb.DoubleVar(value=v); vcmd = vcmd_float
            else:
                var = tb.StringVar(value=str(v)); vcmd = None

            entry = tb.Entry(
                param_frame, width=20, textvariable=var,
                validate="key" if vcmd else "none",
                validatecommand=vcmd if vcmd else None,
            )
            entry.grid(row=i, column=1, pady=10, padx=10)

            tip = p.get("tooltip")
            if tip:
                ToolTip(entry, text=tip, delay=300)

            self.param_entries[p["name"]] = entry
            self.param_vars[p["param"]] = var

        # 右侧状态卡片列
        status_frame = tb.Labelframe(top_frame,padding=20,text="状态")
        status_frame.pack(side=RIGHT, fill=BOTH, expand=True,padx=5)

        # 卡片1：UE/TD状态
        status_card_1 = tb.Labelframe(status_frame, text="系统状态", padding=5)
        status_card_1.pack(fill=X, expand=False, pady=5)
        self.ue_label = tb.Label(status_card_1, text=f"UE_STATUS: {UE_STATUS}", bootstyle=SUCCESS if UE_STATUS=="正常" else WARNING)
        self.ue_label.pack(fill=X, pady=5)
        self.td_label = tb.Label(status_card_1, text=f"TD_STATUS: {TD_STATUS}", bootstyle=SUCCESS if TD_STATUS=="正常" else WARNING)
        self.td_label.pack(fill=X, pady=5)

        # 卡片2：绑定状态
        status_card_2 = tb.Labelframe(status_frame, text="绑定状态", padding=10)
        status_card_2.pack(fill=X, expand=False, pady=5)

        self.binding_labels = []
        for i in range(4):
            label = tb.Label(status_card_2, text=f"对象{i+1}：NONE", anchor="w")
            label.pack(fill=X, pady=10)
            self.binding_labels.append(label)

        # 卡片3：ZED CAMERA 视频区（模拟宽高比）
        # status_card_3 = tb.Labelframe(status_frame, text="ZED CAMERA", padding=10)
        # status_card_3.pack(fill=X, expand=False, pady=5)
        # canvas = tb.Canvas(status_card_3, bg="black", width=400, height=250)
        # canvas.pack()

        # 按钮区
        btn_frame = tb.Frame(status_frame)
        btn_frame.pack(pady=10)
        self.btn_get = tb.Button(btn_frame, text="获取参数", command=self.get_params,padding=(20, 10))
        self.btn_get.pack(side=LEFT, padx=10,pady=10)
        self.btn_set = tb.Button(btn_frame, text="设置参数", command=self.set_params,padding=(20, 10))
        self.btn_set.pack(side=LEFT, padx=10,pady=10)
        self.btn_ueSet = tb.Button(btn_frame,text="UE参数",command=start_ueSettings,padding=(20, 10))
        self.btn_ueSet.pack(side=LEFT,padx=10,pady=10)
        self.btn_start = tb.Button(btn_frame, text="启动", command=self.toggle_start,bootstyle=SUCCESS,padding=(20, 10))
        self.btn_start.pack(side=LEFT, padx=10,pady=10)

        self.btn_get.config(state="disabled")
        self.btn_set.config(state="disabled")
        self.btn_ueSet.config(state="disable")

        # 日志区
        log_frame = tb.Labelframe(main_frame, text="日志", padding=10,height=200)
        log_frame.pack(fill=BOTH, expand=True, pady=10, ipady=150)
        self.log_panel = scrolledtext.ScrolledText(log_frame, wrap="word", height=20)
        self.log_panel.pack(fill=BOTH, expand=True)

#启动停止..................................
    def toggle_start(self):
        if not self.running:
            # 启动状态
            self.running = True
            self.btn_get.config(state="normal")
            self.btn_set.config(state="normal")
            self.btn_ueSet.config(state="normal")
            self.btn_start.config(text="停止", bootstyle=DANGER)
            start_app(self.hb.is_td_alive,self.runner.loop,reset_callback=self.reset_state)
            self.get_params()
        else:
            # 停止状态
            self.running = False
            self.btn_get.config(state="disabled")
            self.btn_set.config(state="disabled")
            self.btn_ueSet.config(state="disabled")
            self.btn_start.config(text="启动", bootstyle=SUCCESS)
            stop_app() 

    def reset_state(self):
        self.running = False
        self.btn_get.config(state="disabled")
        self.btn_set.config(state="disabled")
        self.btn_ueSet.config(state="disabled")
        self.btn_start.config(text="启动", bootstyle=SUCCESS)
        stop_app() 

#启动停止..................................

    def body_message_callback(self, items):
        for i, label in enumerate(self.binding_labels):
            if i < len(items):
                item = items[i]
                state = "YES" if item.get("locked") else "NO"
                score = f"{item.get('score', 0):.2f}"
                label.config(text=f"BODY{i+1}：{item.get('id')} / 锁定：{state} / 分数：{score}")
            else:
                label.config(text=f"BODY{i+1}：NONE")

    def get_params(self):
        self.log_panel.insert("end", "[INFO] 正在获取参数...\n")
        self.log_panel.see("end")

        # 如果 AsyncRunner.submit 期望协程对象（从你 set_params 可用来看，这里 OK）
        fut = self.runner.submit(self.td.get_params(timeout=5))

        def done(fut):
            def ui():
                try:
                    resp = fut.result()  # 你说后端已有超时/异步，这里也可以保留或删除
                    # self.log_panel.insert("end", f"[GET] {resp}\n")
                    cur = (resp or {}).get("params", {}) or {}
                    # ✅ 用 param_vars（英文key）来回填 textvariable
                    for k, v in cur.items():
                        if k in self.param_vars:
                            if isinstance(v,float):
                                v = round(v, 2)  # 保留2位小数
                            try:
                                self.param_vars[k].set(v)
                            except Exception:
                                self.param_vars[k].set(str(v))

                except Exception as e:
                    self.log_panel.insert("end", f"[ERR][GET] {e}\n")
                self.log_panel.see("end")
            self.root.after(0, ui)
        fut.add_done_callback(done)

    def set_params(self):
        params = {}
        for name, entry in self.param_vars.items():
            try:
                params[name] = float(entry.get())
            except ValueError:
                self.log_panel.insert("end", f"[ERR] {name} 请输入数值\n")
        self.log_panel.see("end")
        fut = self.runner.submit(self.td.set_params(params, timeout=5))
        def done(fut):
            def ui():
                try:
                    resp = fut.result()
                    # self.log_panel.insert("end", f"[SET] {resp}\n")
                except Exception as e:
                    self.log_panel.insert("end", f"[ERR][SET] {e}\n")
                self.log_panel.see("end")
            self.root.after(0, ui)
        fut.add_done_callback(done)

    def on_close(self):
        # 停止 WS 服务器（线程安全）
        self.td.stop()
        
        # 销毁窗口
        self.root.destroy()


    def start_log_polling(self):
        self.last_log_len = 0
        self.poll_logs()

    def poll_logs(self):
        logs = get_logs()
        # 只追加新日志，提高性能
        if hasattr(self, 'last_log_len'):
            new_logs = logs[self.last_log_len:]
        else:
            new_logs = logs
        if new_logs:
            for line in new_logs:
                self.log_panel.insert("end", line + "\n")
            self.log_panel.see("end")
        self.last_log_len = len(logs)
        self.root.after(500, self.poll_logs)  # 每0.5秒刷新

    def _numeric_validator(self, is_float=True):
        def _fn(P):
            if P in ("", "-", "."):
                return True
            try:
                float(P) if is_float else int(P)
                return True
            except ValueError:
                return False
        return _fn
    
    def _status_tick(self):
        td_ok = self.hb.is_td_alive()
        ue_ok = self.hb.is_ue_alive()

        self._set_td_status("正常" if td_ok else "离线")
        self._set_ue_status("正常" if ue_ok else "离线")

        self.root.after(500, self._status_tick)

    def _set_td_status(self, text):
        boot = "success" if text == "正常" else "danger"
        self.td_label.configure(text=f"TD_STATUS: {text}", bootstyle=boot)

    def _set_ue_status(self, text):
        boot = "success" if text == "正常" else "danger"
        self.ue_label.configure(text=f"UE_STATUS: {text}", bootstyle=boot)


if __name__ == "__main__":
    root = tb.Window(themename="flatly")
    app = ControlPanelApp(root)
    root.mainloop()