# appStart.py
import asyncio
import os
import subprocess
from contextlib import suppress
import inspect

from logger import logger

# Windows 创建标志
CREATE_NO_WINDOW         = 0x08000000
DETACHED_PROCESS         = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

# ===== 内置配置 =====
cfg = {
    "td_player_exe": r"C:\Program Files\Derivative\TouchDesigner\bin\TouchPlayer.exe",
    "td_project_toe": r"td_project\TD_Zed.toe",
    "ue_exe": r"ue_project\LBD_TT_554.exe",
    "ue_args": [
        "-fullscreen",
        "-NoSplash",
        "-NoPause",
        # "-RCWebControlEnable",
        # "-RCWebInterfaceEnable",
    ],
    "td_connect_timeout": 30,   # 等待心跳的总时长（秒）
    "td_ready_timeout": 10,     # 仅用于回退到 get_params() 的调用超时
    "poll_interval": 0.5,       # 轮询间隔（秒）
}

# ===== 进程句柄 =====
proc_td = None
proc_ue = None

def _kill_tree_by_pid(pid: int):
    # /T 杀整棵子进程树，/F 强制
    with suppress(Exception):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )

def _kill_by_image(image_path: str):
    # 兜底：按映像名（不含路径）杀
    imagename = os.path.basename(image_path)
    with suppress(Exception):
        subprocess.run(
            ["taskkill", "/IM", imagename, "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW
        )



# ===== 工具函数 =====
def _spawn(cmd, silent: bool, cwd=None, env=None, preclean: bool = True):
    """
    启动外部进程。
    - silent=True: 极力静默（用于 TD）
    - silent=False: 正常可见（用于 UE）
    """
    try:
        exe_path = cmd[0]
        if preclean and exe_path:
            _kill_by_image(exe_path)
    except Exception:
        pass

    
    if silent:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            startupinfo=si,
        )
    else:
        # 可见启动：不施加隐藏标志，保留独立进程组方便关闭
        return subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env or os.environ.copy(),
            creationflags=CREATE_NEW_PROCESS_GROUP,
        )

# ===== 主启动/停止 =====
# —— 放在文件靠前位置，补上这个小工具（供 stop_app 用）——
def cb(fn, *args):
    if callable(fn):
        try:
            fn(*args)
        except Exception:
            pass

# —— 把 start_app 的签名/注释改清楚，并确保用指定 loop 创建 task ——
def start_app(is_td_alive, loop=None, retries=15, interval=2.0,reset_callback=None):
    """
    异步启动流程入口：
      - is_td_alive: 函数引用（同步或异步），返回 bool
      - loop: 事件循环（如 self.runner.loop）
      - retries: 额外重试次数（不含首次检查）
      - interval: 每次重试间隔（秒）
    """
    if loop is None:
        loop = asyncio.get_event_loop()
    if not loop.is_running():
        raise RuntimeError("传入的 asyncio loop 未运行，请先启动 AsyncRunner 或在已有 loop 上调用。")

    loop.create_task(start_app_async(is_td_alive, retries, interval,reset_callback))

def stop_app(on_stopped=None):
    global proc_td, proc_ue

    # 先杀 UE（常见问题在 UE）
    if proc_ue:
        if proc_ue.poll() is None:
            _kill_tree_by_pid(proc_ue.pid)
        if proc_ue.poll() is None:
            _kill_by_image(cfg["ue_exe"])
    proc_ue = None

    # 再杀 TD
    if proc_td:
        if proc_td.poll() is None:
            _kill_tree_by_pid(proc_td.pid)
        if proc_td.poll() is None:
            _kill_by_image(cfg["td_player_exe"])
    proc_td = None

    # 可选回调
    try:
        if callable(on_stopped):
            on_stopped()
    except Exception:
        pass

async def start_app_async(is_td_alive, retries=15, interval=5.0,reset_callback=None):
    """
    异步版启动流程：
      1) 启动 TD（静默）
      2) 立即检查一次 is_td_alive()，然后重试 `retries` 次；每次间隔 `interval` 秒（await，不阻塞）
      3) 成功则启动 UE（可见），返回 True；失败则 stop_app() 并返回 False
    """
    global proc_td, proc_ue
    try:
        td_exe  = os.path.abspath(cfg["td_player_exe"])
        td_path = os.path.abspath(cfg["td_project_toe"])

        if not os.path.isfile(td_exe):
            logger.error(f"TD Player 不存在: {td_exe}")
            return False
        if not os.path.isfile(td_path):
            logger.error(f"TD 工程不存在: {td_path}")
            return False

        proc_td = _spawn([td_exe, td_path], silent=True)
        logger.info("已启动 TD Player")

        attempts = retries + 1  # 立即一次 + 重试N次
        for i in range(attempts):
            ok = is_td_alive() if callable(is_td_alive) else False
            if inspect.isawaitable(ok):
                ok = await ok

            if ok:
                logger.info("TD 已在线，启动 UE")
                ue_exe = os.path.abspath(cfg["ue_exe"])
                if not os.path.isfile(ue_exe):
                    logger.error(f"UE 可执行文件不存在: {ue_exe}")
                    # stop_app()
                    reset_callback()
                    return False
                proc_ue = _spawn([ue_exe, *cfg["ue_args"]], silent=False)
                return True

            if i < attempts - 1:
                logger.info(f"TD 未就绪，重试 {i+1}/{retries}")
                await asyncio.sleep(interval)

        logger.error("TD 启动失败，未检测到心跳，停止流程")
        # stop_app()
        reset_callback()
        return False

    except Exception as e:
        logger.error(f"启动失败: {e}")
        # stop_app()
        reset_callback()
        return False


def start_ueSettings(url: str=None):
    """启动 Chrome 并打开指定页面"""
    # 常见安装路径（可按需添加）
    url = "http://127.0.0.1:30000/"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    chrome_exe = None
    for path in chrome_paths:
        if os.path.isfile(path):
            chrome_exe = path
            break

    if not chrome_exe:
        raise FileNotFoundError("找不到 Chrome 可执行文件，请检查安装路径。")

    # 启动 Chrome 打开页面
    subprocess.Popen([chrome_exe, url], shell=False)