# Immunefi Web2 / 0x 阶段总结（公开安全版）

更新时间：2026-07-13 UTC

## 1. 一句话状态

0x 的 Web/App 规则、current API v2 documentation/OpenAPI、official examples、Settler binding 与 Matcha/Meta 被动映射已经完成一轮有界复核。当前 submission-ready finding 数量为 `0`。Swap/Gasless 的关键 client trust boundary 已建立，但 current backend/Matcha frontend 不公开，且没有 production intent-to-output mismatch。

## 2. 奖励与 scope 修正

目录上的 `$1,000,000` 属于 mixed Smart Contract program，不是 Web ceiling。

Web/App：

- qualifying Critical：`$50,000`
- other Critical：`$15,000`
- High：`$10,000`
- Medium：`$1,000`

full reward 的 KYC 可以拒绝，代价是 payout 降至 70%。Web/App 全部是 Primacy of Rules，scope 只有 Matcha、Meta Matcha、`api.0x.org/swap/` 与 `api.0x.org/gasless/`。

## 3. 特别严格的有效性门槛

0x 明确排除因 caller 自己错误编码 action、错误排序、误用 slippage、调用 attacker-controlled BASIC target，或使用已有替代 encoding/action/field 即可避免的 self-loss。

因此有效 Web/API finding 必须证明：正常 documented request 由 first-party API/app 生成违背用户 intent 的 unsigned transaction 或 signed message；不能把 integrator misuse、third-party liquidity、oracle 或纯 Settler contract 行为包装成 Web 漏洞。

## 4. Source 与 production mapping

0x 公开 current docs/OpenAPI、v2 examples 与 Settler contracts；不公开 current Swap/Gasless backend 或 Matcha/Meta frontend。legacy `0x-api` repo 已 archived/deprecated，不能当 current backend。

Matcha 与 Meta 根页面都返回 Cloudflare access-control page。本轮没有执行 challenge、retry 或 bypass，也没有取得 app entry/build/source map。业务 API 没有 live call。

## 5. 已建立的 API 安全边界

Swap API：valid request intent → API quote → allowance target / execution entry → unsigned transaction。Permit2 path 另有 EIP-712 permit；AllowanceHolder path 使用专用 allowance/entry contract。

Gasless API：quote 返回 optional token approval 与 trade EIP-712；trade witness 签名绑定 chain、sell token/amount、spender、nonce、deadline、recipient、buy token、minimum output 和 action bytes，然后由 0x relayer submit。

本地 exact-digest harness 从 official OpenAPI fixture 独立重算出 trade hash `0x3ff032fa3a970a3f2b763afce093fd133ced63c0b097ab12ae1441b42de4a167`。逐项修改 chain、Permit2 verifying contract、sell token/amount、Settler spender、nonce、deadline、recipient、buy token、minimum output、action byte 或 action ordering 均会改变 digest；未发现 mutation/replay bypass。

official clients 会直接使用 API 返回的 transaction/typed data，这是高价值 integration sink；但没有 first-party response-control 或 production semantic mismatch 时，它不是漏洞。

## 6. 一个确认的 docs/OpenAPI 不一致

current AllowanceHolder response example 中，`allowanceTarget`、`issues.allowance.spender` 和 `transaction.to` 对应的 contract role 与 current narrative docs 不一致。Permit2 example 则 cross-field consistent。

这个差异在本地 harness 中可稳定识别，但目前只证明 docs/fixture correctness。没有 production response 或资金影响，Web bounty 也没有 Low tier，因此不应作为 Immunefi finding 提交。

## 7. 为什么当前停止

- current backend/frontend source 不可用；
- Matcha/Meta build 无法被动映射；
- live quote/relayer/wallet/mainnet validation 不在允许路径；
- Gasless signed witness 对核心字段有强绑定；
- OpenAPI 矛盾只达到 docs correctness；
- third-party/upstream testing 与 caller-misuse hypotheses 明确不 eligible。

## 8. 恢复阈值

仅在 current backend/source bundle、官方 production response corpus、明确授权的 local/staging API harness、Matcha build provenance、first-party response/cache primitive 或相关 semantic diff 出现时恢复。

详细 fixture、字段映射、离线 harness 与 rejected hypotheses 保存在被 `.gitignore` 排除的：

```text
.greybox/targets/0x-research/
```
