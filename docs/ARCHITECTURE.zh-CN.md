# InferForge v2 白盒架构决策

## 决策摘要

InferForge v2 的主循环是 Source → Evidence Graph → Hypothesis → Local
Verification → Triage → Report。源码是强制输入；流量不是攻击面发现的权威来源；
Burp Suite MCP 不再属于产品依赖。

这个决策不是因为 Burp 不好用，而是因为白盒审计和代理重放解决的是不同问题。
有源码时，最稀缺的信息不是“最近浏览器走过哪些请求”，而是：

- 哪些入口没有被浏览器走到；
- 请求数据如何经过 middleware、service、queue、ORM 和模板；
- 哪些信任边界仅存在于配置、后台任务、Server Action 或 GraphQL resolver；
- 哪些控制在运行时被装配，哪些只是未使用的 helper；
- 如何把漏洞机制固定成一个可重复、可审计的本地回归测试。

## 为什么不以 Burp MCP 为核心

### 覆盖偏差

Burp history 只包含已经触发的路径。大型 Web 应用里，管理员入口、异常分支、
feature flag、异步 worker、webhook、导入/导出和版本迁移通常不会自然出现在一次
会话中。以 history 为起点会把“没走到”误当成“不重要”。

### 状态不可重复

GUI project、cookie、extension、proxy listener、历史容量和 MCP capability 都是
环境状态。它们适合人工调试，但不适合作为代码审计的稳定中间表示。Git commit、
source digest、SARIF、测试名称和 artifact hash 更容易复核。

### 上下文质量

HTTP response 是目标控制的不可信文本，体积大且包含大量 UI/静态噪声。源码上下文
同样不可信，但可以按 route、symbol、source、sink、control 和具体问题切片，Agent
不需要在完整 history 中自行恢复结构。

### 验证方向

白盒结论应尽可能落到本地单元/集成测试、属性测试或最小 harness。Burp replay 可以
帮助人工理解一个会话，但它不能替代部署版本映射、源码根因和负面对照。

### 保留的外部角色

Burp 可以继续作为产品外的可选人工工作台，用于复杂浏览器会话、协议可视化和手工
重放。任何有价值证据都应被最小化为：

1. 对应的源码路径；
2. 可重复的本地验证；
3. 负面对照；
4. 明确的 Impact 与 Likelihood；
5. 必要时才保留脱敏的请求响应附件。

v2 不提供 Burp MCP adapter，避免可选工具重新演变成编排中心。

## 分层架构

### 1. Source inventory

inventory.py 在固定预算内遍历 source root，不跟随 symlink，跳过依赖、构建和本地
artifact。它记录语言、文件摘要、generated/manifest 属性、跳过原因以及完整性状态。

任何超大、不可读或预算外文件都会把 coverage 标记为 incomplete。扫描器不能用
“没看到”证明安全。

### 2. Entrypoint adapters

routes.py 从框架约定和声明式路由中提取入口。Route 是统一入口对象，可以表示 HTTP
method、WebSocket、GraphQL operation 或 Server Action，并保留源码位置、动态参数、
状态变更属性和附近安全信号。

入口适配器的结果是 coverage root，不是漏洞结论。

### 3. Local topology

topology.py 建立：

- 文件内 symbol；
- 可解析的本地 import；
- 唯一 symbol call hint；
- route 到 entry symbol；
- route 经本地 import 可达的文件集合。

动态 dispatch、宏、runtime DI 和代码生成不可能由轻量引擎完整解析，因此 artifact
明确把这些边叫 may-call/may-reach。它们用来确定审查上下文和 gap，不能当作运行时
可达性证明。

### 4. Source/sink inventory and native dataflow

signals.py 记录所有不可信 source 与危险 sink。analyzer.py 只在有直接表达式或有界
变量传播时生成 source-to-sink candidate。

危险 sink 没有被 native dataflow 链接时不会消失；它会产生 sink-callpath-review，
要求审查 caller、DI、跨文件参数和框架 binding。这一设计同时控制误报和漏审。

