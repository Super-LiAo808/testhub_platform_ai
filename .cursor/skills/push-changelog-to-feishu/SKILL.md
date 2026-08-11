---
name: push-changelog-to-feishu
description: >-
  在推送代码时梳理 Git 改动与项目迭代，生成详细变更说明并写入飞书知识库。
  Use when the user asks to push、推送、git push，或明确要求把本次迭代/变更写到飞书 Wiki。
---

# 推送梳理 → 飞书知识库

每次**推送代码**（或用户明确要求同步迭代说明）时执行本流程：梳理改动 → 生成 Markdown → 写入飞书知识库 → 再完成/确认 push。

## 触发

- 用户说：push / 推送 / `git push` / 推上去
- 用户说：把本次改动写到飞书、同步迭代说明、推送梳理

**不要**在仅 commit、未提及推送时自动写飞书。

## 前置检查

1. 工作区为 git 仓库；确认当前 branch、ahead/behind、是否已 push。
2. 飞书：Cursor MCP `user-lark-mcp` / `lark-mcp` 可用，且 user token 含 `wiki:wiki`、`docs:doc`、`drive:drive`（不要把 secret/token 写进文档或 commit）。
3. 读取配置（优先级从高到低）：
   - 环境变量 `FEISHU_WIKI_SPACE_ID`、`FEISHU_WIKI_PARENT_NODE`
   - 项目文件 `.cursor/skills/push-changelog-to-feishu/config.json`（可参考 `config.example.json`）
   - 默认（TestHub）：`space_id=7672779267561786346`，`parent_node=NNPOwCrEVidgl2kBeLbc4qfUnCg`

缺配置时先问用户 Wiki 父节点链接，再继续。

## 工作流

复制并跟踪：

```
- [ ] 1. 收集推送范围
- [ ] 2. 梳理改动与迭代
- [ ] 3. 生成 Markdown 文档
- [ ] 4. 写入飞书知识库
- [ ] 5. 执行或确认 git push
- [ ] 6. 向用户回报 Wiki 链接
```

### 1. 收集推送范围

在仓库根目录执行（PowerShell 可用 `;` 连接）：

```bash
git status -sb
git branch -vv
git log --oneline @{u}..HEAD   # 无 upstream 则用 origin/main..HEAD 或用户指定 base
git diff --stat @{u}..HEAD
git log -20 --oneline --format="%h %s"
```

范围规则：

| 场景 | 梳理范围 |
|------|----------|
| 已 ahead、准备 push | `@{u}..HEAD` 全部 commits + diff |
| 刚 push 完 | 本次 push 的 commits（从对话/reflog 确认） |
| 用户指定 | 按其给的 base/区间 |

**禁止**把 `.env`、密钥、mcp token、真实密码写进梳理文档。

### 2. 梳理改动与迭代

按模块归类（贴合本仓库）：

- `apps/ui_automation`、`apps/app_automation`、`apps/api_testing`、其它 `apps/*`
- `frontend/src/...`
- 配置 / Docker / docs / migrations

提炼：

- **改动项**：功能 / 修复 / 重构 / 性能 / 文档（条目化，写清「为什么」）
- **迭代情况**：相对上一版能力变化、已知限制、部署注意（如仅 Daphne、Redis≥5）
- **风险与验证**：建议回归点（可选）

可参考 [reference.md](reference.md) 模板。

### 3. 生成 Markdown

1. 标题：`TestHub 迭代说明 YYYY-MM-DD`（或含 branch/短 sha）
2. 保存到 `docs/changelogs/YYYY-MM-DD-<shortsha>.md`（目录不存在则创建）
3. 正文用 [reference.md](reference.md) 结构；篇幅完整，勿只写一句话摘要

### 4. 写入飞书知识库

**推荐**：跑脚本（从 `mcp.json` 读 `-u` token，勿打印 token）：

```bash
python .cursor/skills/push-changelog-to-feishu/scripts/publish_to_feishu_wiki.py --md docs/changelogs/<file>.md
```

可选参数：`--space-id`、`--parent-node`、`--title`、`--mcp-json <path>`。

**备选（无脚本环境）**：

1. MCP `docx_builtin_import`（`useUAT: true`）导入 Markdown  
2. OpenAPI `wiki/v2/spaces/{space_id}/nodes/move_docs_to_wiki`，`parent_wiki_token` = 父节点  
3. 轮询/列举子节点拿到 `https://my.feishu.cn/wiki/<node_token>`

权限失败时：提示用户给应用/账号 Wiki **可编辑**，并提供已生成的本地 md + 云文档链接；**不要**把 secret 写进回复。

### 5. Git push

- 若用户要求 push 且尚未推送：在飞书写入成功（或用户确认可稍后补写）后执行 `git push`（需用户规则允许的网络权限）。
- 默认不 `force push`；不改 git config。
- 若 push 失败：保留本地 changelog，说明飞书是否已写。

### 6. 回报用户

简短中文回复，包含：

- 推送结果（成功/跳过/失败）
- 改动要点 3–8 条
- 飞书 Wiki 链接
- 本地 md 路径

## 质量要求

- 改动描述面向同事可读，避免堆文件名列表而无结论
- 同一推送区间不重复刷多篇；若 Wiki 已有同名文档，说明并询问是否覆盖/新建
- 响应使用简体中文（除非用户要求其它语言）
