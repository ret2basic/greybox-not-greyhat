# InferForge v2 白盒审查工作流

## 目标

这份工作流描述如何让人工研究员或 Agent 在有源码的前提下，从全仓攻击面走到可
复核 finding。它强调覆盖、证据和本地验证，不追求一次扫描输出最多告警。

## Phase A：固定审查身份

1. 记录 source root 对应的仓库、branch、commit 和 dirty 状态。
2. 确认 vendored/generated/fixture 目录是否应排除。
3. 在 inferforge.json 声明关键 trust boundary，例如 admin、wallet、billing、
   webhook、file processing 或 tenant isolation。
4. 运行 doctor。

如果源码不是实际部署版本，必须把版本相关性作为外部 blocker；扫描器不能替你推断
production equivalence。

## Phase B：建立攻击面

运行 scan 后按以下顺序查看：

1. inventory.json：coverage 是否 complete，是否跳过关键文件；
2. routes.json：入口总量、状态变更入口、动态 identifier；
3. topology.json：route 是否能进入 service/worker；
4. signals.json：未链接的危险 sink；
5. candidates.json：直接数据流和外部 SARIF 线索；
6. review-plan.json：排序后的实际工作；
7. coverage.json：每条 route 尚未关闭的 lane。

不要用 candidate 数量衡量仓库安全。一个零 candidate、很多 open route 的扫描是
“尚未完成审查”，不是“没有漏洞”。

## Phase C：逐任务深挖

每轮只领取一个 task，生成 context packet。沿源码回答：

- 外部输入在哪里产生，类型和身份是什么；
- route 前后的 middleware/guard 是什么；
- caller 是否经过 alternate mount、internal API、queue 或 cron；
- 对象从哪里加载，owner/tenant 如何绑定；
- 危险操作之前有哪些校验，是否真正作用于最终值；
- error、retry、batch、cache、race 和 rollback 是否改变不变量；
- 影响资产和攻击者前置能力是什么。

如果 native topology 不完整，使用 rg、语言 server、IDE、Semgrep 或 CodeQL 扩大
调用链，但把最终关键位置写回 evidence。

## Phase D：设计验证

优先顺序：

1. 已有单元测试旁新增负面对照；
2. framework test client 的集成测试；
3. service/handler 的最小 harness；
4. property/fuzz test；
5. 本地容器或临时环境；
6. 只有前面无法表达时，才由人工使用浏览器或代理辅助。

验证至少包含：

- 一个攻击输入；
- 一个预期被拒绝的负面对照；
- 一个合法输入不被破坏的回归对照；
- 可观察的安全 end effect；
- 固定依赖和 fixture；
- 不触碰生产或第三方。

InferForge 本身不执行这些测试命令。Agent 应按仓库契约和授权运行，然后把稳定的
测试引用记录到 review/triage。

## Phase E：关闭 gap

review completed 不是“我读过了”。它需要：

- 精确源码证据；
- 结论说明；
- 独立验证引用。

not-applicable 也需要源码证明，例如该 route 只读、没有对象 identifier，或控制在
统一 middleware 中已经覆盖。不能因为“没发现问题”而关闭。

重新 scan 后检查 coverage closure。所有 route evidence-closed 才能声明本轮白盒
覆盖完成；若 inventory incomplete，则仍不能作全仓完成声明。

## Phase F：候选判断

### rejected

记录候选为何不成立，尤其是：

- 输入并非攻击者控制；
- sink 不可达；
- 最终值由 server-owned map 决定；
- sanitizer 对当前上下文确实完整；
- framework 在更早层强制阻断；
- 影响不越过攻击者自身权限。

### confirmed

确认前复核：

- source root 和部署版本边界；
- 攻击者模型；
- 正例、负例和合法回归；
- 跨租户/跨用户/跨信任域的影响；
- 现有控制与绕过机制；
- Impact 和 Likelihood；
- 修复位置和回归测试。

### fixed

fixed 需要修复源码位置和回归测试；仅有 commit message 或开发者说明不够。

## Phase G：报告

report 只输出 confirmed。生成后仍应人工补充：

- 精确部署/版本证据；
- 业务资产与最坏可信影响；
- PoC 前置条件；
- 必要的日志/截图/请求响应附件；
- 修复建议与兼容性影响。

不要把完整 scan corpus、secret、客户源码或不相关 candidate 放进外部报告。
