---
name: commit
description: Generate commit messages following Conventional Commits specification
trigger: commit, message, 提交, git commit
---
# Commit Message 生成指南

## 格式规范

遵循 Conventional Commits 规范：

```
<type>(<scope>): <subject>

<body>
```

## type 可选值

| type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(auth): add OAuth login support` |
| `fix` | 修复 bug | `fix(session): handle missing session key` |
| `docs` | 文档更新 | `docs(api): add rate limit documentation` |
| `style` | 代码格式（不影响功能） | `style: fix indentation in utils.py` |
| `refactor` | 重构（非功能变更） | `refactor(auth): extract token validation` |
| `test` | 测试相关 | `test(todo): add validation edge cases` |
| `chore` | 构建/工具/杂项 | `chore: update dependencies` |

## 生成步骤

1. 运行 `git diff --cached` 查看已暂存的变更
2. 分析变更的类型和功能
3. 选择合适的 type 和 scope
4. 用祈使句写 subject（如 "add" 而非 "added"）
5. 如果有多个不同类型的变更，考虑拆分为多个 commit

## 注意事项

- subject 不超过 72 字符
- type 必须是小写
- 使用中文生成但最终输出英文 commit message
- scope 应该是被修改的模块名或功能区域
