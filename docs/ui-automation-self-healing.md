# TestHub UI 自动化自愈能力：现状分析与未来方案

> 更新时间：2026-08-12  
> 范围：`apps/ui_automation` + APP 诊断对齐  
> 状态：**企业落地 Phase A～C 核心已交付**

---

## 1. 目标定义

| 层级 | 含义 | 成熟度 |
|------|------|--------|
| 运行时自愈 | 主定位失败尝试 `backup_locators`，记录命中并可升格 | 已具备 |
| 事后自愈 | 失败诊断 → 策略控制应用 → 重跑验证 → 可回滚 | 半自动闭环 |
| 度量治理 | 自愈中心看板 + 项目级策略 | 已具备 |

原则：业务代码永不自动改仓；默认 `manual_apply` + `verify_rerun`。

---

## 2. 项目策略（`UiProject.heal_settings`）

```json
{
  "auto_diagnose": true,
  "mode": "manual_apply",
  "auto_apply_types": ["increase_wait", "add_backup_locator"],
  "verify_rerun": true,
  "auto_promote_backup": false,
  "use_llm_on_manual_diagnose": true
}
```

- `diagnose_only`：只诊断不写元素  
- `manual_apply`：人工点应用（默认）  
- `auto_low_risk`：白名单类型自动应用并验证  

前端：项目编辑对话框「自愈策略」。

---

## 3. 闭环流程

1. 执行失败 → signal 自动规则诊断（可关）  
2. 补全 `element_id` / `candidate_locators` / 截图引用 / DOM 片段  
3. 人工或低风险自动应用 → 写入 `before_snapshot`  
4. `verify_rerun` 重跑关联用例 → `verify_status`  
5. 失败可 **回滚** 到快照  

备用命中：`locator_used` + `used_backup` 落库 → 升格提案（可 `auto_promote_backup`）。

---

## 4. 入口

| 入口 | 说明 |
|------|------|
| `/ui-automation/self-healing` | 自愈中心看板 |
| AI 执行报告 | 查看/重新 AI 诊断 |
| 用例执行列表 | 「自愈诊断」 |
| APP 执行 | `POST .../app-automation/executions/{id}/diagnose/` |

API：

```http
GET  /api/ui-automation/self-healing/stats/?project_id=&days=30
POST /api/ui-automation/failure-diagnoses/{id}/apply-script-fix/
POST /api/ui-automation/failure-diagnoses/{id}/rollback-script-fix/
```

---

## 5. 已知限制（后续）

1. 完整视觉灰测多候选 ranking 未默认开启  
2. APP 仅分类诊断，无 OCR 自动写回  
3. 套件路径与单用例引擎路径备用回退已对齐，但极端定位策略仍需回归  
4. 自愈成功率依赖 `verify_rerun` 与可关联用例  

---

## 6. 部署

```bash
python manage.py migrate ui_automation
```

迁移：`0007_heal_enterprise_fields.py`（`heal_settings`、提案验证/回滚字段、`execution_type=app`）。
