# TestHub AI 智能测试平台实施状态（可恢复检查点）

> 文件职责：记录“现在做到哪里、验证过什么、下一步是什么”的短期可变状态。  
> 规范来源：[AI_INTELLIGENT_TESTING_PLATFORM_DESIGN.md](./AI_INTELLIGENT_TESTING_PLATFORM_DESIGN.md) 是唯一设计 SSOT；本文件不得覆盖其 DEC/FR/AC/安全约束。  
> 更新规则：每次开始工作、上下文即将压缩、准备关机、长任务暂停和结束回复前都必须更新。  
> 安全规则：禁止写入密码、PAT、API Key、Cookie、storage state、client secret 或敏感原文。

---

## 1. 恢复启动协议

新的人工或 AI 会话必须按顺序执行：

1. 完整读取本文件。
2. 首次参与项目时完整读取设计 SSOT；后续至少读取 SSOT 第 0、14、18、19、20、21 节及当前 WP 引用章节。
3. 执行 `git status --short` 和 `svn status`，把已有改动视为用户资产，不回退、不覆盖。
4. 核对 `design_version`、`active_wp`、blocker 和 `next_actions`。
5. 只推进第一个未完成且未阻塞的 next action；完成后更新本文件和 SSOT 第 20.5 节。
6. 没有测试/探测证据不得把 WP 标记为 `DONE`。

---

## 2. 当前机器可恢复状态

```yaml
state_schema_version: 1.0.0
last_updated: 2026-07-17T10:11:37+08:00
design_version: 1.6.1
active_wp: null
wp_status: WP-001_DONE_WP-101_READY
implementation_started: true
parameter_discovery_started: false
current_owner: root + user
last_completed_wp: WP-001
next_ready_wp: WP-101
primary_vcs: svn
mirror_vcs: git
vcs_mode: svn_authoritative_git_mirror
```

时间戳由下次实施会话更新为真实保存时间；以上状态内容比聊天历史优先，但低于 SSOT。

### 当前目标

`WP-001` 已完成：版本化、脱敏、确定性的 cassette/Web/security 黄金包和首个基线报告全部通过。M0 基线已就绪，下一入口为 `WP-101`，建立 `knowledge`、`ai_orchestration` app、配置、health check 与默认关闭的 feature flags。

### 已确认的环境

- Django 4.2 + Vue 3 现有平台，包含 requirement analysis、UI automation、Playwright、页面图谱、AI 用例 Skill 和 MCP 能力。
- Neo4j `5.26.2 Community`：HTTP 7474、Bolt 7687、默认数据库认证只读验证成功；秘密未写入文件。
- Ollama `qwen3-embedding:0.6b`：595.78M Q8_0、1024 维，2 条冷启动和 16 条热批次 embed 调用成功。
- Qdrant：localhost:6333 当前未运行；用户允许后续使用 Docker 部署。
- 内部 GPT：数据库已有活动 writer/reviewer 配置，模型别名 `gpt-5.6-sol` 且凭证存在；未输出/保存 API Key。
- 模型策略：全部基线 role 使用 GPT；reviewer 使用隔离 Prompt/Run，Claude 仅可选 challenger，不是依赖。
- 被测系统：用户独占环境，允许 SUT 内任意操作；跨系统邮件/短信/Webhook/支付仍需 allowlist。
- 知识规模：PIMC 共 52,205 Issue，其中测试用例 24,678；容量按 10 万～100 万 chunk 规划。
- Jira：`https://jira.dms365.com`，版本 11.3.6，HTTPS/HSTS 正常，REST v2 未认证返回 401；无 Xray/Zephyr 等测试管理插件。
- Confluence：`https://conf.dms365.com`，版本 10.2.7，HTTPS/HSTS 正常，`/rest/api/space` 未认证返回 401。
- Atlassian 凭证位于 `.env` 最后四行，变量名为 `CONFLUENCE_NAME/CONFLUENCE_TOKEN/JIRA_NAME/JIRA_TOKEN`，且 `.env` 已加入 SVN ignore；只允许检查变量存在性和执行只读认证，任何会话不得输出值。
- 用户已确认旧 Jira/Confluence PAT 均已撤销；`.env` 中轮换后的 Jira/Confluence PAT 均已通过不回显的只读认证。2026-07-17 新 Confluence PAT 的身份接口与批准范围 P331/66978175 均返回 200。
- 首批 Jira 范围严格限定 `PIMC`：需求 1,625、测试用例 24,678、测试计划 37、缺陷 24,193，另有任务/技术预研/分解任务。
- PIMC 安装有效许可 SynapseRT，REST 基址 `/rest/synapse/latest/`；只读 adapter 必须覆盖 suite/step/plan/cycle/run/requirement/bug 关系并拒绝写/执行/AI endpoint。
- 首批 Confluence 范围严格限定 `P331` 根页面 `66978175`（探测版本 144）；child/page、附件、评论、restriction 可用，descendant/page 返回 500，递归使用 BFS。
- 公司门户：HTTP-only，HTTPS 443 拒绝，页面和认证 API 都不安全；未向门户提交真实凭证。

