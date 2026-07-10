# Berachain Web/Apps 后续输入需求（历史状态已更新）

原始生成时间：2026-07-08

状态更新时间：2026-07-10

## 当前状态

本文最初记录的 Immunefi 静态页面缺口已经解决。更新后的解析器能够从页面序列化数据中恢复完整列表，本地权威画像现为：

- Assets in Scope：`16/16`
- Impacts in Scope：`20/20`
- 状态：`ready`
- Information、Scope、Resources：`3/3` 页面已读取

因此，不再需要为了补齐 scope 而手工展开 `Show all`。旧的 `12/16`、`12/20` 和 `partial-needs-review` 结论不得再作为当前状态引用。

公开、脱敏的阶段总结和换机说明见 [docs/BERACHAIN_HANDOFF_2026-07-10.zh-CN.md](docs/BERACHAIN_HANDOFF_2026-07-10.zh-CN.md)。完整研究证据仍在本地私密 artifact 中，不会进入公开 GitHub 仓库。

## 仍有价值的可选输入

以下页面的当前生产构建曾受 checkpoint 或限流影响。正常浏览器导出的 HTML 仍可用于“当前构建相关性”复核，但它们不再是补全 bounty scope 的前置条件：

```text
bridge.html
nftbridge.html
hub.html
honey.html
```

建议存放到：

```text
manual-inputs/berachain-webapps/
```

`manual-inputs/` 已加入 `.gitignore`。浏览器导出、HAR、认证会话、钱包 profile、签名和密钥只能通过私密带外渠道迁移，不能提交到当前公开仓库。

离线解析示例：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/berachain-webapps \
  immunefi-program-profile --program-slug berachain-webapps \
  --input-dir manual-inputs/berachain-webapps --no-fetch \
  --show-assets --show-impacts --show-techniques --show-links
```

Web App 页面可继续通过 `blackbox-asset-map --input-html` 离线提取候选，不需要扩大自动请求。

## 测试账号与钱包材料

只有在用户明确授权具体验证步骤后，才可使用专用测试账号或测试钱包材料。继续遵守：

- 不使用真实用户数据或主网资金。
- 不提交真实交易、claim、approval 或签名。
- 不测试第三方 OAuth、表单或其他第三方服务。
- 不做 DoS、压力测试、高流量扫描或 scanner-only 报告。
- 未在完整 16 项 scope 列表中的同父域 host，仍按 out-of-scope-by-default 处理。

## 换机时的注意事项

本文件和公开 Git 历史只保存可公开内容。`.greybox/berachain-webapps/`、浏览器导出和未披露 finding 证据必须单独加密或通过安全带外方式复制；仅执行 `git clone` 无法恢复它们。
