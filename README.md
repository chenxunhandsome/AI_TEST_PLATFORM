# TestHub 智能测试管理平台

TestHub 是一个基于 `Django 4.2 + Vue 3` 的测试管理平台，覆盖测试资产管理、API 测试、UI 自动化测试、APP 自动化测试、需求分析、用例评审、报告统计和统一通知等能力。

当前仓库同时包含后端服务、前端页面、自动化执行能力以及辅助文档，适合用于团队级测试平台搭建与二次开发。

## 项目概览

- 后端框架：`Django 4.2`、`Django REST Framework`
- 前端框架：`Vue 3`、`Element Plus`、`Pinia`
- 数据库：`MySQL`
- 自动化能力：
  - API 测试
  - Web UI 自动化测试
  - APP 自动化测试
- AI 能力：
  - 需求文档分析
  - 测试用例生成
  - Browser Use 智能模式

## 核心功能

### 1. 测试资产管理

- 项目管理、版本管理、成员协作
- 测试用例管理、步骤维护、附件与评论
- 测试套件组织与执行编排
- 测试执行记录与报告追踪

### 2. API 测试

- API 项目、接口集合、请求定义
- 环境变量与请求历史
- 测试套件执行与定时任务
- 通知推送与操作日志

### 3. UI 自动化测试

- UI 项目管理
- 元素管理与元素分组
- 页面对象管理
- 脚本管理
- 测试用例管理
- 测试套件、执行记录、截图、报告
- 定时任务与通知配置
- AI 智能测试模式

### 4. APP 自动化测试

- APP 元素管理
- APP 测试用例与执行
- 本地执行与报告查看

### 5. AI 需求分析与用例生成

- 上传需求文档进行分析
- 自动提取业务需求与测试点
- 生成测试用例初稿
- 支持多模型配置

### 6. 用例评审

- 评审任务管理
- 模板管理
- 评审意见记录
- 评审流程跟踪

### 7. 统一通知与调度

- 邮件通知
- Webhook 通知
- API 测试、UI 自动化、APP 自动化统一调度

## 目录结构

```text
testhub_platform-main/
├── apps/
│   ├── api_testing/            # API 测试模块
│   ├── app_automation/         # APP 自动化模块
│   ├── assistant/              # 智能助手
│   ├── core/                   # 核心能力与统一配置
│   ├── data_factory/           # 数据工厂
│   ├── executions/             # 执行管理
│   ├── projects/               # 项目管理
│   ├── reports/                # 报告统计
│   ├── requirement_analysis/   # AI 需求分析
│   ├── reviews/                # 用例评审
│   ├── testcases/              # 测试用例管理
│   ├── testsuites/             # 测试套件管理
│   ├── ui_automation/          # UI 自动化测试
│   ├── users/                  # 用户管理
│   └── versions/               # 版本管理
├── backend/                    # Django 项目配置
├── docs/                       # 说明文档
├── frontend/                   # Vue 3 前端
├── manage.py
└── README.md
```

## 快速开始

### 1. 环境要求

- Python `3.12`
- Node.js `18+`
- MySQL `8+`

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制环境变量模板并按实际情况修改：

```bash
cp .env.example .env
```

Windows 环境也可以直接复制 `.env.example` 为 `.env` 后手工编辑。

### 4. 初始化数据库

```bash
python manage.py migrate
```

### 5. 初始化 UI 自动化定位策略

```bash
python manage.py init_locator_strategies
```

### 6. 启动后端

```bash
python manage.py runserver
```

### 7. 启动前端

```bash
cd frontend
npm install
npm run dev
```

## 常用命令

### 后端

```bash
python manage.py runserver
python manage.py migrate
python manage.py init_locator_strategies
python manage.py run_all_scheduled_tasks
```

### 前端

```bash
cd frontend
npm install
npm run dev
npm run build
```

## UI 自动化项目协作与权限管理

本次已补充 UI 自动化模块的项目协作权限能力，支持将其他用户加入到 UI 自动化项目中，并共同维护元素和测试用例。

### 功能说明

- UI 自动化项目负责人可以在 `UI自动化 -> 项目管理` 页面创建项目成员。
- 负责人可以编辑项目基本信息，并维护项目成员列表。
- 项目成员加入后，可以访问并维护该项目下的：
  - 元素
  - 页面对象
  - 脚本
  - 测试用例
  - 测试套件
  - 执行记录
- 普通成员不能修改项目成员列表，也不能删除项目。

### 权限规则

- 项目负责人：
  - 可以创建、编辑、删除 UI 自动化项目
  - 可以添加或移除项目成员
- 项目成员：
  - 可以访问自己参与的 UI 自动化项目
  - 可以共同维护该项目下的元素和测试用例
  - 不允许修改项目配置和成员
- 后端会校验项目访问权限，避免向无权限项目写入元素或测试用例

### 前端入口

- 页面路径：`前端 -> UI自动化 -> 项目管理`
- 支持：
  - 新建项目时选择成员
  - 编辑项目时调整成员
  - 详情页查看负责人和成员列表

## 主要模块说明

### `apps.projects`

- 通用项目管理
- 项目成员与角色模型

### `apps.testcases`

- 手工测试用例管理
- 用例步骤、附件、评论

### `apps.api_testing`

- API 项目与接口资产
- 接口测试执行与调度

### `apps.ui_automation`

- UI 自动化项目
- 元素、页面对象、脚本、测试用例、测试套件
- 执行记录、截图、定时任务、通知日志

### `apps.app_automation`

- APP 自动化元素与用例
- 本地执行与结果输出

### `apps.requirement_analysis`

- 需求文档上传与解析
- AI 测试用例生成

### `apps.reviews`

- 评审任务
- 评审模板
- 评审记录

### `apps.core`

- 统一通知配置
- 统一调度命令
- UI 自动化初始化命令

## 相关文档

- [UI 自动化测试执行说明](./docs/UI自动化测试执行说明.md)
- [UI 自动化本地执行说明](./docs/UI自动化本地执行说明.md)
- [APP 自动化快速开始](./docs/APP/APP自动化快速开始.md)
- [WebDriver 驱动管理优化说明](./docs/WebDriver驱动管理优化说明.md)
- [问题排查指南](./docs/问题排查指南.md)

## 开发建议

- UI 自动化、API 测试、APP 自动化三个模块都存在各自独立的数据模型和接口，新增能力时优先沿用各模块自己的权限边界。
- 如果要继续扩展项目协作能力，建议统一抽象“负责人/成员/只读成员”等角色体系，再复用到 API 测试和 APP 自动化模块。
- 前端项目页的成员选择，建议复用统一用户列表接口，避免不同模块维护重复用户源。

## 许可证

本项目使用 `MIT License`。

