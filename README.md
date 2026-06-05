# UE_MI_ZED_HandCTL

一个用 Python 开发的控制面板，用于协调 **TouchDesigner (TD)**、**Unreal Engine (UE)** 和 **ZED 摄像头**的集成系统。该项目提供了一个图形化界面来管理参数、监控系统状态和控制应用生命周期。

## 🎯 功能特性

- **多应用集成** - 同时启动和管理 TouchDesigner 和 Unreal Engine
- **实时参数控制** - 通过 UI 获取和设置 TD 参数
- **心跳监控** - 实时检测 TD/UE 在线状态，支持 OSC 心跳协议
- **WebSocket 通信** - TD 与 Python 通过 WebSocket 实时通信
- **系统绑定状态** - 显示 BODY 识别和锁定状态
- **日志记录** - 完整的日志系统，支持文件归档

## 📋 系统要求

- **Python** >= 3.8
- **Windows** 系统（应用启动逻辑针对 Windows 优化）
- **TouchDesigner** - 推荐最新版本
- **Unreal Engine** - 5.0 或更高版本
- **Chrome** - 用于 UE 参数设置页面

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/giordanoshai/UE_MI_ZED_HandCTL.git
cd UE_MI_ZED_HandCTL
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置路径

编辑 `appStart.py`，更新以下路径为您的系统路径：

```python
cfg = {
    "td_player_exe": r"C:\Program Files\Derivative\TouchDesigner\bin\TouchPlayer.exe",
    "td_project_toe": r"td_project\TD_Zed.toe",
    "ue_exe": r"ue_project\LBD_TT_554.exe",
    "ue_args": ["-fullscreen", "-NoSplash", "-NoPause"],
    "td_connect_timeout": 30,
    "td_ready_timeout": 10,
    "poll_interval": 0.5,
}
```

### 4. 运行应用

```bash
python hand_main.py
```

## 📖 使用指南

### 控制面板界面

#### 参数控制区
- **最小稳定帧** - 判断稳定所需的最少帧数
- **最大移动帧** - 超过此值时解锁
- **触发比例** - 移动触发阈值（0-1）
- **解锁帧数** - 解锁所需帧数
- **切换增量** - BODY 分数切换阈值
- **左右阈值** - 站定区域左右范围
- **最小/最大距离** - 站定区域前后范围

#### 控制按钮
- **获取参数** - 从 TD 读取当前参数值
- **设置参数** - 将本地参数同步到 TD
- **UE参数** - 打开浏览器进入 UE 参数设置页面
- **启动/停止** - 启动或停止整个系统

#### 状态指示器
- **系统状态** - 显示 TD 和 UE 的在线状态（绿色=正常，红色=离线）
- **绑定状态** - 显示 4 个 BODY 的识别情况和锁定状态

### 工作流程

1. 确保 TouchDesigner 项目已准备好
2. 点击「启动」按钮，系统将：n   - 启动 TouchDesigner Player
   - 等待 TD 心跳连接（最多 30 秒）
   - 启动 Unreal Engine
3. 使用参数控制区调整参数
4. 监控日志区的实时输出
5. 点击「停止」关闭所有应用

## 🏗️ 项目结构

```
UE_MI_ZED_HandCTL/
├── hand_main.py          # 主 UI 应用入口
├── appStart.py           # 应用启动/停止逻辑
├── td_client.py          # TouchDesigner WebSocket 客户端
├── ws_server.py          # WebSocket 服务器实现
├── heartbeat.py          # 心跳监控管理器
├── logger.py             # 日志系统
├── README.md             # 项目文档
├── requirements.txt      # Python 依赖
├── LICENSE               # MIT 许可证
├── .gitignore            # Git 忽略列表
└── td_project/           # TouchDesigner 项目目录
    └── TD_Zed.toe        # TD 工程文件
└── ue_project/           # UE 项目输出目录
    └── LBD_TT_554.exe    # UE 可执行文件
```

## 🔧 核心模块说明

