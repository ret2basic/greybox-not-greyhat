# Immunefi Web2 / Variational 阶段总结（公开安全版）

更新时间：2026-07-13 UTC

## 1. 一句话状态

Variational 的规则、公开源码、生产静态构建、产品文档和审计边界已经完成一轮有界复核。当前 submission-ready finding 数量为 `0`；该目标已从主动研究切换为条件监控，下一条主线转向 Kiln 的单一 source-mapped Web cluster。

## 2. 奖励与范围修正

Variational 是 mixed Smart Contract + Web/App program。目录上的 `$100,000` 不是 Web/App ceiling。

Web/App 实际奖励：

- Critical：`$10,000–$50,000`
- High：`$10,000`
- Medium：`$2,000`
- Low：`$1,000`

`$50,000` 只适用于不需要用户操作的资金损失，或 private-key/private-key-generation 泄漏并导致未授权资金访问；其他 Critical Web/App impact 为 `$10,000`。

精确 scope 是一个主要应用 `omni.variational.io`，外加一个仅用于 Critical direct-theft Primacy-of-Impact 报告归类的 `www.variational.io` placeholder。它不是子域 wildcard，也不扩大测试权限。

KYC 与 PoC 均 required，Safe Harbor inactive，公开披露需要批准。

## 3. 生产与源码映射

生产应用识别为 SvelteKit，静态构建标记为：

```text
omni-v3.0.5 / prod
```

官方公开 GitHub 组织只有一个 Python reference SDK。该 SDK 能说明部分 protocol/API 词汇，但不包含当前 Omni frontend、browser auth/session、backend、cache、renderer 或 deployment provenance。

生产 entry 宣告 source map，但本轮没有取得可用 source map；因此不能把公开 SDK commit 与生产前端建立 source equivalence。

## 4. 本轮建立的安全边界

公开文档与少量静态 bundle 足以确认以下高价值边界存在：

- wallet-sign login 与 mobile session linking；
- gasless USDC transfer authorization；
- per-user settlement pool；
- 平台 transactor / watcher；
- trade/quote/margin/withdrawal concurrency；
- account-sensitive position and transfer APIs；
- public metadata/cache 与 execution data 的隔离要求。

但决定漏洞是否成立的 server-side verifier、nonce/session lifecycle、object authorization、recipient/amount binding、idempotency 和 recovery logic 都不在公开源码中。

选定 bundle 没有建立第一方 XSS、remote localStorage control、client-side auth grant 或危险 metadata-rendering data flow。客户端出现的签名与 session-transfer call sites 只能定义审计问题，不能证明生产 bypass。

## 5. 为什么当前不能提交

当前所有高价值 lead 都停在以下至少一个缺口：

- 只有 client call site，没有 server validation implementation；
- 没有普通攻击者可用的第一方 response-control/XSS/cache 原语；
- 生产验证需要调用受保护 API、签钱包或触达主网，而本轮明确不允许；
- 两次私有源码审计的大部分 finding 被 redacted，存在无法公开排除的 dedupe blind spot；
- 公开的 acknowledged audit issues 本身不具备 bounty eligibility。

因此不能把“服务端可能漏验”或“客户端信任服务端 template”写成漏洞报告。

## 6. 恢复研究的触发条件

只有出现以下至少一项，才值得重新打开 Variational：

1. 官方公开 frontend/backend source 或为 bounty 提供私有 source bundle；
2. production source map / build provenance 可用；
3. 明确授权的本地测试环境，可验证 server authorization；
4. production build 或 bounty semantic fingerprint 发生相关变化；
5. 新的第一方 XSS、response substitution、cache poisoning 或 storage-read 原语。

在此之前，Variational 应保持 monitor-only；继续开放式黑盒投入的证据成本已经高于切换目标。

## 7. 私密证据边界

具体 bundle hash、minified call-site excerpt、离线 harness、server-side hypotheses 和 audit dedupe notes 位于被 `.gitignore` 排除的：

```text
.greybox/targets/variational-research/
```

该目录不得加入公开 Git、PR 或未授权披露。公开文件只保留状态、边界和切换阈值。

## 8. 不可越过的边界

- 不在 mainnet 或 public testnet 测试；
- 不调用生产业务 API 去猜测 BOLA、replay 或 signature validation；
- 不连接钱包、不签名、不提交 transaction；
- 不测试 third-party systems；
- 不做 DoS、significant automation、phishing 或 social engineering；
- 不把理论风险、客户端 sink 或 docs gap 表述成当前漏洞。

