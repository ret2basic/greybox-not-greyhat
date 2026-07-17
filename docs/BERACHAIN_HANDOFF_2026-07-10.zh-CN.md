# BeraChain Web/Apps 挖洞阶段总结与换机交接

更新时间：2026-07-10 UTC

补充校正：2026-07-11（后续研究状态优先于原交接结论）

交接分支：`main`

公开远端：`ret2basic/greybox-not-greyhat`（Public）

## 1. 一句话状态

BeraChain Web/Apps 的 bounty scope 已完整归档，16 个显式资产均完成基础盘点；当前确认 finding 数量为 `0`。原交接时的一项 Medium 候选在补入遗漏的框架 URL 规范化语义后被否决，状态为 invalid / not reportable，禁止按旧结论提交。现有高价值项目均仍是待补生产可达性或影响证明的 lead。

## 2. 状态口径

后续继续工作时必须区分以下状态：

- **内部已验证**：本地技术证据和负面对照成立。
- **可提交**：范围、影响、PoC、生产相关性和报告材料均通过提交前复核。
- **已提交**：已经取得 Immunefi submission/ticket 记录。
- **平台确认**：项目方或平台已确认有效性、严重度或奖励。

当前没有仍然成立的“内部已验证” finding，也没有已提交或平台接受的记录。旧交接中的内部验证状态已被 2026-07-11 的负面对照 supersede。

## 3. 已完成的工作

### 3.1 Program 与 scope

- Immunefi Information、Scope、Resources 三个页面均已解析。
- Assets in Scope：`16/16`。
- Impacts in Scope：`20/20`。
- 本地程序画像状态：`ready`。
- 原 `BERACHAIN_INPUTS_NEEDED.zh-CN.md` 中的 `12/16`、`12/20` 已失效，该文件已更新为历史说明。

### 3.2 资产与影响面覆盖

- 对全部 16 个显式资产做了 DNS/HTTPS 接管负面基线，未发现 dangling-provider 信号。该结论只覆盖接管假设，不代表应用没有漏洞。
- 系统检查了开放重定向、静态内容写入、跨用户操作、敏感信息暴露、钱包交易参数替换、资金/NFT 影响、metadata 渲染、服务端危险输入链和接管等主要影响面。
- 对钱包 UI、空投、Swap/SOR、Hub、Honey、Token Bridge、NFT Bridge、静态站点和历史路由做了源码、归档构建或低量被动相关性分析。
- 原 1 项 Medium 候选已在补充真实框架行为后被否决；当前确认 finding 为 0。否决一个候选不代表其他资产或假设安全。

### 3.3 主要线索与负面证据

仍值得继续的高优先级线索：

1. 一个 vault 页面中，服务端是否对未白名单或仅 ABI-compatible 的地址始终隐藏交易组件。
2. 一个 SDK 中已离线证明的 quote/build 方向一致性缺陷，尚未找到官方生产前端触发条件。
3. OAuth 发起与回调的浏览器会话绑定缺口，尚未证明能达到项目定义的 Medium 影响，且不得测试第三方 OAuth 服务。
4. 若干归档生产构建的交易参数绑定已经审查，但仍缺当前构建或 server-component 调用点的相关性证明。

已取得的主要负面证据：

- 已审查的交易路径普遍绑定账户、token、amount、receiver、目标链或 minimum output，尚未证明可被另一用户或远端 quote 替换。
- 已审查的 metadata/文档页面没有发现第一方上传、动态文件选择或可执行 HTML 写入面。
- 公共 SOR 数据的低量隔离检查没有发现 amount、方向、swap kind 或协议版本之间的 cache crossover。
- 已审查的消息通信路径包含来源窗口和 origin 绑定；已知历史缺陷在相关生产 bundle 中未复现。
- 当前没有已验证的资金/NFT 盗取、恶意交易替换、跨用户敏感修改、私密数据泄露或服务端代码执行路径。

这些均为特定假设和特定版本下的证据，不能扩张为“资产安全”结论。

## 4. 工具进展

本次未提交代码把 InferForge 扩展为更完整的离线源码风险审查器，主要包括：

- 从 Immunefi 页面序列化数据补全 program assets/impacts。
- `source-risk-review` 的 44 类静态风险信号和上下文关联。
- 导入、路由可达性、控制顺序/生效性、输入 shape、CSRF/CORS、响应、缓存、路径、上传、认证、OAuth、权限、浏览器消息、渲染、存储、业务值、日志、错误、执行、反序列化、查询、GraphQL、SSRF、重定向、webhook 和身份绑定等审查面。
- `regression-suite --offline-only --plan-only` 及其“不得调度活动步骤”的安全守卫。
- 黑盒静态资源优先级和失败诊断的小幅改进。
- 完整 bounty program 的 scope/lead 语义指纹 lineage；旧 scope 会阻断下游 lead 使用。
- Program impact 明确为 planning-only，不再虚增 actionable finding 计数，并显式记录候选资产截断数量。
- 显式缺失 `--profile`、超限离线 HTML 输入改为 fail-closed。
- Source risk 覆盖 `.mjs/.cjs` 和根级运行入口；超大/不可读文件会把覆盖标为不完整。
- `artifact-health` 会比较 program、scope 与 lead 消费的语义指纹。
- 显式 `corpus_integrity` 的 `summary-only/corpus-missing` 会进入 artifact-health evidence gap，而不是被摘要中的 SHA 伪装成原始语料仍在。

它是启发式线索生成器，不是漏洞证明器；regex 和近邻分析仍可能误报或漏报。

本轮验证结果：

