# 飞书知识库文档模板与要点

## 分析类文档模板

用于梳理 / 现状分析 / 方案 / 架构 / 调研。落盘后**必须**上传飞书。

```markdown
# <主题>：现状分析与未来方案

> 更新时间：YYYY-MM-DD  
> 范围：`<模块或路径>`  
> 同步知识库：（上传后回填 Wiki URL）

## 1. 目标 / 背景

用 2～4 句话说明为何梳理、要回答什么问题。

## 2. 现状

- 已有能力（条目化）
- 关键路径 / API / UI 入口（表格可选）

## 3. 架构或流程（可选）

```text
…简图或步骤…
```

## 4. 缺口与风险

1. …
2. …

## 5. 未来方案（分期）

### Phase A（短期）
- [ ] …

### Phase B（中期）
- [ ] …

### Phase C（长期）
- [ ] …

## 6. 验证建议（可选）

1. …
```

本地建议路径：`docs/analysis/YYYY-MM-DD-<topic>.md`，或模块专属 `docs/<module>-<topic>.md`。

---

## 迭代说明模板（push 场景）

```markdown
# TestHub 迭代说明 YYYY-MM-DD

> 分支：`<branch>` · 范围：`<base>..HEAD` · 提交：`<shortsha 列表>`  
> 同步知识库：https://my.feishu.cn/wiki/<parent_or_new_node>

## 一、本次摘要

用 3～6 句话说明本轮迭代目标与结果。

## 二、改动项

### 功能
- …

### 修复
- …

### 重构 / 性能 / 其它
- …

## 三、模块影响

| 模块 | 变化 | 影响 |
|------|------|------|
| ui_automation | … | … |
| app_automation | … | … |
| frontend | … | … |

## 四、项目迭代情况

- 能力新增/增强：
- 行为变更（破坏性需标注）：
- 已知限制 / 后续计划：

## 五、部署与验证

- 依赖进程：Daphne / Redis≥5 / …
- 建议验证：
  1. …
  2. …

## 六、提交列表

- `abc1234` message
- …

---
*文档由 publish-to-feishu-wiki skill 生成*
```

本地路径：`docs/changelogs/YYYY-MM-DD-<shortsha>.md`。

---

## 飞书写入要点

1. **User Access Token** 需要：`wiki:wiki`、`docs:doc`、`drive:drive`（或等价）。
2. 流程：`medias/upload_all`（md）→ `drive/v1/import_tasks`（`point.mount_type=1` + 个人空间 root）→ 轮询 ticket → `move_docs_to_wiki`。
3. 应用身份常无法写 Wiki 父节点；优先 UAT（`mcp.json` 的 `-u`）。
4. `move_docs_to_wiki` 可能返回 `task_id`（异步）；用「列举父节点 children」确认新节点 URL。
5. **禁止**在文档、日志、commit 中写入 App Secret / user token。
6. Token 过期时：请用户更新 `mcp.json` 的 `-u` 后重跑脚本；勿用过期 token 反复重试刷屏。

## 上传命令

```bash
python .cursor/skills/push-changelog-to-feishu/scripts/publish_to_feishu_wiki.py \
  --md <path.md> \
  --title "<标题>"
```

## 配置示例

见同目录 `config.example.json`，复制为 `config.json`。