### 已完成的安全探测

- Jira 本地 HTTPS 登录只使用门户凭证验证一次，返回凭证错误；未重试、未保存 session、未读取/修改 Issue。
- 门户未认证 `client-info` 响应出现非空 `clientSecret` 字段；实际值已遮罩且未保存/使用，建议报告公司门户维护方。
- 用户在聊天中发送过门户密码；应建议用户轮换，任何项目文件不得记录该值。

### 当前 blocker / 安全待办

1. `WP-101` 当前无外部 blocker；SVN 同步按用户要求等待公司网络/代理恢复，不影响本地实现和验证。
2. 用户尚未确认聊天中暴露的门户密码是否已轮换；平台不使用该密码，此项不阻塞 `WP-101`，但仍应尽快完成。
3. 浏览器目标并发、生产对象存储实例和证据保留期尚未最终确认，但不阻塞基础代码骨架。

### 下一步动作（严格按顺序）

1. 完成 `WP-001` 的路径级 Git 提交与远端推送；SVN 保持待同步，不发起网络连接。
2. 开始 `WP-101` 前盘点 Django settings、URL、health check 和现有 app 命名边界。
3. 创建 `knowledge`、`ai_orchestration` app 骨架与默认关闭的 feature flags，关闭时现有行为必须不变。
4. 添加配置/health/flag 测试并重跑黄金集、既有 40 tests、Django/migration check 和 Vue build。

---

## 3. 工作树保护

- 设计开始前仓库已经存在用户未提交的 `apps/ui_automation`、相关 frontend 页面和其他本地文件改动。
- 本项目新增/更新了：
  - `docs/AI_INTELLIGENT_TESTING_PLATFORM_DESIGN.md`
  - `docs/AI_IMPLEMENTATION_STATE.md`
- 任何恢复会话都必须重新执行 Git/SVN 状态检查；本节不是实时状态的替代。
- 未经用户明确授权，不自动 commit、push、svn commit、回退或清理工作树。
- 用户已选择 SVN 为权威主线，并于 2026-07-17 要求后续内容同步到 Git。每个本项目提交必须使用相同 WP ID，先提交 SVN、再提交 Git 镜像，并记录两边 revision/hash；任一侧失败时在本文件记录 divergence，修复前不得声称已同步。
- 禁止 `git add .` 或无目标的递归 SVN commit；只暂存/提交当前工作包明确归属的文件，保护两套工作树中的既有用户改动。
- 根目录 `svn:ignore` 已加入 `.env`，`svn status .env` 应显示 `I`；两份上下文文档已 `svn add`。根目录属性变更和文档尚未 commit。

---

## 4. 最近一次验证证据

