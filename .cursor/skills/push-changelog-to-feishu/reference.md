# 迭代说明模板与飞书说明

## Markdown 模板

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
*文档由 push-changelog-to-feishu skill 生成*
```

## 飞书写入要点

1. **User Access Token** 需要：`wiki:wiki`、`docs:doc`、`drive:drive`（或等价）。
2. 流程：`medias/upload_all`（md）→ `drive/v1/import_tasks`（`point.mount_type=1` + 个人空间 root）→ 轮询 ticket → `move_docs_to_wiki`。
3. 应用身份常无法写 Wiki 父节点；优先 UAT。
4. `move_docs_to_wiki` 可能返回 `task_id`（异步）；用「列举父节点 children」确认新节点 URL。
5. **禁止**在文档、日志、commit 中写入 App Secret / user token。

## 配置示例

见同目录 `config.example.json`，复制为 `config.json`（建议加入 `.gitignore` 若含私有节点；当前仅 space/node id 可提交）。