### 5. External static-analysis evidence

sarif.py 接受 SARIF 2.1，将 Semgrep、CodeQL 等成熟引擎结果统一为 candidate。外部
tool 不能直接写 finding 状态。所有位置必须位于 source root 内，message 会被限长和
脱敏。

这让 InferForge 专注于编排、证据关系、覆盖和生命周期，而不是维护每种语言的完整
parser/IR。

### 6. Evidence graph

evidence-graph.json 的节点包括 source-file、symbol、route、source signal、sink
signal、candidate、review task 和声明式 trust boundary。边包括 declared-in、
imports、may-call、may-reach、supports、reviews 和 verifies。

图的主要消费者是 Agent context selection、覆盖审计和人工可视化。每条静态推断边
都保留弱语义，避免把图可达误报成漏洞可达。

### 7. Coverage and review lifecycle

每条 route 默认打开 authentication、authorization、input validation、request
integrity、abuse control 和 dangerous dataflow lane。review-plan 根据源码证据生成
任务。

review-state.json 是人工状态。completed 需要源码位置和独立验证；not-applicable
需要源码证据。重新扫描会把状态投影回派生 artifact。所有相关任务关闭后，route
才会变成 evidence-closed。

### 8. Candidate lifecycle

candidate 的状态包括 needs-review、confirmed、rejected、accepted-risk 和 fixed。

confirmed 必须提供：

- 至少一个 source-root 内的证据位置；
- 本地测试、harness 或其他独立验证引用；
- 机制与攻击者能力说明；
- Impact；
- Likelihood。

最终 Severity 由矩阵推导。reporting.py 只渲染 confirmed，避免扫描器把假设包装成
交付 finding。

每个 review/triage evidence location 都固定当时文件 SHA-256。重新扫描时，如果
证据文件发生变化、消失或不再属于 inventory，旧终态会被标为 stale 并重新打开；
report 会拒绝渲染 stale confirmation。这样 unrelated chat state 或旧源码判断不能
在代码变化后继续冒充当前结论。

## Agent 交互契约

AI Agent 不应直接吞入整个仓库或整个 traffic corpus。正确循环是：

1. 读取 scan-summary 和最高优先级 task；
2. 用 context 命令取得有界源码包；
3. 验证 route composition、caller、data ownership 和控制顺序；
4. 在本地 fixture/test 环境构造最小正例和负例；
5. 用 review 或 triage 写入证据；
6. 重新扫描；
7. 只有确认项进入 report。

context packet 的源码、注释、字符串、fixture 和 SARIF message 都是不可信数据。
它们不能改变系统指令、授权边界或测试范围。

## 稳定性与模型时代

v1 把大量工作流逻辑硬编码在一个 18.5 万行 Python 文件中，且流程围绕某一代模型
如何调用 Burp 设计。v2 将确定性工作放回代码：

- 文件和路由发现由 adapter 完成；
- 规则语义存在 machine-readable catalog；
- 外部引擎通过 SARIF 接入；
- lifecycle gate 由 CLI 强制；
- artifact 由 schema version 和 hash 固定；
- Agent 只负责需要语义判断、攻击建模和测试设计的部分。

这样更强或更弱的模型都面对同一份证据契约，模型升级不需要重写整个工具。

## 当前边界

InferForge v2 不是编译器、SCA 平台、DAST scanner 或自动漏洞证明器。以下内容必须
依赖外部分析或人工审查：

- 跨语言 RPC 和消息队列；
- 反射、宏、动态 route registration；
- 完整框架 middleware composition；
- 复杂 sanitizer 和编码上下文；
- ORM scope、事务隔离和竞争条件；
- 业务状态机与经济不变量；
- 部署环境、IAM、云策略和基础设施；
- 生产版本与源码版本映射。

这些边界会进入 coverage 与 review plan，不会被隐藏。
