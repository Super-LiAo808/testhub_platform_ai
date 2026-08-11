# TestHub 智能测试管理平台

<div align="center">

**基于 AI 驱动的全栈测试管理平台**

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2-green.svg)](https://www.djangoproject.com/)
[![Vue](https://img.shields.io/badge/Vue-3-brightgreen.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/License-GPL_v3-blue.svg)](LICENSE)

</div>

## 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [技术架构](#技术架构)
- [项目结构](#项目结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [核心功能模块说明](#核心功能模块说明)
- [录制与扫描](#录制与扫描)
- [API 结构](#api-结构)
- [配置说明](#配置说明)
- [数据库设计概览](#数据库设计概览)
- [管理命令](#管理命令)
- [文档索引](#文档索引)
- [常见问题](#常见问题)
- [许可证](#许可证)

---

## 项目简介

TestHub 是一个面向测试团队的智能测试管理平台，集成 **AI 需求分析**、**测试用例管理与评审**、**API 测试**、**UI 自动化（Web）**、**APP 自动化（Android）**、**数据工厂**、**执行与报告** 等能力。

技术栈为 **Django 4.2（后端）+ Vue 3（前端）**，提供现代化界面、JWT 安全认证、多语言（中/英/日/韩）以及可扩展的自动化与 AI 能力。

---

## 核心特性

### AI 智能化

- **AI 需求分析**：解析 PDF / Word / TXT 需求文档，提取业务需求与功能点
- **智能用例生成**：基于需求自动生成测试用例，支持自定义提示词（见 `docs/tester.md`、`docs/tester_pro.md`）
- **智能助手**：集成 Dify，支持多会话与测试咨询
- **多模型支持**：DeepSeek、通义千问、硅基流动、智谱、小米、OpenAI 兼容 API 等
- **AI 智能模式（Browser-use）**：基于 DOM / 文本理解自动完成浏览器测试；执行后可将识别元素同步到 UI 元素库（`discovery_source=ai_discovered`）
- **录制固化**：Web 操作录制 → `UIActionTrace` → 编译为可回归 `TestCase`；失败诊断与半自动修复管线（见 UI 自动化模块）

### 安全机制

- **JWT 双 Token**：短期 Access Token + 长期 Refresh Token
- **自动刷新**：前端在过期前无感续期；刷新期间请求排队
- **Token 黑名单**：登出 / 轮换后旧 Refresh Token 不可再用
- **CORS / CSRF**：可通过环境变量精细配置（见 `.env.example`）

### 统一配置中心

- 浏览器 / Playwright 环境检测与驱动管理
- AI 模型按角色配置（编写专家、评审专家、Browser Use 文本模式等）
- 连接测试与参数校验
- 邮件 / Webhook（企业微信、钉钉、飞书等）通知配置（`core` 统一通知）

### 测试用例管理

- 完整生命周期：创建、编辑、版本关联、归档
- 多维度组织：项目、版本、标签等
- 步骤化设计：前置条件、操作步骤、预期结果
- 附件上传与团队评论

### 测试用例评审

- 多人评审、评审模板、检查清单
- 状态：待评审 / 评审中 / 已通过 / 已拒绝等
- 整体意见、用例意见、步骤意见等多层级反馈

### API 测试

- 项目 / 集合树形组织，HTTP 与 WebSocket
- 多方法请求、环境变量与变量替换
- 测试套件、断言、执行顺序
- 请求历史、定时任务、邮件 / Webhook 通知
- Allure 报告

### UI 自动化测试（Web）

- **双引擎**：Selenium、Playwright
- **元素管理**：多种定位策略；页面分组；**页面 URL 异步扫描入库**（Playwright + 并发限制 + SSRF 防护）
- **页面对象（POM）**、测试脚本 / 用例步骤、多浏览器（Chrome / Firefox / Edge）
- **Web 操作录制**：Chromium 采集点击 / 输入 / 滚动等 → 生成 TestCase
- **执行记录**：日志、截图；定时任务（Cron / 间隔 / 单次）
- **AI 智能模式**：任务规划、步骤执行、元素同步、可选固化用例

### APP 自动化测试（Android）

- **回放引擎**：Airtest + 图像 / 坐标 / 区域元素
- **设备管理**：本地 / 远程设备、锁定与资源池
- **组件化编排**：基础组件、自定义组件、组件包导入（`load_component_pack`）
- **UI Flow**：JSON 流程编排，变量作用域（global / local / outputs）
- **操作录制**：优先 **scrcpy H.264 实时投屏**，手势同步生成图片元素与 `ui_flow`；scrcpy 不可用时回退截屏；中文输入按需 Appium（不抢前台）
- **实时进度**：Channels WebSocket（需 Daphne + Redis ≥ 5）
- **报告**：pytest + Allure；Celery 异步执行（可选）

### 测试执行与报告

- 测试计划关联项目、版本与用例
- 手工 / 自动化执行与历史对比
- 多维度统计与图表
- Allure 专业报告

### 数据工厂

覆盖字符、编码、随机、加密、测试数据（姓名 / 手机 / 身份证等）、JSON、Crontab、条码 / 二维码等工具；支持标签、使用记录，以及在 API / UI 步骤中通过选择器引用。

详细说明见 [docs/数据工厂使用说明.md](./docs/数据工厂使用说明.md)。

### 项目与团队

- 多项目、成员与角色
- 版本规划与用例关联
- 用户偏好与国际化（zh-hans / en / ja / ko）

---

## 技术架构

### 后端

| 类别 | 技术 |
|------|------|
| 框架 | Django 4.2、Django REST Framework |
| 数据库 | MySQL 8.0+（utf8mb4） |
| 认证 | JWT（simplejwt）+ Token 黑名单 |
| API 文档 | drf-spectacular（Swagger / ReDoc） |
| 异步 | Celery（可选）、后台线程（录制 / 页面扫描等） |
| WebSocket | Django Channels + Daphne；Redis Channel Layer |
| 自动化 | Selenium、Playwright、browser-use、LangChain |
| APP | Airtest、EasyOCR、OpenCV、Appium（录制辅助）、scrcpy |
| 其他 | httpx、Celery、APScheduler 风格调度命令、文档解析（PyPDF / python-docx 等） |

### 前端

| 类别 | 技术 |
|------|------|
| 框架 | Vue 3 Composition API |
| 构建 | Vite |
| UI | Element Plus |
| 状态 / 路由 | Pinia、Vue Router |
| 网络 | Axios |
| 可视化 / 编辑 | ECharts、Monaco Editor |
| 其他 | vue-i18n、vuedraggable、xlsx、dayjs、curlconverter |

### 运行时拓扑（简图）

```text
浏览器 (Vite :3000)
    │  /api 代理
    ▼
Django / Daphne (:8000)
    ├── MySQL
    ├── Redis（Channels / Celery，推荐）
    ├── Playwright / Selenium（UI）
    ├── scrcpy + ADB（APP 录制）
    └── Airtest（APP 回放）
```

---

## 项目结构

```text
testhub_platform/
├── apps/                              # Django 应用
│   ├── users/                         # 用户认证与资料（自定义 User）
│   ├── projects/                      # 项目管理
│   ├── testcases/                     # 手工测试用例
│   ├── testsuites/                    # 测试套件
│   ├── executions/                    # 测试计划与执行
│   ├── reports/                       # 报告
│   ├── reviews/                       # 用例评审
│   ├── versions/                      # 版本管理
│   ├── requirement_analysis/          # AI 需求分析与用例生成
│   ├── assistant/                     # Dify 智能助手
│   ├── api_testing/                   # API 测试
│   ├── ui_automation/                 # UI 自动化 / AI / Web 录制 / 页面扫描
│   ├── app_automation/               # APP 自动化 / 设备 / 录制 / 执行
│   ├── data_factory/                  # 数据工厂
│   ├── analytics/                     # 行为埋点（ANALYTICS_ENABLED）
│   └── core/                          # 共享能力与全部 management commands
├── backend/
│   ├── settings.py                    # 配置（DB / JWT / Celery / Channels / CORS）
│   ├── urls.py                        # 根路由
│   ├── asgi.py                        # ASGI；有 channels 时启用 WebSocket
│   └── wsgi.py
├── frontend/
│   ├── src/
│   │   ├── api/                       # 接口封装
│   │   ├── views/                     # 各业务页面
│   │   │   ├── api-testing/
│   │   │   ├── app-automation/        # 含 recording/
│   │   │   ├── ui-automation/         # 含 recording/、elements/、ai/
│   │   │   ├── data-factory/
│   │   │   ├── requirement-analysis/
│   │   │   ├── configuration/
│   │   │   └── ...
│   │   ├── stores/                    # Pinia
│   │   ├── router/
│   │   ├── locales/                   # i18n
│   │   ├── components/
│   │   └── utils/
│   ├── vite.config.js
│   └── package.json
├── tools/scrcpy/                      # 内置 scrcpy（APP 实时投屏）
├── docs/                              # 专题文档
├── media/                             # 上传文件、截图、Allure 产物等
├── logs/                              # 运行日志（含 scheduler）
├── requirements.txt
├── .env.example
├── manage.py
├── README.md
├── AGENTS.md / CLAUDE.md              # 给 AI Agent 的仓库指引
└── LICENSE
```

---

## 环境要求

| 依赖 | 版本 / 说明 |
|------|-------------|
| Python | **3.12 推荐**（其他版本可能不兼容） |
| Node.js | **18+**（前端构建；APP 录制用 Appium 也需要） |
| MySQL | **8.0+**，utf8mb4 |
| Redis | **≥ 5**（Channels；过旧会降级 InMemory，多进程下投屏不可用） |
| Java | 17+ 可选（Allure 等） |
| 浏览器 | Chrome 等（UI 自动化） |
| Android 工具 | ADB；录制建议 Appium + uiautomator2；可选本机 scrcpy |

---

## 快速开始

### 1. 克隆与虚拟环境

```bash
git clone <repository-url>
cd testhub_platform

python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. 环境变量

```bash
cp .env.example .env
```

至少配置：

- `SECRET_KEY`、`DEBUG`、`ALLOWED_HOSTS`
- `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD`
- `REDIS_URL`（APP WebSocket / Celery 推荐）
- 按需：邮件、短信、`SCRCPY_*`、`CHANNELS_*`、`UI_SCAN_MAX_CONCURRENT` 等

### 3. 数据库

```bash
mysql -u root -p -e "CREATE DATABASE testhub CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

python manage.py migrate
python manage.py createsuperuser
```

### 4. 初始化数据（建议）

```bash
python manage.py init_locator_strategies   # UI 定位策略
python manage.py download_webdrivers       # 浏览器驱动（可选）
python manage.py load_component_pack       # APP 组件包（可选，--overwrite 覆盖）
```

### 5. 启动后端

```bash
# 仅 HTTP（UI Web 录制可用；APP 投屏 WebSocket 不可用）
python manage.py runserver

# 推荐：HTTP + WebSocket（APP 录制 / 执行进度）
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

另开终端按需启动：

```bash
# API + UI 定时任务统一调度
python manage.py run_all_scheduled_tasks

# Celery Worker（APP 等异步任务，可选）
celery -A backend worker -l info
```

### 6. 启动前端

```bash
cd frontend
npm install
npm run dev      # 默认 http://localhost:3000，代理 /api 到后端
npm run build    # 生产构建
npm run lint
```

### 7. 访问地址

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:3000 |
| 后端 API | http://localhost:8000 |
| Swagger | http://localhost:8000/api/docs/ |
| ReDoc | http://localhost:8000/api/redoc/ |
| Admin | http://localhost:8000/admin/ |

---

## 核心功能模块说明

### 1. `core` — 跨模块核心

- **管理命令**：定时调度、定位策略、WebDriver、APP 组件包（见下方「管理命令」）
- **变量解析**：跨模块变量替换
- **统一通知**：`UnifiedNotificationConfig`，企业微信 / 钉钉 / 飞书等 Webhook，可按 API / UI 模块开关

API：`/api/core/`

### 2. `requirement_analysis` — AI 需求分析

- 上传并解析需求文档，提取业务需求，生成测试用例
- 模型配置：`AIModelConfig`（多提供商、多角色）

主要模型：需求文档、分析记录、业务需求、生成用例、分析任务等。

API：`/api/requirement-analysis/`

### 3. `assistant` — 智能助手

- Dify 配置、会话、消息历史

API：`/api/assistant/`

### 4. `api_testing` — API 测试

- 项目 / 集合 / 请求、环境变量、套件执行、历史、定时任务、通知、Allure

API：挂在 `/api/` 下（见模块路由）

### 5. `ui_automation` — UI 自动化

- 元素 / 分组 / 页面对象 / 脚本与 TestCase / 套件 / 执行 / 定时任务
- AI 智能模式（`ai_base.py`、`ai_agent.py`）
- Web 录制与动作轨迹编译
- **页面扫描异步任务** `PageElementScanJob`：提交后后台 Playwright 扫描并入库

API：`/api/ui-automation/`

### 6. `app_automation` — APP 自动化

- 项目、设备、元素（image / pos / region）、用例 `ui_flow`、套件、执行、报告
- scrcpy 镜像录制、Appium 按需输入、WebSocket 进度

API：`/api/app-automation/`  
WebSocket：`ws/app-automation/executions/<execution_id>/`

### 7. `data_factory` — 数据工厂

- 多类工具执行、历史记录、标签、在 API/UI 中引用

API：`/api/data-factory/`

### 8. `reviews` / `executions` / `reports` / `versions` / `projects` / `testcases`

- 评审流程、测试计划与执行、报告、版本、项目成员、手工用例全生命周期

### 9. `analytics` — 埋点（可选）

- 通过 `ANALYTICS_ENABLED` 启用；API：`/api/analytics/`

---

## 录制与扫描

### Web 操作录制

| 项 | 说明 |
|----|------|
| 入口 | `/ui-automation/recording` |
| 产物 | 事件落库 `UIActionTrace`，可编译为 `TestCase` + `Element` |
| 引擎 | Playwright Chromium；敏感输入（密码等）会脱敏 |

### APP 操作录制

| 项 | 说明 |
|----|------|
| 入口 | `/app-automation/recording` |
| 镜像 | 优先 scrcpy H.264 → 前端 WebCodecs；失败回退截屏（不强制按 HOME 抢前台） |
| 控制 | 点击 / 滑动走 ADB；中文等复杂输入按需 Appium |
| 产物 | 图片元素 + `ui_flow`，可生成 `AppTestCase` |
| 运行要求 | **Daphne + Redis ≥ 5**；本机 Appium（`npm i -g appium && appium driver install uiautomator2`）；ADB / SDK |

环境变量示例（详见 `.env.example`）：

```env
REDIS_URL=redis://127.0.0.1:6379/0
# SCRCPY_PATH=
# SCRCPY_SERVER_PATH=
SCRCPY_MAX_SIZE=1280
SCRCPY_BIT_RATE=2M
# CHANNELS_INMEMORY=False
# CHANNELS_REQUIRE_REDIS=False
```

### UI 页面元素扫描（异步）

1. 前端「元素管理」提交 URL  
2. `POST /api/ui-automation/elements/scan-page/` → `202` + `job_id`  
3. `GET /api/ui-automation/elements/scan-jobs/{id}/` 轮询进度  
4. 成功后写入单一页面分组（`discovery_source=page_scan`）

服务端策略：

- 强制无头 Chromium
- 全局并发限制（默认 2，可用 `UI_SCAN_MAX_CONCURRENT` 调整）
- URL SSRF 防护（拒绝 localhost / 私网 / 元数据地址）
- 同项目排队中任务数量上限

AI 执行结束后也会把发现的元素同步到元素库（`ai_discovered`）。

---

## API 结构

所有业务 API 以 `/api/` 为前缀：

| 前缀 | 模块 |
|------|------|
| `/api/auth/`、`/api/users/` | 认证与用户 |
| `/api/projects/` | 项目 |
| `/api/testcases/` | 手工用例 |
| `/api/testsuites/` | 套件 |
| `/api/executions/` | 执行 |
| `/api/reports/` | 报告 |
| `/api/reviews/` | 评审 |
| `/api/versions/` | 版本 |
| `/api/assistant/` | 助手 |
| `/api/requirement-analysis/` | 需求分析 |
| `/api/`（api_testing 路由） | API 测试 |
| `/api/ui-automation/` | UI 自动化 |
| `/api/app-automation/` | APP 自动化 |
| `/api/core/` | 核心共享 |
| `/api/data-factory/` | 数据工厂 |
| `/api/analytics/` | 埋点（可选） |

交互式文档：`/api/docs/`（Swagger）、`/api/redoc/`（ReDoc）。

---

## 配置说明

### JWT

`backend/settings.py` 中典型配置思路：

- Access Token 短时效，Refresh Token 较长
- `ROTATE_REFRESH_TOKENS` + 黑名单，降低盗用风险
- 前端 Axios 拦截器自动带 Bearer，并在 401 时刷新

### AI 模型与角色

在统一配置中心配置提供商、API Key、Base URL、模型名、Temperature 等。

常见角色：

- 测试用例编写专家 / 评审专家
- `browser_use_text`：Browser Use 文本模式

提示词模板：`docs/tester.md`、`docs/tester_pro.md`。

### Dify 助手

配置 API URL 与 API Key 后启用助手模块。

### UI 自动化

- 引擎：Selenium / Playwright
- 有头 / 无头；驱动可通过配置中心或 `download_webdrivers` 管理
- 页面扫描：`UI_SCAN_FORCE_HEADLESS`、`UI_SCAN_MAX_CONCURRENT`、`UI_SCAN_ACQUIRE_TIMEOUT`

### APP / Channels

- `REDIS_URL`：Celery 与 Channels 共用
- Redis &lt; 5 时自动降级 `InMemoryChannelLayer`（日志会告警）；生产可用 `CHANNELS_REQUIRE_REDIS=1` 强制失败
- scrcpy：`SCRCPY_PATH` / `SCRCPY_SERVER_PATH` / 码率与最大边长

### 通知

- 邮件：`EMAIL_*`
- Webhook：`core` 统一通知配置

### 生产注意

1. 修改强 `SECRET_KEY`，`DEBUG=False`
2. 限制 `ALLOWED_HOSTS`、`CORS_ALLOWED_ORIGINS`、`CSRF_TRUSTED_ORIGINS`
3. 勿将 `.env` 提交仓库
4. 使用 Redis ≥ 5 跑 Daphne，保证 APP 投屏多进程可用
5. media / logs 由运行时生成，勿依赖仓库内产物

---

## 数据库设计概览

主要表域（逻辑名，实际以各 app `Meta.db_table` 为准）：

- **用户**：自定义 User、资料、JWT 黑名单相关表
- **项目 / 版本**：项目、成员、版本
- **手工用例**：用例、步骤、附件、评论、套件关联
- **执行 / 报告**：计划、执行、结果、报告统计
- **评审**：评审单、分配、意见、模板
- **需求分析 / AI**：文档、分析、业务需求、生成用例、`AIModelConfig`
- **助手**：Dify 配置、会话、消息
- **API 测试**：项目、集合、请求、环境、套件、历史、定时任务
- **UI 自动化**：项目、元素、分组、页面对象、脚本、TestCase、执行、定时任务、AI 用例、**页面扫描任务**
- **APP 自动化**：项目、设备、元素、用例、执行、录制会话、配置
- **数据工厂**：工具使用记录与标签
- **核心**：统一通知配置
- **埋点**：事件表（可选）

---

## 管理命令

全部位于 `apps/core/management/commands/`：

```bash
python manage.py run_all_scheduled_tasks   # 统一调度 API + UI 定时任务（可 --once）
python manage.py init_locator_strategies   # 初始化 / 更新定位策略
python manage.py download_webdrivers       # 下载 Chrome / Firefox / Edge 驱动
python manage.py load_component_pack       # 从 YAML 加载 APP 组件包（--overwrite）
```

调度日志：`logs/scheduler.log`。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [数据工厂使用说明](./docs/数据工厂使用说明.md) | 工具与引用详解 |
| [数据工厂快速开始](./docs/数据工厂快速开始.md) | 快速上手 |
| [数据工厂功能说明](./docs/数据工厂功能说明.md) | 功能清单 |
| [数据工厂 API 接口文档](./docs/数据工厂API接口文档.md) | 接口说明 |
| [UI 自动化测试执行说明](./docs/UI自动化测试执行说明.md) | 执行指南 |
| [UI 自动化测试用户使用手册](./docs/UI%20自动化测试用户使用手册.md) | 用户手册 |
| [WebDriver 驱动管理优化说明](./docs/WebDriver驱动管理优化说明.md) | 驱动管理 |
| [APP 自动化快速开始](./docs/APP/APP自动化快速开始.md) | APP 入门 |
| [APP 自动化集成说明](./docs/APP/APP自动化集成说明.md) | 集成说明 |
| [用例评审管理功能说明](./docs/用例评审管理功能说明.md) | 评审 |
| [I18N 国际化使用说明](./docs/I18N国际化使用说明.md) | 多语言 |
| [问题排查指南](./docs/问题排查指南.md) | 排障 |
| [tester.md](./docs/tester.md) / [tester_pro.md](./docs/tester_pro.md) | AI 提示词模板 |

仓库内 `AGENTS.md` / `CLAUDE.md` 供开发与 AI Agent 快速理解架构与常用命令。

---

## 常见问题

**Q: APP 投屏卡顿或不更新？**  
A: 请用 `daphne` 启动并确保 Redis ≥ 5；`runserver` 无 WebSocket。检查 Channels 启动日志是否降级为 InMemory。

**Q: 页面扫描很慢或提示繁忙？**  
A: 扫描为异步任务且限制并发 Chromium；等待当前任务完成或调大 `UI_SCAN_MAX_CONCURRENT`（注意机器资源）。

**Q: 扫描提示不允许内网地址？**  
A: 为 SSRF 防护，默认拒绝 localhost / 私网 / 云元数据 URL。

**Q: UI 自动化找不到浏览器驱动？**  
A: 执行 `python manage.py download_webdrivers`，或在配置中心安装 Playwright 浏览器。

**Q: Appium / 中文输入导致 App「闪退」？**  
A: 录制路径已避免准备阶段按 HOME；请使用较新代码，并确认按需启动 Appium 时 `steal_focus=False`。

**Q: MySQL / venv 找不到？**  
A: Windows 需将 MySQL `bin` 加入 PATH；务必激活项目 `venv` 后再执行 `manage.py`。

---

## 许可证

本项目遵循 [GPL v3](./LICENSE)。