```yaml
document_structure:
  design_sections: 25
  markdown_fences_balanced: true
neo4j:
  version: 5.26.2
  edition: community
  authenticated_read: passed
ollama_embedding:
  model: qwen3-embedding:0.6b
  dimensions: 1024
  batch_16: passed
qdrant:
  localhost_6333: not_running
jira:
  https: passed
  hsts: passed
  rest_api_v2_unauthenticated: 401_expected
  portal_credential_local_login: failed_once_no_retry
  pat_authenticated_read: passed
  env_pat_differs_from_chat_exposed_value: true
  old_pat_revocation_confirmed: true
  accessible_projects: 385
  issue_types: 23
  fields: 174
  selected_project: PIMC
  selected_project_total: 52205
  test_cases: 24678
  test_plans: 37
  requirements: 1625
  defects: 24193
  synapsert_license: valid
  synapsert_rest_discovery: passed_static_read_only
confluence:
  https: passed
  hsts: passed
  rest_api_space_unauthenticated: 401_expected
  pat_authenticated_read: passed_rotated_token
  old_pat_revocation_confirmed: true
  rotated_pat_identity_status: 200
  rotated_pat_scope_status: 200
  pagination: passed
  selected_space: P331
  root_page_id: 66978175
  root_page_version: 144
  child_page_bfs: required
baseline:
  django_check: passed
  migration_check: passed_no_changes_detected
  app_automation_migration_0003: 24_metadata_only_alterfield_applied_in_clean_test_db
  requirement_analysis_tests: 4_passed
  ui_ai_mcp_tests: 36_passed
  wp_002_target_tests: 40_passed
  frontend_build: passed_with_existing_bundle_warnings
golden_baseline:
  bundle_version: 1.0.0
  manifest_sha256: d9e773e450718711e53d7e5fb7b6732ea8e81680f85849e58b5d5856b745d793
  manifest_files: 18
  cassettes: 3
  security_cases: 27
  web_states: 8
  web_edges: 10
  contract_tests: 8_passed
  combined_regression_tests: 48_passed
  report: docs/baselines/WP-001_GOLDEN_BASELINE.md
svn:
  primary: true
  env_ignored: true
  context_docs_scheduled_add: true
  committed: false
  commit_deferred_by_user: true
  defer_reason: corporate_network_proxy_unavailable
  last_attempt: timed_out_no_revision
  working_copy_lock_cleaned: true
git:
  mirror_enabled: true
  branch: main
  context_docs_tracked: true
  design_checkpoint_commit: 9c528c9
  wp_002_commit: 9e28eaa
  committed: true
  remote_push: passed_direct_without_persistent_proxy_change
  remote_head_at_last_verification: 3d135dd
  wp_001_commit: 3d191e7
  wp_001_remote_sync: passed
portal:
  http: reachable
  https_443: refused
  secure_context: false
  real_credential_submitted: false
```

---

## 5. 会话交接记录

### 2026-07-17 / WP-001 完成 → WP-101 READY

- 建立 `tests/golden/v1` bundle 1.0.0：18 个 manifest/hash 保护文件、Jira/Confluence/SynapseRT 三类 cassette、27 个安全案例、8 状态/10 边 Web 真值图。
- cassette 全部 synthetic/sanitized/read-only，并严格限制 PIMC、P331/66978175；SynapseRT 写/执行/克隆/删除/AI endpoint fail closed。
- 建立 loopback-only 可控 Web server，覆盖 route/login/tab/modal/form/pagination/dynamic ID/loop/risk/prompt injection。
- 篡改 hash、跨项目 Issue、非脱敏字段、ACL、prompt injection、SSRF 和危险动作均有故障注入测试。
- 验收通过：8/8 golden tests、48/48 合并回归、Django check、migration check、Vue build；报告为 `docs/baselines/WP-001_GOLDEN_BASELINE.md`。
- 当前工作包 Git 主提交为 `3d191e7`，完成检查点为 `3d135dd`；两者已推送到 `origin/main`。SVN 继续按用户要求等待网络恢复。

### 2026-07-17 / WP-001 开始

- 用户授权开始 WP-001，并允许推送当前 `main` 领先远端的全部 5 个提交。
- 默认本地 Git 代理未运行导致首次 push 失败；使用仅本次命令生效的空代理参数直连成功，未修改全局配置，`origin/main` 已更新到 `ea3f713`。
- WP-001 只建立脱敏 fixture、cassette 契约、安全黄金集和基线报告，不提前实现 WP-203～205 正式连接器。
- 仓库没有现成 golden/cassette 框架；采用 Python 标准库和 Django/`unittest` 可离线运行，避免引入新的网络测试依赖。

