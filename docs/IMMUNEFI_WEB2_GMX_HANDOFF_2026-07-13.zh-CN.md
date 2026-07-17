# Immunefi Web2 / GMX 研究阶段总结（公开安全版）

更新时间：2026-07-13 UTC

交接分支：`main`

公开远端：`ret2basic/greybox-not-greyhat`（Public）

## 1. 一句话状态

Immunefi Web/App 目录与前 12 个候选画像已经刷新；GMX 仍是本轮完成度最高的源码主线，但当前确认的 submission-ready finding 数量为 `0`。本地已经验证一项“特定首存状态 + 跨链 UI 路径”缺陷机制和一项第三方 swap calldata 信任边界，另确认 1CT 本地密钥存储是高价值条件性 sink；三者都缺少当前生产可达性或第一方攻击者原语，不得按现状提交。

## 2. 状态口径

后续工作必须区分：

- **机制成立**：本地代码路径、负面对照和离线 PoC 成立。
- **生产可达**：当前 in-scope 生产资产存在普通攻击者可以触发的前置条件。
- **可提交**：scope、impact、生产相关性、PoC end-effect 和报告材料均通过复核。
- **已提交**：已经取得 Immunefi submission/ticket 记录。
- **平台确认**：GMX 或 Immunefi 已确认有效性、严重度或奖励。

当前只有若干“机制成立”的条件性 lead；没有生产可达、可提交、已提交或平台确认的 finding。

## 3. 平台目录状态

2026-07-13 的目录刷新结果：

- Immunefi 全部目录项目：`191`
- 含 Websites and Applications：`78`
- Web/App-only：`10`
- mixed scope：`68`
- 已补完整 enrichment：`12`
- 与上一次快照比较：`no-change`
- 离线 self-test：`13/13` 通过

机器排序的前 12 名恰好就是已 enrichment 的 12 个项目，因此存在明显的 enrichment-selection bias；它不是全体 78 个项目之间的无偏统计排序。asset count 也会把 GitHub repository 或 Immunefi placeholder 计入，对 Chainlink、Spark 等项目尤其容易虚高。

人工调整后的继续顺序仍为：

1. GMX（本轮主线，现转为条件监控）
2. Kiln
3. 0x
4. Lido
5. Variational
6. StakeWise

若目标是下一份报告命中率，优先切换 Variational；若目标是单份 Web/App 奖励上限，优先 StakeWise。Kiln、0x、Lido 保留在完整人工队列中，不代表已经完成针对它们的源码审计。

## 4. GMX 为什么仍值得保留

GMX Web/App 规则在 2026-07-13 的语义指纹保持不变：

```text
d49e66191a5d993805d9cca7f29f35d14b88293951a998847fd49ce19ed4411c
```

确认条件：

- in-scope Web hosts 只有 `gmx.io`、`app.gmx.io`；
- Web/App Critical / High / Medium 分别为固定 `$50,000` / `$25,000` / `$10,000`；
- KYC 不要求；
- 没有 pay-to-submit fee；
- PoC 必须包含影响 in-scope asset 的代码和 end-effect；
- 由 Immunefi managed triage；
- 共 20 条 Web/App impact，其中 17 条是 Critical 或 High。

生产前端的公开构建标记解析到：

```text
9b11b95d33ecbffd9d24e42bd80da74d45dab17c
```

审查所用 detached worktree 固定在该 commit；关键 GMX/GLV、external swap、multichain 和 platform-token 文件与刷新时 `release` worktree 中的内容哈希一致。由于两个 shallow commit 是断开的 graft root，不使用虚假的 merge-base 结论。

## 5. 当前候选的公开安全结论

### 5.1 首存状态的跨链 GLV 路径

本地源码链和完全离线回归 PoC 已证明：在一种协议要求的“首次存入特殊 receiver”状态中，前端把资产接收者与跨链身份账户错误地复用了；后续签名校验失败，但先前的 bridge credit 不会随被 catch 的 action 一起回滚。

这是一条真实机制，不是单纯静态告警。但是当前 production multichain allowlist 只包含两只早在该前端功能上线前就存在并被运维的主网 GLV。源码历史没有证明缺陷上线后曾出现 `totalSupply == 0` 且用户 UI 可选的窗口，因此当前状态为：

```text
mechanism-confirmed / reachability-unproven / not submission-ready
```

只有公开证据证明新 GLV 在未 bootstrap 时已经对 source-chain deposit 开放，才能进入提交前复核。

### 5.2 External swap / opaque calldata

