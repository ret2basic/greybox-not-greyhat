# InferForge v2

InferForge 是一个**必须提供源码**的 Web 安全审查证据引擎。它先从仓库本身建立
入口、调用关系、信任边界、危险操作和覆盖缺口，再把这些证据切成适合人工或
AI Agent 深挖的任务。它不会把正则命中当作漏洞，也不会通过远程流量猜测应用
结构。

仓库名称 greybox-not-greyhat 是历史名称；v2 产品语义已经是纯白盒。

## 结论：Burp MCP 不再是核心

Burp Suite 仍然是一款优秀的人工 Web 测试工作台，但它不适合作为有源码审计的
编排中枢：

| 能力 | Burp/MCP 作为核心 | InferForge v2 的选择 |
| --- | --- | --- |
| 攻击面起点 | 已观察到的请求 | 源码入口、配置、路由和调用拓扑 |
| 未走到的业务分支 | 很难发现 | 直接进入覆盖台账 |
| 跨文件数据流 | 依赖 Agent 从流量反推 | 原生线索加 Semgrep/CodeQL SARIF |
| 可重复性 | 依赖 GUI 项目、历史和扩展状态 | Git 身份、源码摘要和完整性 manifest |
| 验证 | 重放线上或本地请求 | 优先生成本地测试/ harness 的验证契约 |
| AI 上下文 | 大量不可信请求响应 | 有界 source context packet |
| 无人值守 | GUI/MCP 生命周期较重 | 无第三方 Python 依赖的离线 CLI |

因此 v2 没有 Burp MCP 客户端、历史同步、Repeater 调度、远程 target、赏金目录、
资产映射或 source-free mode。需要人工调试复杂会话时，可以在产品外部使用 Burp，
但 Burp 证据必须回到本地回归测试或明确的验证记录后，才会影响 finding 状态。

完整决策见 docs/ARCHITECTURE.zh-CN.md。

## 核心流水线

    local source tree
        |
        +-- inventory and framework detection
        +-- HTTP / WebSocket / GraphQL / Server Action entrypoints
        +-- local imports, symbols, calls, route reachability
        +-- untrusted sources, dangerous sinks, nearby controls
        +-- native candidate hypotheses
        +-- optional Semgrep / CodeQL / SARIF evidence
        |
        v
    evidence graph + route coverage ledger + bounded review plan
        |
        v
    human or AI source review + local test harness + negative control
        |
        v
    explicit triage (Impact + Likelihood) and confirmed-only reports

扫描成功只证明证据构建成功，不证明应用安全。candidate 只是待验证假设；缺少
认证、授权或校验信号只是 coverage gap；只有显式完成确认契约的项目才会生成
漏洞报告。

## 快速开始

要求 Python 3.10 或更高版本。运行时没有第三方依赖。

    git clone git@github.com:ret2basic/greybox-not-greyhat.git
    cd greybox-not-greyhat
    python3 -m pip install -e .

直接审查一个本地源码仓库：

    inferforge scan --source-root /path/to/application --json

不安装包也可以使用仓库入口：

    python3 scripts/inferforge.py \
      scan \
      --source-root /path/to/application \
      --workspace /path/to/application/.inferforge \
      --json

扫描不会发出 HTTP 请求、不会操作浏览器、不会启动或管理目标进程，也不会连接
任何代理或 MCP 服务。

## 推荐工作流

### 1. 检查环境

    inferforge doctor --source-root /path/to/application

doctor 验证源码可读性、扫描预算和已有 artifact 完整性，并报告 Git、ripgrep、
Semgrep、CodeQL 是否可用。Semgrep 和 CodeQL 是可选增强，不是运行依赖。

### 2. 建立源码证据

    inferforge scan --source-root /path/to/application

默认 artifact 目录是源码根目录下的 .inferforge。可以放到仓库外：

    inferforge scan \
      --source-root /path/to/application \
      --workspace /secure/review/application

### 3. 合并成熟静态分析器