- Python 编译：通过。
- CLI 加载：通过。
- `git diff --check`：通过。
- Immunefi profile 自测：`8/8` 通过。
- Source risk 自测：`404/404` 通过，覆盖 44 类信号。
- Offline regression guard 自测：`10/10` 通过，计划中的活动命令为 0。

2026-07-11 增量验证：Immunefi/profile/scope/lead 自测扩展为 `22/22`，包括 OOS 标题/澄清分类、稳定语义指纹、完整 program allowlist fail-closed、人工 override、20 条 planning-only impact、旧 scope lineage blocker 与重建解除；artifact-health 自测 `28/28`；source-risk 自测 `406/406`，覆盖 44 类信号及根级 `.cjs`、`src/*.mjs`、大文件 incomplete guard；显式缺失 profile 返回退出码 2，离线 HTML 超限返回退出码 2；Python 编译通过。

没有运行完整集成 regression suite；上述专项 synthetic self-test 不等于整套系统集成证明。

## 5. 私密证据与公开仓库边界

当前 GitHub 远端是公开仓库，program 又要求未修复漏洞披露前取得批准。因此以下内容不得 push：

- finding 的资产名、可利用 URL、payload、根因细节和完整报告；
- PoC、现场响应元数据、原始 HTML/JS、HAR、Burp/raw HTTP；
- cookie、Authorization/Bearer、测试账号、钱包 profile、签名、私钥或助记词；
- 本地运行时/资源快照和 operator evidence；
- 完整 `.greybox/berachain-webapps/`。

公开 Git 只保存脱敏进展、通用工具代码、无凭证的运行说明和忽略规则。私密研究材料必须通过加密包或其他安全带外方式迁移。

## 6. Artifact 新旧状态

新机恢复后不要把所有 JSON 同等视为权威状态：

- 最新 program profile 已是 `16/16` assets、`20/20` impacts、`ready`。
- 人工维护的 coverage/research ledger 更新到 2026-07-11，并明确将旧 Medium 候选判为 invalid。
- `scope-policy.json` 已于 2026-07-11 离线重建为 16 个显式 host、deny-by-default、0 unresolved；完整 program 资产存在时不再把任意命令行 target 自动加入 allowlist。
- `lead-portfolio.json` 已于 2026-07-11 离线重建：20 条 program impact 现在明确标为 planning-only，不能再计作 actionable vulnerability leads；另有 12 条既有 takeover 负面基线，当前 actionable 计数为 0。
- 根目录或子目录的通用 `config.json`、`target-profile.json`、`profile-validation.json` 可能仍指向本机 fixture、绝对路径或其他测试 profile，不代表 BeraChain 验证状态。
- 通用 artifact manifest 的 `incomplete` 可能来自未运行整套审计流水线，不能替代人工研究台账。

## 7. 新机器恢复清单

1. 克隆公开代码并确认分支：

   ```bash
   git clone git@github.com:ret2basic/greybox-not-greyhat.git
   cd greybox-not-greyhat
   git switch main
   git pull --ff-only
   ```

2. 通过安全带外渠道取得私密交接包，先执行随包提供的 SHA-256 校验，再解密/解包到仓库根目录。不要把包或解包后的 `.greybox` 加入 Git。

3. 安装 Python 3 和 Node 22。README 中若出现旧机器的缓存 Node 绝对路径，只能视为旧环境示例；新机应使用 mise、nvm 或系统 Node 22。

4. 重建前端依赖，不迁移 `node_modules` 或 `.next`：

   ```bash
   cd infrafi-web
   npm ci
   npm run lint
   ```

5. 回到仓库根目录运行无网络 smoke test：

   ```bash
   python3 -m py_compile scripts/inferforge.py
   python3 scripts/inferforge.py --help >/dev/null
   python3 scripts/inferforge.py --artifact-dir .greybox/handoff-selftest-bounty \
     self-test-bounty-program-profile
   python3 scripts/inferforge.py --artifact-dir .greybox/handoff-selftest-source \
     self-test-source-risk-review
   python3 scripts/inferforge.py --artifact-dir .greybox/handoff-selftest-offline-guard \
     self-test-regression-offline-safety
   ```

6. 重新配置仓库外状态：Git/SSH 凭证、Burp、浏览器 profile、Codex/Burp MCP 注册和任何本机环境变量。这些都不在 Git 中。

## 8. 下一轮优先级

1. 将旧 Medium 候选固定为 invalid / not reportable；任何自动化或人工 handoff 都不得再把它提升为 submission-ready。
2. 继续补 profile/target 一致性与 artifact freshness 守卫；16-asset scope policy 和无 fixture 污染的 root lead portfolio 已完成离线重建。
3. 证明 vault 交易组件的服务端白名单门禁；没有生产可达性前继续保持 lead 状态。
4. 恢复缺失的 Hub server call site / confirmation chunk，并对当前构建做相关性确认。
5. 用浏览器导出的当前构建材料离线复核 Hub、Honey、Bridge 和 NFT Bridge；任何新主动步骤都需要重新确认 scope 和授权。
6. 继续钱包交易展示/解码、WalletConnect、App manifest 和 signing-intent 审查。

## 9. 不可越过的安全边界

- 不测试第三方服务或 OAuth provider。
- 不在主网或公测网提交交易、签名、claim、approval、上传或持久写入。
- 不做 DoS、压力测试、高流量自动化、rate-limit 或大查询测试。
- 不把静态信号、历史版本缺陷或 SDK misuse 当成当前生产 finding。
- 未在完整 scope 中列出的 host 按 out-of-scope-by-default 处理。
- 未取得披露批准前，不公开未修复 finding 的可操作细节。

本文件所在的 Git 提交是公开代码交接基线；私密证据包的 SHA-256 sidecar 是研究材料交接基线。
