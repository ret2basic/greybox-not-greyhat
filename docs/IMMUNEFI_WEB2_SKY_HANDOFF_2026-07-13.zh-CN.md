# Immunefi Web2 — Sky 阶段性交接（2026-07-13）

## 结论

Sky 已完成当前 production Web/App 的最强公开源码候选映射、投票边界审查和
纯本地验证，并明确保留未被 public deployment metadata 证明的版本边界。

```text
strong portal source candidate mapped /
indexer and contract public provenance pinned with deployment qualifiers /
one private governance-result submission candidate packaged /
secondary conditional leads classified /
no live-chain or production-API testing performed
```

未修复问题的技术细节、PoC 和报告草稿只保存在被 `.gitignore` 忽略的
`.greybox/targets/sky-research/`，不会进入公开文档或 Git 历史。

## 生产源码映射

当前 production source candidate：

```text
skybase-foundation/sky-governance-portal
6f900304fd69b93c87ad95ebb96d351fbe7671df
```

GitHub Production deployment 与该 commit 精确绑定；被动捕获的 production
Next.js 静态 bundle 也与其投票 hook、SKY 文案、合约/API 配置和构建结构一致。
静态 bundle 只用于佐证 custom domain、frontend deployment 与源码候选的对应关系，
不单独证明 server-only modules。

相关 indexer/source pins：

```text
skybase-foundation/sky-money-indexer
44b173950416ce09f64bc565c339a2413fa5442f

sky-ecosystem/symbolic-voting
f000d3856f6c03513ce7945dae756f3dcc154d61

makerdao-dux/polling-contract
8a8e0819e5511f1ec84aec9dde08d2930ad1fc11

sky-ecosystem/polls
9f900c03f806b0712b8951f14810db3dd529a44d
```

## 验证边界

本轮只执行：

- 公开 GitHub 源码与 deployment metadata 读取；
- 已允许的被动静态 production bundle 对照；
- dependency-free 本地 fixture/算法 PoC；
- 负向控制和 source-version 比较。

本轮没有：

- 主网或公测网交易；
- 钱包连接、签名或广播；
- RPC、oracle、relayer 或流动性源调用；
- production API 探测；
- 内网/metadata/loopback 探测；
- DoS、压力测试或大规模自动化。

## 当前状态

详细私有包中包含：

- 1 个优先提交候选；
- 1 个需要 scope 解释的独立 governance 候选；
- 2 个已确认机制但尚无 accepted impact 的关闭/conditional 线索；
- 完整 source pins、PoC、controls、修复建议和英文报告草稿。

下一步是在人工复核后由用户决定是否执行外部提交；在此之前不公开、不 commit、
不 push 漏洞细节。平台级研究目标仍继续，不因单个 target 打包而结束。