### 2026-07-17 / WP-002 完成 → WP-001 READY

- requirement fixture 已补 `Project.owner`；4/4 测试通过。
- UI AI 两个失败已以三个最小 hunk 修复：业务流草稿保留“创建类流程”标题语义，结构化数据要素重建 warning 明确包含“数据要素创建流程”；用户其他生成器改动未覆盖。
- app_automation `0003` 对齐 24 个仅元数据 `AlterField`；无 Add/Remove/Create/Delete/SQL/Python 操作，在干净测试库应用成功，migration check 无漂移。
- 验收通过：目标 40/40 tests、Django check、migration check、Vue build。Vue 仅保留既有 bundle/tree-sitter 警告。
- Git 设计检查点已本地提交为 `9c528c9`；`WP-002` 代码提交为 `9e28eaa`。SVN 与远端 Git 按用户要求等待网络/范围条件。

### 2026-07-17 / WP-002 开始

- 用户确认旧 Jira/Confluence PAT 已撤销；轮换后的 Confluence PAT 通过身份与 P331/66978175 最小只读验证，均返回 200。
- 用户授权提交本轮设计文档到 SVN，并要求后续内容同步到 Git；采用 SVN 权威主线 + Git 镜像，按工作包进行路径级提交。
- SVN 连接连续超时且未产生 revision；用户随后明确要求网络/代理恢复前不提交 SVN。本地 working-copy lock 已清理，待办保留。
- `WP-002` 已切换为 `IN_PROGRESS`；第一动作是检查目标测试、生成器和 migration 的现有改动归属。
- 门户密码轮换尚未确认，作为非阻塞安全待办保留；平台不使用该密码。

### 2026-07-16 / WP-000 完成 → WP-002 READY

- 完成完整 SSOT 设计、工作包、验收和上下文协议。
- 根据用户环境更新到设计 v1.4.1。
- 完成 Neo4j、Ollama、GPT 配置、Atlassian 地址/TLS/未认证 REST 的只读探测。
- Jira PAT 从 `.env` 安全读取且与聊天暴露值不同；Confluence PAT 只读探测虽成功但仍是聊天暴露值，已记录必须撤销替换；PIMC/P331 范围、SynapseRT 与分页能力已完成只读探测。
- SVN 已确认为主 VCS，`.env` 已 ignore，两份上下文文档已 schedule add，未 commit。
- 基线发现 migration drift、4 个 fixture error 和 2 个 UI AI test failure；Vue build/Django check 通过。
- 下一会话从 WP-002 开始，不重复 Neo4j/Ollama/Atlassian/基线探测。

---

## 6. 用户重启后的固定续接提示词

电脑重启、对话过长或新开会话时，用户只需发送：

```text
继续 TestHub AI 智能测试平台项目。请先完整读取：
1. docs/AI_IMPLEMENTATION_STATE.md
2. docs/AI_INTELLIGENT_TESTING_PLATFORM_DESIGN.md

然后检查 git status --short 和 svn status，保护所有已有改动；从 state 文件的 active_wp 和第一个未完成 next_action 继续。不要重做已通过的环境探测，不要依赖历史聊天，不要在输出或文件中泄露任何凭证。每次结束前更新实施状态文件和设计文档第 20.5 节。
```

如果只想询问状态而不继续开发，在末尾增加：`只汇报状态，不修改代码。`

---

## 7. 每次结束前的强制保存清单

- [ ] 更新真实 `last_updated`。
- [ ] 更新 active WP/status、已完成项、测试结果和第一个 next action。
- [ ] 把新架构决策写入 SSOT/ADR，而不是只留在聊天。
- [ ] 记录新增 migration、Prompt/Schema/collection/graph snapshot 版本。
- [ ] 记录失败命令的第一个根因和已排除原因。
- [ ] 检查文件中没有密码、Token、Cookie、client secret 或敏感原文。
- [ ] 重新检查 Git/SVN 状态，确认没有覆盖用户改动。
- [ ] 工作包完成且用户授权时，使用选定的唯一版本控制系统形成可恢复提交。
