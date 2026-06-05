# 贡献指南

感谢您对 UE_MI_ZED_HandCTL 项目的关注！我们欢迎各种形式的贡献。

## 📋 行为准则

请遵循我们的行为准则以维护友好的社区环境。任何形式的骚扰、歧视或不尊重的行为都是不被接受的。

## 🐛 报告问题

### 提交 Issue 前
- 检查是否已存在相同的 Issue
- 搜索已关闭的 Issue，您的问题可能已被解决
- 阅读 README 和文档

### Issue 模板
```markdown
## 问题描述
清晰简明地描述您遇到的问题

## 复现步骤
1. 第一步
2. 第二步
3. ...

## 预期行为
您期望发生什么

## 实际行为
实际发生了什么

## 环境信息
- OS: Windows/Linux/Mac
- Python 版本: X.X.X
- 其他相关信息

## 日志输出
粘贴相关的日志或错误信息
```

## 💡 建议功能

我们欢迎功能建议！请在 Issue 中详细描述：
- 功能的用途和好处
- 实现思路（如果有的话）
- 参考资源或示例代码

## 🔧 提交 Pull Request

### 准备工作
1. Fork 本仓库到您的账户
2. 克隆您的 Fork：`git clone https://github.com/YOUR_USERNAME/UE_MI_ZED_HandCTL.git`
3. 添加上游远程：`git remote add upstream https://github.com/giordanoshai/UE_MI_ZED_HandCTL.git`

### 开发工作流
1. 拉取最新代码：`git fetch upstream`
2. 创建新分支：`git checkout -b feature/your-feature-name`
3. 进行更改并提交：`git commit -m 'Add your changes'`
4. 同步上游更新：`git fetch upstream && git rebase upstream/main`
5. 推送到您的 Fork：`git push origin feature/your-feature-name`
6. 在 GitHub 上创建 Pull Request

### PR 模板
```markdown
## 描述
简要描述您的更改

## 关联 Issue
Fix #123

## 更改类型
- [ ] Bug 修复
- [ ] 新功能
- [ ] 文档更新
- [ ] 性能优化
- [ ] 其他

## 测试
描述您进行的测试

## 检查清单
- [ ] 代码遵循项目风格
- [ ] 已添加/更新相关文档
- [ ] 提交信息清晰
- [ ] 无新的警告信息
```

### 提交信息规范
```
<type>: <subject>

<body>

<footer>
```

类型说明：
- `feat` - 新功能
- `fix` - Bug 修复
- `docs` - 文档更新
- `style` - 代码格式（无逻辑变化）
- `refactor` - 代码重构
- `perf` - 性能优化
- `test` - 测试添加或修改
- `chore` - 构建、依赖等

示例：
```
feat: 添加参数验证功能

实现参数类型检查和范围验证，防止无效值导致系统错误。

Fix #123
```

## 📝 代码标准

### Python 风格
- 遵循 PEP 8 规范
- 使用有意义的变量和函数名
- 添加必要的注释和文档字符串
- 函数和类应有 docstring

### 示例
```python
def process_parameters(params: dict, timeout: float = 5.0) -> dict:
    """
    处理并验证参数
    
    Args:
        params: 参数字典
        timeout: 处理超时时间（秒）
    
    Returns:
        处理后的参数字典
    
    Raises:
        ValueError: 参数无效时
    """
    # 实现代码
    pass
```

## 🧪 测试

- 所有新功能应包含相应的测试
- 运行现有测试确保无回归
- 提供测试覆盖率报告

## 📚 文档

- 更新 README 和相关文档
- 为新功能添加注释和示例
- 保持文档与代码同步

## 🎯 优先级

我们按以下顺序处理：
1. 安全性修复
2. Bug 修复
3. 文档改进
4. 新功能
5. 代码优化

## ❓ 常见问题

**PR 需要多久被审阅？**
- 通常在 1-2 周内，具体取决于复杂性

**如果 PR 被拒绝怎么办？**
- 我们会提供详细的反馈
- 您可以讨论或进行修��后重新提交

**我可以提交多个 PR 吗？**
- 可以！建议为不同功能创建独立的 PR

## 📞 获取帮助

- 查看 [FAQ](FAQ.md)
- 搜索已有讨论
- 提交 Issue 或在讨论区提问

---

**再次感谢您的贡献！** 🙏
