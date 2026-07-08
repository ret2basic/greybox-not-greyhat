# Berachain Web/Apps 后续输入需求

生成时间：2026-07-08

## 当前状态

我们已经用 `immunefi-program-profile` 读取了 Berachain Web/Apps 的 Immunefi 三个页面：

- Information: `https://immunefi.com/bug-bounty/berachain-webapps/information/`
- Scope: `https://immunefi.com/bug-bounty/berachain-webapps/scope/`
- Resources: `https://immunefi.com/bug-bounty/berachain-webapps/resources/`

当前静态页面可见结果：

- Assets in Scope: 解析到 `12/16`
- Impacts in Scope: 解析到 `12/20`
- 状态：`partial-needs-review`

这说明 Immunefi 静态 HTML 没有暴露完整的 `Show all` / 分页内容。工具已经保守处理，不会假装 scope 完整。

## 我需要你提供的内容

### 1. 渲染后的 Immunefi Scope 页面

请用浏览器打开：

```text
https://immunefi.com/bug-bounty/berachain-webapps/scope/#top
```

操作：

1. 展开 `Assets in Scope` 的 `Show all`。
2. 展开 `Impacts in Scope` 的 `Show all`。
3. 保存完整 HTML，命名为：

```text
scope.html
```

如果浏览器只能复制文本，也可以保存为：

```text
scope.txt
```

但优先 HTML，因为 HTML 能保留 asset URL。

### 2. 渲染后的 Immunefi Information 和 Resources 页面

请分别打开：

```text
https://immunefi.com/bug-bounty/berachain-webapps/information/#top
https://immunefi.com/bug-bounty/berachain-webapps/resources/#top
```

保存为：

```text
information.html
resources.html
```

这两个页面用于补齐奖励规则、KYC/PoC/禁止活动、文档和审计链接。

### 3. 被 429 拦住的 Web App 页面 HTML

自动低频请求以下页面时返回了 HTTP `429`，所以工具已经停止扩大抓取：

```text
https://bridge.berachain.com/
https://nftbridge.berachain.com/
https://hub.berachain.com/
```

请用正常浏览器打开这些页面，等待页面完整加载后保存 HTML：

```text
bridge.html
nftbridge.html
hub.html
```

这些文件会让工具离线提取：

- JavaScript bundle URL
- API endpoint 候选
- WebSocket endpoint 候选
- 钱包交易构造路径
- NFT metadata / URI 相关路径

### 4. 可选：测试账号和测试钱包材料

如果后面要验证 authenticated action、fund/NFT theft、wallet transaction integrity 这类 impact，需要你提供明确授权的测试材料。

最低需求：

```text
test-account-1
test-account-2
test-wallet-address-1
test-wallet-address-2
testnet-only private key or browser wallet profile
```

要求：

- 只用测试账号。
- 不使用真实用户数据。
- 不使用主网资金。
- 不提交真实交易。
- 不做 DoS、压力测试、scanner-only 报告。

## 建议目录结构

把文件放到一个目录，例如：

```text
manual-inputs/berachain-webapps/
  information.html
  scope.html
  resources.html
  bridge.html
  nftbridge.html
  hub.html
```

然后我可以用：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/berachain-webapps \
  immunefi-program-profile --program-slug berachain-webapps \
  --input-dir manual-inputs/berachain-webapps --no-fetch \
  --show-assets --show-impacts --show-techniques --show-links
```

Web App 页面可以继续用 `blackbox-asset-map --input-html` 做离线解析，不需要再请求目标站点。