InferForge 不重新实现所有语言的编译器级数据流。让 Semgrep、CodeQL 或其他工具
生成 SARIF 2.1，然后在同一次源码扫描中合并：

    inferforge scan \
      --source-root /path/to/application \
      --sarif /tmp/semgrep.sarif \
      --sarif /tmp/codeql.sarif

SARIF 位置必须落在 source root 内；越界位置会被拒绝并记录 diagnostic。外部
结果仍是 candidate，不会绕过确认门槛。

### 4. 领取一个有界任务

查看状态和最高优先级任务：

    inferforge status --source-root /path/to/application --top 20

生成只包含相关源码片段、问题和完成证据的上下文包：

    inferforge context \
      --source-root /path/to/application \
      --id task-xxxxxxxxxxxxxxxx \
      --output /tmp/review-packet.md

上下文包明确把源代码、注释、字符串、fixture 和 SARIF message 标记为不可信数据，
避免把仓库内 prompt injection 当成 Agent 指令。

### 5. 用证据关闭覆盖任务

完成任务需要源码位置和独立验证，例如本地单元测试、集成测试或确定性的 harness：

    inferforge review \
      --source-root /path/to/application \
      --id task-xxxxxxxxxxxxxxxx \
      --status completed \
      --note "Authorization binds the loaded object to the authenticated tenant." \
      --evidence src/accounts/service.ts:84 \
      --verification tests/security/accounts.test.ts::rejects_cross_tenant_access

重新扫描后，review-plan.json 和 coverage.json 会继承记录。只有该路由所有相关任务
都完成或有证据证明 not-applicable，route closure 才会变成 evidence-closed。

### 6. 对 candidate 做生命周期判断

否决误报：

    inferforge triage \
      --source-root /path/to/application \
      --id cand-xxxxxxxxxxxxxxxx \
      --status rejected \
      --note "The apparent URL is selected from a closed server-side destination map." \
      --evidence src/proxy/destinations.ts:44

确认漏洞必须同时提供源码证据、独立验证、Impact 和 Likelihood：

    inferforge triage \
      --source-root /path/to/application \
      --id cand-xxxxxxxxxxxxxxxx \
      --status confirmed \
      --note "A tenant user controls the final outbound host and can reach internal services." \
      --evidence src/proxy/fetch.ts:91 \
      --verification tests/security/proxy.test.ts::blocks_private_destinations \
      --impact high \
      --likelihood medium

Severity 由 Impact 和 Likelihood 的固定矩阵推导，不接受脱离证据的自由标签。
每条 evidence 同时固定文件 SHA-256。后续扫描发现证据文件变化或消失时，终态不会
静默继承：candidate 会重新变成 needs-review，completed task 会重新打开，report
会扣留 stale confirmation，直到分析员用当前源码重新验证。

### 7. 只渲染已确认报告

    inferforge report --source-root /path/to/application

没有通过确认契约的 candidate 不会被包装成 finding。报告默认写到
.inferforge/reports。

## Artifact 契约

| Artifact | 用途 |
| --- | --- |
| run.json | 工具版本、Git 身份、源码摘要、无网络声明 |
| effective-config.json | 实际生效的 v2 配置 |
| inventory.json | 文件、语言、框架、跳过原因和扫描完整性 |
| routes.json | HTTP、WebSocket、GraphQL、Server Action 等入口 |
| topology.json | 符号、本地 import、唯一符号 call 和 route reachability |
| signals.json | 所有不可信 source 和危险 sink，包括尚未解析输入来源的 sink |
| rule-catalog.json | 原生规则和语义契约 |
| candidates.json | 原生与 SARIF candidate hypotheses |
| evidence-graph.json | file、route、symbol、signal、candidate、task 的证据关系 |
| review-plan.json | 按风险排序的有界审查任务 |
| coverage.json | 每条 route 的安全 lane 和证据关闭状态 |
| scan-summary.json / md | 扫描摘要与正确解释 |
| artifact-manifest.json | 所有派生 artifact 的大小和 SHA-256 |
| triage.json | candidate 生命周期记录；不会被重新扫描覆盖 |
| review-state.json | review task 关闭记录；不会被重新扫描覆盖 |
| reports/report-manifest.json | confirmed-only 报告生成清单，用于安全清除过期 finding |

