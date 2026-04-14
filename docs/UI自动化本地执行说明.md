# UI 自动化本地执行说明

## 变更目标

原来的 UI 自动化执行链路是：

1. 访问者在页面点击“运行”
2. 后端 Django 直接启动 Playwright / Selenium
3. 浏览器实际运行在部署机器上

现在改为：

1. 访问者在页面选择“本机执行”
2. 后端只创建待执行任务，并把任务指派给访问者自己的本地 runner
3. 本地 runner 在访问者电脑上领取任务
4. Playwright / Selenium 在访问者电脑上真正启动浏览器
5. 执行结果回传到平台并写入执行记录

## 涉及范围

- UI 自动化单用例手工执行
- UI 自动化执行记录页重跑

当前未改造：

- UI 自动化测试套件的本地执行
- UI 自动化定时任务的本地执行

这两类仍然走服务端执行链路。

## 访问者电脑需要做什么

访问者电脑必须具备以下条件：

- 已拉取本项目代码
- 已安装项目 Python 依赖
- 已安装本机需要使用的浏览器
- 若使用 Playwright，已执行 `playwright install`
- 若使用 Selenium，已具备对应浏览器和驱动环境

## 启动本地 runner

在访问者自己的电脑上进入项目根目录后执行：

```powershell
venv\Scripts\python.exe apps\ui_automation\local_runner.py --server http://你的部署机器:8000 --username 你的用户名 --password 你的密码
```

示例：

```powershell
venv\Scripts\python.exe apps\ui_automation\local_runner.py --server http://192.168.1.20:8000 --username zhangsan --password 123456
```

启动成功后，runner 会：

- 登录平台
- 注册当前机器为一个“本地执行器”
- 定时发送心跳
- 轮询领取指派给当前用户当前机器的 UI 自动化任务

## 页面上如何使用

### 单用例页面

在 `UI自动化 -> 测试用例` 页面：

1. 选择引擎
2. 选择浏览器
3. 选择有头/无头
4. 把执行位置切换为“本机执行”
5. 选择在线的本地执行器
6. 点击运行

### 执行记录页重跑

在 `UI自动化 -> 执行记录` 页面重跑时：

1. 选择执行位置为“本机执行”
2. 选择本地执行器
3. 提交重跑

## 当前新增接口

- `GET /api/ui-automation/local-runners/`
- `POST /api/ui-automation/local-runners/register/`
- `POST /api/ui-automation/local-runners/heartbeat/`
- `POST /api/ui-automation/local-runners/claim/`
- `POST /api/ui-automation/local-runners/report/`

## 数据结构变更

### `TestCaseExecution`

新增字段：

- `execution_mode`
- `assigned_runner`

### `LocalRunner`

新增模型，用于表示某个用户在某台机器上启动的本地执行器。

## 迁移

部署后需要执行：

```powershell
venv\Scripts\python.exe manage.py migrate
```