### `hand_main.py` - UI 主程序
- 基于 `ttkbootstrap` 的 GUI 应用
- 参数输入验证（支持整数和浮点数）
- 异步任务管理（`AsyncRunner`）
- 实时日志显示和轮询更新

### `td_client.py` - TD 通信管理
- 通过 WebSocket 与 TD 通信
- 支持参数获取和设置
- 自动请求 ID 追踪
- 接收 BODY 状态和调试信息

### `ws_server.py` - WebSocket 服务器
- 异步 WebSocket 服务器实现
- 支持多客户端连接
- 自动心跳（ping/pong）
- 安全的连接管理

### `heartbeat.py` - 心跳监控
- TD 消息触发心跳
- UE 通过 OSC 协议发送心跳
- 可配置的超时时间
- 在线/离线状态检测

### `logger.py` - 日志系统
- 内存日志收集
- 控制台输出
- 文件归档（rotating handler）
- 实时日志查询接口

## 📡 通信协议

### WebSocket 消息格式

**获取参数请求：**
```json
{
  "action": "get_params",
  "request_id": "uuid-string"
}
```

**设置参数请求：**
```json
{
  "action": "set_params",
  "request_id": "uuid-string",
  "params": {
    "MinStableFrames": 20,
    "MovingMaxFrames": 10,
    "TriggerRatio": 0.8
  }
}
```

**参数响应：**
```json
{
  "status": "ok",
  "request_id": "uuid-string",
  "current": {
    "MinStableFrames": 20,
    "MovingMaxFrames": 10
  }
}
```

**BODY 状态消息：**
```json
{
  "topic": "body_status",
  "items": [
    {"id": "body_001", "locked": true, "score": 0.95},
    {"id": "body_002", "locked": false, "score": 0.75}
  ]
}
```

### OSC 心跳
- **地址** - `/ue/heartbeat`
- **端口** - `9002`（可配置）
- **格式** - 任意数据，定期发送即可

## 🔐 安全性说明

- 所有敏感配置（路径、端口）都应在本地 `appStart.py` 中配置
- WebSocket 服务器默认绑定 `127.0.0.1`，仅允许本地连接
- 日志文件自动归档，不包含敏感信息
- 建议在受信网络环境中使用

## 🐛 故障排查

### TD 连接超时
- 检查 TouchDesigner 项目是否正确配置 WebSocket 服务器
- 确保 WebSocket 连接到 `127.0.0.1:9989`
- 查看日志中的详细错误信息

### UE 启动失败
- 验证 UE 可执行文件路径是否正确
- 检查系统磁盘空间是否充足
- 查看是否有权限访问 UE 项目文件

### 参数同步失败
- 确保 TD 和 Python 都在运行
- 检查 WebSocket 连接状态
- 验证参数名称是否正确

## 📦 依赖项

详见 `requirements.txt`：
- `ttkbootstrap` - 现代化 Tkinter 主题
- `websockets` - WebSocket 异步库
- `python-osc` - OSC 协议支持

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

### 开发工作流
1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/AmazingFeature`
3. 提交更改：`git commit -m 'Add some AmazingFeature'`
4. 推送分支：`git push origin feature/AmazingFeature`
5. 提交 Pull Request

## 📝 更新日志

### v1.0.0 (2025-08-10)
- 初始版本发布
- 支持 TD/UE 应用管理
- 实现参数控制界面
- 集成心跳监控系统

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 👨‍💻 作者

**giordanoshai** - [GitHub Profile](https://github.com/giordanoshai)

## 💬 联系方式

如有问题或建议，请提交 [GitHub Issues](https://github.com/giordanoshai/UE_MI_ZED_HandCTL/issues)

## 🙏 致谢

感谢以下开源项目的支持：
- [ttkbootstrap](https://github.com/israel-dryer/ttkbootstrap)
- [websockets](https://github.com/aaugustin/websockets)
- [python-osc](https://github.com/attwad/python-osc)

---

**祝您使用愉快！** 🚀