运行以下命令检查派生产物是否与 manifest 一致、是否部分丢失，以及是否仍对应当前
源码/配置/引擎版本：

    inferforge verify-artifacts --source-root /path/to/application

triage.json、review-state.json 和 reports 是人工状态，不属于可重复派生的 scan manifest。
它们内部的源码证据带文件摘要，并在每次 scan/report 时与当前 inventory 对照。
verify-artifacts 还会重建当前源码与有效配置摘要；只要代码或分析配置变化，context、
status、review、triage 和 report 都会 fail closed 要求先重新 scan。
manifest 没有数字签名，不提供对拥有 workspace 写权限攻击者的真实性保证；高信任
交付应在外部对整个 evidence bundle 签名。

## 源码入口覆盖

当前内置入口适配器覆盖：

- Next.js App Router、Pages API 和 file-level Server Actions；
- SvelteKit +server 路由；
- Express、Fastify、express-ws 和通用 Node WebSocket handler；
- NestJS Controller；
- FastAPI、Flask 和 Django urlpatterns；
- Spring Web annotations；
- Laravel Route、Rails routes；
- Go net/http、Gin/Echo 风格路由；
- Rust Axum、Actix Web；
- JavaScript resolver map 和 Python Strawberry 风格 GraphQL Query/Mutation。

未知框架仍会进入文件、source、sink、import 和 SARIF 分析；路由覆盖会明确显示缺口，
不会假装完整。

## 原生规则

运行以下命令查看完整 catalog：

    inferforge rules

内置 source-to-sink 规则覆盖命令注入、SQL/查询注入、SSRF、路径穿越、XSS、开放
重定向、模板注入、动态代码执行、不安全反序列化、LDAP 注入、响应头注入、交易
签名完整性和 mass assignment。高置信静态规则覆盖 TLS/JWT 验证关闭、危险 CORS、
debug、YAML loader、硬编码密钥、cookie 属性和弱哈希。

原生引擎是有界线索生成器，不是编译器。跨模块、动态 dispatch、ORM 语义、宏、
代码生成和复杂 sanitizer 应由 CodeQL/Semgrep、自定义测试以及人工审查补足。

## 配置

生成最小配置：

    inferforge init --source-root /path/to/application

配置 schema 位于 schemas/inferforge-config.schema.json，示例位于
inferforge.example.json。可配置扫描预算、排除目录/路径、规则禁用、severity
override 和声明式 trust boundary。

v2 会 fail closed 拒绝 assessment_mode、target、burp、scope_hosts、bounty_program
等旧配置键。不存在兼容的 source-free fallback。

## 安全模型

- source root 是唯一攻击面权威来源；
- 默认跳过依赖、build、coverage、VCS、旧研究目录和本地 artifact；
- 不跟随 symlink，artifact 中不复制疑似 secret 值；
- 有文件数、单文件大小和总字节预算；预算触发会标记 coverage incomplete；
- SARIF 位置不能逃逸 source root；
- context 有最大行半径并再次脱敏；
- scanner 不执行目标代码、不安装依赖、不启动服务、不发送请求；
- 自动扫描结果永远不能自行变成 confirmed；
- 所有报告必须来自显式 evidence-backed triage。

更完整的威胁模型见 SECURITY.md。

## 开发与验证

运行完整离线验证：

    scripts/validate.sh

或分别运行：

    python3 -m compileall -q src scripts/inferforge.py tests
    PYTHONPATH=src python3 -m unittest discover -s tests -v

测试 fixture 故意包含漏洞模式，只在离线源码扫描中使用。CI 不启动 fixture，也不
产生任何网络探测。

## v1 迁移

v1 的单体 runner、Burp MCP、黑盒资产发现、赏金目录、远程 scope、主动 probe、
目标 profile 和研究交接文档已从当前产品删除。重构前公开安全检查点保留在 Git
历史 commit 6eff034，便于审计历史而不污染 v2 接口。

逐项命令迁移和不兼容说明见 docs/MIGRATION_V2.zh-CN.md。