本地 ABI PoC 已证明：前端 pin 住第三方聚合器的顶层 router，却不把 opaque inner calldata 重新绑定到 UI 展示的 token、receiver、amount、minimum output 和 fee 语义。该 trust boundary 有潜在高影响，但目前没有发现 `app.gmx.io` / `gmx.io` 第一方 XSS、同源 response substitution、可利用缓存混淆或 URL override。

第三方 API host 本身也不在 GMX Web host scope，production 交易提交前还有模拟。当前状态为：

```text
conditional sink / third-party premise / no in-scope attacker primitive / not submission-ready
```

不得测试第三方聚合器来补齐该前置条件。

### 5.3 1CT / subaccount 本地密钥

1CT 使用固定消息签名派生 subaccount key，把经 AES 包装的 private key 存入 localStorage，而包装口令只是公开主钱包地址。任何真实的 same-origin script execution 或 storage-read primitive 都会把它升级为高价值会话密钥盗取路径。

当前生产源码中没有找到这种远端第一方原语；本机/浏览器 compromise、扩展和 phishing 又明确 out of scope。已审查的 approval typed data 也绑定 subaccount、action、nonce、deadline、destination chain 和 verifying router。当前状态为条件性 sink，不是独立 finding。

### 5.4 两个被降级的 near-miss

- 一个 URL query 能触发“把现有 TP/SL order 改为 auto-cancel”的钱包交易请求，但 query 不能选择 order key、router 或 calldata，仍需当前钱包确认；它属于 intended conversion / UX-CSRF，且 phishing/social engineering 不在允许路径内。
- 原生币余额的 SWR key 漏了 account，切换钱包后可短暂复用上一账户的公开余额；影响局限于费用提示和按钮门禁误判，当前钱包的真实发送和链上余额仍是最终约束。定性为 Low/Info correctness，不是跨用户资金原语。

## 6. 已否定或未建立的假设

对 production-mapped source tree 的第一方应用代码检查未建立以下原语：

- `dangerouslySetInnerHTML`、application-controlled `innerHTML`、`outerHTML`、`insertAdjacentHTML`、`document.write`、`DOMParser` 或 `srcDoc`；
- Markdown/HTML sanitizer 绕过面；
- cross-window message listener 缺 origin check；现有 message path 只有专用 multicall Web Worker；
- service worker、Workbox、CacheStorage 或持久 response cache；
- production host 可用的 localStorage API/indexer/RPC override；
- account-sensitive SWR key 的可利用跨用户响应替换；
- external swap endpoint 的 URL/query override；
- subaccount typed-data 跨 account/chain/router replay。

这些是针对当前 commit 和已审查路径的负面证据，不是“GMX 安全”的结论。

## 7. 继续或切换阈值

继续主动投入 GMX，必须先出现以下至少一项新证据：

1. 新 GLV 在 source-chain deposit 已开放、但仍未 bootstrap 的公开 launch sequencing 证据；
2. `app.gmx.io` / `gmx.io` 第一方 XSS、storage-read、response substitution 或可利用 cache poisoning；
3. 不依赖第三方 compromise、浏览器 compromise、phishing 或主网测试的 Kyber payload 生成路径；
4. 当前 production commit 发生相关 semantic diff。

在此之前，GMX 应作为监控 lane，而不是继续无界扩张源码搜索：

- 追求命中率：切换 Variational；
- 追求单份奖励上限：切换 StakeWise；
- GMX 目录、规则或 production commit 变化时，再做一次窄范围 diff。

## 8. 私密证据边界

本公开仓库不得保存或 push 尚未修复漏洞的可操作细节、完整 PoC、恶意 payload 或报告草稿。完整研究交接和离线 PoC 位于被 `.gitignore` 排除的：

```text
.greybox/targets/gmx-research/
.greybox/targets/gmx-research/private-artifacts.sha256
```

任何迁移都应通过安全带外渠道并校验 SHA-256。不要把 `.greybox`、原始 bundle、钱包资料、签名、私钥、HAR 或 Burp 历史加入公开 Git。

## 9. 不可越过的安全边界

- 不在主网或公测网测试、签名或发送交易；
- 不测试 Kyber、钱包扩展、SSO 或其他第三方系统；
- 不做 DoS、压力测试、高流量自动化或 rate-limit 测试；
- 不做 phishing 或 social engineering；
- 不把机制成立、历史版本缺陷或 defense-in-depth 建议写成当前生产 finding；
- 未修复问题不得公开披露。

本文件只保留公开安全的状态和决策阈值；它不是提交报告，也不包含复现漏洞所需的完整操作细节。
