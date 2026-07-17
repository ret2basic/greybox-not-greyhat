# Immunefi Web2 / Kiln 阶段总结（公开安全版）

更新时间：2026-07-13 UTC

## 1. 一句话状态

Kiln 的 11 个 Web/App asset 已完成规则分组，并对 stake/widget cluster 做了有界 source/production mapping。当前 submission-ready finding 数量为 `0`。生产 widget 可识别为当前 React/Inertia/Vite build，但没有公开 source equivalence；本轮转为条件监控，下一条主线切换到 0x。

## 2. 规则修正

Web/App tier table 显示：

- Critical：`$20,000–$100,000`
- High：`$2,500–$8,000`
- Medium：`$1,000–$2,500`

详细 reward prose 另称：只有无用户操作的资金损失或 qualifying key leakage 按 `10% impacted TVL`、上限 `$100,000`；其他 Critical 为 flat `$8,000`。这与表格 minimum 冲突，提交前必须让 program/Immunefi 澄清。

PoC 应按 required 处理。catalog 的一个 raw tag 写 `PoC Not Required`，但 normalized field、candidate summary 和 detail text 都写 required。

全部 asset/impact 都是 Primacy of Rules。KYC required，Safe Harbor inactive，禁止 mainnet/public-testnet、第三方、wallet extension、oracle、DoS、significant automation 与 phishing 测试。

## 3. 为什么选择 stake/widget

11 个 hostname 被分成 public/staking、account/custody、API/integration 和 operations/data 四个 cluster。stake/widget 直接对应 wallet transaction integrity、direct theft 和 metadata XSS，并且理论上可以用 production-correlated source + local mocked wallet 验证。

Dashboard/API 虽有 RCE、SQLi、IAM、sensitive file 和 BOLA 等高价值 impact，但没有公开 backend/source mapping 或安全本地环境；不能把它变成 production black-box probing。

## 4. 生产映射结论

`widget.kiln.fi/overview` 的 current build fingerprint：

```text
Vite + React 18.3.1 + Inertia
build_id: main-6d49ad2e-1783064769
entry: /build/assets/app-D07ivQTC.js
```

该 build 包含 multi-chain wallet infrastructure 和 transaction-capable lazy modules，但没有 source map、public repository marker 或 full commit。公开 GitHub 组织中的 SDK、旧 Solana demo、integration example 和 archived React components 都与 production dependency/source tree 不同。

`stake.kiln.fi` 当前把根路径重定向到一个未列入本轮 exact scope 的 hostname；本轮没有 follow 或测试该目标。

## 5. 建立但未闭合的安全边界

确认存在：

- server product metadata / deeplink → lazy transaction builder → Wagmi/Viem → wallet；
- product/asset/return deeplink 配置；
- Inertia response/head HTML rendering sink；
- embedded/custom connector 体系；
- multi-chain RPC/chain switching 与 token-specific approval reset。

没有建立：

- attacker-controlled product/asset/contract/recipient/calldata 进入 wallet request；
- first-party untrusted response/metadata 进入 HTML sink；
- cross-tenant config authorization bypass；
- production business `postMessage` origin bug；
- client-visible API/RPC key 具备 secret impact。

公开文档中的 arbitrary HTTPS callback return 与 branding/custom-link 能力是明确 integration feature；没有证据证明它们产生超出设计的 open redirect/XSS/BOLA 影响。

## 6. Public example 为什么不能当 production finding

一个旧 Solana widget demo 会把 API 返回的 serialized transaction 交给钱包，而 visible client 没有重新校验具体指令；另一个 testnet iframe integration example 只以 frame object 区分消息来源，并使用 wildcard response target。

这两项机制都可在本地复现，但它们没有映射到当前 production React/Inertia build，也没有普通攻击者可用的 response control、frame navigation 或 first-party exploit primitive。把 example/demo sink 报成当前生产漏洞会混淆机制成立与生产可达性。

## 7. 恢复阈值

只有以下至少一项出现才恢复主动投入：

1. production frontend/backend repo 或 bounty source bundle；
2. source map / build provenance；
3. 明确授权的 local/staging environment；
4. first-party metadata/response/config control primitive；
5. production build 或 bounty semantic fingerprint 相关变化；
6. scope 明确加入当前 redirect destination 或 organization-specific widget slug。

## 8. 私密证据边界

bundle hash、source comparison、具体 conditional sink、离线 harness 和 rejected-hypothesis 细节保存在：

```text
.greybox/targets/kiln-research/
```

该目录被 `.gitignore` 排除，不得加入公开 Git、PR 或未批准披露。

