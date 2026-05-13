# 从零构建 Claude Code -- 动手学习 AI Agent 架构

> **"The Model IS the Agent. You build the harness."**

基于 [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 从零重建，通过 12 个渐进式课程，理解 Claude Code / AI Agent 的核心架构。

---

## 项目简介

本项目不是简单地阅读源码，而是通过**亲手实现** AI Agent 的每一层功能，深入理解"模型即 Agent"的设计哲学。你将从一个简单的 API 循环开始，逐步构建出子代理、技能系统、上下文压缩、多 Agent 协作等高级功能。

---

## 课程大纲

| 课程 | 主题 | 说明 |
|------|------|------|
| s01 | Agent Loop | `while(stop_reason=="tool_use")` 核心循环 |
| s02 | Tool Dispatch | `{tool_name: handler}` 工具分派机制 |
| s03 | TodoWrite + 会话持久化 | 内存任务列表 + JSONL 持久化 + Nag 提醒 |
| s04 | Subagents | 用干净的上下文生成一次性子代理 |
| s05 | Skills | 按需加载 SKILL.md 技能文件 |
| s06 | Context Compact | 三层上下文压缩（微型/自动/手动） |
| s07 | Tasks | 基于文件的任务图，支持依赖关系 |
| s08 | Background Tasks | 守护线程 + 通知队列 |
| s09 | Agent Teams | JSONL 邮箱 + 消息总线 |
| s10 | Team Protocols | 关闭协议 + 计划审批握手 |
| s11 | Autonomous Agents | 空闲周期任务认领 |
| s12 | Worktree + 综合项目 | 每个 Agent 独立工作目录，s01-s11 整合 |

---

## 目录结构

```
.
├── codes/                  # 骨架代码（待填充 TODO）
│   ├── s03_my_todolist.py  # s03 实现已完成
│   └── s04_subagents.py    # s04 骨架代码
├── lessons/                # 课程学习材料
│   ├── s03_lesson_material.md
│   ├── s04_lesson_material.md
│   └── ... (s05 ~ s12)
├── diagrams/               # 流程图与架构图
├── review/                 # 代码审查记录
├── PROGRESS.md             # 学习进度追踪
├── .env.example            # 环境变量模板
└── .gitignore
```

---

## 快速开始

### 环境要求

- Python 3.8+
- `anthropic` SDK
- Anthropic API Key（或其他兼容 OpenAI 格式的 API）

### 安装

```bash
# 克隆仓库
git clone https://github.com/shanjw21/claude_code_learning.git
cd claude_code_learning

# 安装依赖
pip install anthropic python-dotenv

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API Key
```

### 运行

```bash
# 从 s03 开始（带会话持久化的 Agent）
python codes/s03_my_todolist.py

# 完成 s04 TODO 后运行子代理版本
python codes/s04_subagents.py
```

---

## 学习方法

本项目采用 **"先理解为什么，再动手怎么做"** 的学习方式：

1. 阅读 `lessons/` 下的课程材料，理解每个功能要解决的问题
2. 在 `codes/` 中找到对应的骨架代码，填充 `TODO` 部分
3. 运行测试，验证功能是否正常
4. 提交代码审查，获取反馈

---

## 架构概览

```
s01  Agent Loop          → while(stop_reason=="tool_use"): 执行、追加、循环
s02  Tool Dispatch       → {tool_name: handler} 映射（循环不变）
s03  TodoWrite           → 内存任务列表 + Nag 提醒
s04  Subagents           → 用干净上下文隔离子任务
s05  Skills              → 按需加载技能文件
s06  Context Compact     → 三层上下文压缩
s07  Tasks               → 基于文件的任务图
s08  Background Tasks    → 后台守护线程
s09  Agent Teams         → JSONL 邮箱 + 消息总线
s10  Team Protocols      → 关闭 + 审批协议
s11  Autonomous Agents   → 空闲周期任务认领
s12  Worktree Isolation  → 每个 Agent 独立工作目录
```

每一课都在前一课的基础上添加新功能，逐步从简单的 API 循环演变为完整的多 Agent 系统。

---

## 当前进度

| 课程 | 学习材料 | 代码实现 | 代码审查 |
|------|:--------:|:--------:|:--------:|
| s03 | ✅ | ✅ | ✅ |
| s04 | ✅ | 🚧 进行中 | -- |
| s05 ~ s12 | ✅ | 待实现 | -- |

详细进度追踪见 [PROGRESS.md](PROGRESS.md)。

---

## 参考

- 原始项目: https://github.com/shareAI-lab/learn-claude-code
- 本项目仓库: https://github.com/shanjw21/claude_code_learning
