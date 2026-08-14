---
name: publish-to-feishu-wiki
description: >-
  将 Markdown 文档写入飞书知识库：含（1）git push 时的迭代变更说明；
  （2）分析/梳理/方案/架构/调研类文档——一旦在对话中生成此类文档，必须落盘并上传 Wiki。
  Use when the user asks to push、推送、git push、写到飞书、同步知识库，
  or when producing 分析、梳理、现状、方案、架构、设计、调研、roadmap、自愈/能力梳理 docs.
---

# 文档 → 飞书知识库

本 skill 覆盖两类交付，**写入飞书是默认必做项**（失败要明确回报，不可静默跳过）：

| 类型 | 何时 | 本地路径约定 |
|------|------|----------------|
| A. 迭代变更说明 | 用户要求 push / 推送 / 同步迭代说明 | `docs/changelogs/YYYY-MM-DD-*.md` |
| B. 分析类文档 | 对话中产出「分析/梳理/方案」类 Markdown | `docs/analysis/` 或既有合理路径（如 `docs/ui-automation-*.md`） |

## 触发（必须应用本 skill）

### A. 推送 / 变更说明

- 用户说：push / 推送 / `git push` / 推上去
- 用户说：把本次改动写到飞书、同步迭代说明

**不要**在仅 commit、未提及推送时自动写「迭代说明」。

### B. 分析类文档（重点）

满足任一即视为分析类，**生成后必须上传飞书**：

- 用户要求：梳理、现状分析、能力盘点、方案设计、架构说明、未来规划、技术调研、对比评估、roadmap
- Agent 主动写出较完整的分析 Markdown（含「现状 / 缺口 / 未来方案 / 架构」等章节）
- 用户说：写到飞书、同步知识库、整理成文档

典型标题关键词：`分析`、`梳理`、`方案`、`架构`、`设计`、`调研`、`自愈`、`能力`、`迭代说明`（分析向）

**不要**把琐碎笔记、纯代码注释、一句话回复当成分析文档去传飞书。

判断有疑义时：若文档面向同事可读、可归档，则上传。

## 前置检查

1. 飞书：Cursor MCP `user-lark-mcp` / `lark-mcp` 可用；`mcp.json` 的 `-u` user token 含 `wiki:wiki`、`docs:doc`、`drive:drive`（勿把 secret/token 写进文档或 commit）。
2. 配置优先级：
   - 环境变量 `FEISHU_WIKI_SPACE_ID`、`FEISHU_WIKI_PARENT_NODE`
   - `.cursor/skills/push-changelog-to-feishu/config.json`（可参考 `config.example.json`）
   - 默认（TestHub）：`space_id=7672779267561786346`，`parent_node=NNPOwCrEVidgl2kBeLbc4qfUnCg`

缺配置时先问用户 Wiki 父节点链接，再继续。

Token 过期 / `99991677` / Wiki `131006 permission denied`：提示用户更新 `mcp.json` 的 `-u` token 后重试；可保留已生成的本地 md 与（若有）云文档链接。

---

## 工作流 B：分析类文档（优先熟记）

```
- [ ] 1. 在对话中完成分析内容
- [ ] 2. 落盘为 Markdown（docs/ 下）
- [ ] 3. 立即上传飞书知识库
- [ ] 4. 向用户回报 Wiki 链接 + 本地路径
```

### B1. 落盘

1. 目录优先：`docs/analysis/`（不存在则创建）；若用户/仓库已有更贴切路径（如模块专属 `docs/ui-automation-*.md`）可沿用。
2. 文件名：`YYYY-MM-DD-<topic-slug>.md`（英文 slug 或拼音短名，避免空格）。
3. 标题清晰，例如：`TestHub UI自动化自愈：现状分析与未来方案`。
4. 结构可参考 [reference.md](reference.md)「分析类文档模板」；须含可读结论，禁止只贴文件名列表。
5. **禁止**写入 `.env`、密钥、mcp token、真实密码、隐私数据。

### B2. 上传飞书（强制）

```bash
python .cursor/skills/push-changelog-to-feishu/scripts/publish_to_feishu_wiki.py \
  --md <本地md路径> \
  --title "<文档标题>"
```

可选：`--space-id`、`--parent-node`、`--mcp-json <path>`。

成功标准：脚本输出 `OK wiki_url=https://my.feishu.cn/wiki/...`。

失败时：

1. 保留本地 md
2. 简体中文说明失败原因（token 过期 / 无 Wiki 编辑权等）
3. 若已有云文档但未迁入 Wiki，给出 `docx` 链接，请用户更新 token 或手动移入父节点
4. **不要**假装已写入 Wiki

### B3. 回报

- 飞书 Wiki 链接（必须）
- 本地 md 路径
- 文档要点 2～5 条（可选，保持简短）

同一主题短时间内不要重复刷多篇；若 Wiki 可能已有同名文档，先说明再问是否新建。

---

## 工作流 A：推送 → 迭代说明 → 飞书 → push

```
- [ ] 1. 收集推送范围
- [ ] 2. 梳理改动与迭代
- [ ] 3. 生成 Markdown（docs/changelogs/）
- [ ] 4. 写入飞书知识库
- [ ] 5. 执行或确认 git push
- [ ] 6. 向用户回报 Wiki 链接
```

### A1. 收集推送范围

```bash
git status -sb
git branch -vv
git log --oneline @{u}..HEAD
git diff --stat @{u}..HEAD
git log -20 --oneline --format="%h %s"
```

| 场景 | 梳理范围 |
|------|----------|
| 已 ahead、准备 push | `@{u}..HEAD` |
| 刚 push 完 | 本次 push 的 commits |
| 用户指定 | 按其 base/区间 |

### A2. 梳理

按模块：`ui_automation` / `app_automation` / `api_testing` / 其它 `apps/*` / `frontend` / 配置 Docker docs。

提炼：改动项（为什么）· 迭代情况 · 风险与验证。模板见 [reference.md](reference.md)。

### A3. 生成 Markdown

- 标题：`TestHub 迭代说明 YYYY-MM-DD`（可含 branch/短 sha）
- 路径：`docs/changelogs/YYYY-MM-DD-<shortsha>.md`

### A4. 写入飞书

同 B2，对 changelog 文件执行 `publish_to_feishu_wiki.py`。

### A5. Git push

用户要求 push 且尚未推送时：飞书写入成功（或用户确认可稍后补写）后再 `git push`。不 force push；不改 git config。

### A6. 回报

推送结果 · 改动要点 3～8 条 · Wiki 链接 · 本地 md 路径。

---

## 上传实现备忘

**推荐脚本**（从 `mcp.json` 读 `-u`，勿打印 token）：

```bash
python .cursor/skills/push-changelog-to-feishu/scripts/publish_to_feishu_wiki.py --md <path.md> --title "<title>"
```

**备选**：MCP `docx_builtin_import`（`useUAT: true`）→ `move_docs_to_wiki` → 取 `https://my.feishu.cn/wiki/<node_token>`。

应用 tenant token 常无法写 Wiki 父节点；**优先 user token**。

---

## 质量要求

- 面向同事可读；分析类须有结论与可执行后续，不堆无结构原文
- 简体中文回复（除非用户要求其它语言）
- 分析类文档：**先落盘，再上传，最后在回复里给 Wiki 链接**——三者缺一视为未完成
