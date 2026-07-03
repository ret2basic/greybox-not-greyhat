# Burp Suite 与 Codex 的 MCP 集成原理

这份文档解释我们当前准备用在灰盒审计工具里的 Burp Suite MCP 链路：它是谁开发的、各组件的边界是什么、请求如何流转、它能控制 Burp 到什么程度，以及它在“70% 黑盒 + 30% 白盒”的审计模式里应该扮演什么角色。

## 结论先行

这套 MCP 集成不是“Burp 内置 AI”，也不是 Codex 直接注入 Burp 进程。

它更准确的定义是：

> Codex 作为 MCP Client，通过一个本地 MCP 通道调用 Burp MCP Server 暴露出来的工具；Burp MCP Server 是一个运行在 Burp Suite 内部的 PortSwigger 扩展，它再通过 Burp 的扩展 API 操作 Burp 的 HTTP 历史、Repeater、Intruder、代理设置、编码工具等功能。

在我们当前机器上的预期链路是：

```text
Codex
  |
  | stdio MCP
  v
mcp-proxy-all.jar
  |
  | HTTP/SSE: http://127.0.0.1:9876
  v
Burp MCP Server extension
  |
  | Burp Montoya API
  v
Burp Suite Community / Professional
```

所以它的核心价值不是“让 Burp 自己变聪明”，而是“把 Burp 变成一个可被 AI Agent 程序化操作的传统 Web 安全工作台”。

## 谁开发了什么

这里有四个层次，需要分清楚：

| 组件 | 开发方 | 作用 |
| --- | --- | --- |
| MCP 协议 | Anthropic 提出并开源，现已被多个 AI 工具生态支持 | 定义 AI 应用如何连接外部工具、数据源和工作流 |
| Burp Suite | PortSwigger | Web 安全测试平台，负责代理、记录流量、重放请求、辅助测试 |
| Burp MCP Server 扩展 | PortSwigger | Burp 的官方 BApp 扩展，把 Burp 功能暴露为 MCP 工具 |
| Codex MCP Client 能力 | OpenAI Codex | 让 Codex 可以连接并调用本地或远程 MCP Server |

因此，“Burp Suite 跟 Codex 的这个 MCP”并不是某个第三方随便做的胶水项目。我们当前使用的是 PortSwigger 官方的 Burp MCP Server 扩展，再由 OpenAI Codex 的 MCP 客户端能力接入。

## MCP 本身是什么

MCP 是 Model Context Protocol 的缩写。它解决的是一个工程问题：

> AI Agent 不应该为每个外部系统都硬编码一套私有接口，而是通过统一协议发现工具、读取上下文、调用操作、拿回结果。

在 MCP 的模型里，通常有三类角色：

| 角色 | 在这套集成里的对应物 |
| --- | --- |
| MCP Client | Codex |
| MCP Server | Burp MCP Server 扩展，或 stdio proxy 背后的 Burp MCP 服务 |
| External System | Burp Suite 以及它能访问的 HTTP 流量、Repeater、Intruder、项目配置等 |

MCP Server 会向 Client 声明自己有哪些工具，例如“读取 HTTP 历史”“发送 HTTP 请求”“创建 Repeater tab”“做 URL/Base64 编码”等。Codex 拿到这些工具定义以后，可以在得到用户授权和当前环境允许的范围内，发起结构化工具调用。

关键点是：MCP 不是浏览器自动化，也不是屏幕点击自动化。它是工具级 API 调用。AI 不需要模拟鼠标去点 Burp UI，而是通过 Burp MCP 扩展暴露的工具直接操作 Burp 的能力。

## Burp MCP Server 是怎么工作的

Burp MCP Server 是一个 Burp 扩展。它被加载进 Burp 后，会在 Burp 里新增一个 `MCP` 配置页，并启动一个本地 MCP 服务。

默认情况下，这个服务监听：

```text
http://127.0.0.1:9876
```

有些 MCP Client 可以直接连接这个 HTTP/SSE 服务；有些 MCP Client 只支持 stdio 形式的 MCP Server。为兼容后者，PortSwigger 的扩展里还提供了一个 `mcp-proxy-all.jar`。

这个 proxy 的作用很简单：

```text
MCP stdio <-> MCP HTTP/SSE
```

也就是说，Codex 启动一个本地 Java 进程：

```bash
/home/ret2basic/.local/opt/BurpSuite/jre/bin/java \
  -jar /home/ret2basic/.local/share/burp/extensions/mcp-proxy-all.jar \
  --sse-url http://127.0.0.1:9876
```

Codex 以 stdio 方式跟这个 Java 进程通信，Java 进程再把请求转发给 Burp 里正在运行的 MCP Server。

Burp MCP Server 收到请求后，并不是自己重新实现一个代理或扫描器，而是调用 Burp 的扩展 API。Burp 的现代扩展 API 叫 Montoya API。它提供了访问 HTTP、Proxy、Repeater、Intruder、Decoder、Organizer、项目配置等功能的接口。Burp MCP Server 本质上就是把其中一部分能力包装成 MCP 工具。

## 实际请求如何流转

以“让 Codex 查看 Burp 代理历史中的请求”为例：

1. 用户在 Codex 里提出需求：查看 Burp HTTP history，找出可疑接口。
2. Codex 发现本地存在名为 `burp` 的 MCP Server。
3. Codex 向 MCP Server 查询可用工具列表。
4. Burp MCP Server 返回可用工具及参数 schema，例如读取 HTTP history、过滤 host、过滤 path、按正则搜索等。
5. Codex 选择合适工具并构造参数。
6. 工具调用先到达 `mcp-proxy-all.jar`。
7. proxy 转发到 `http://127.0.0.1:9876` 上的 Burp MCP Server。
8. Burp MCP Server 通过 Burp API 读取当前 Burp 项目里的 HTTP history。
9. Burp MCP Server 把结果作为 MCP 响应返回给 Codex。
10. Codex 对这些请求和响应做语义分析，提出下一步测试假设。

如果换成“发送一个变体请求验证 IDOR”，流程类似，只是 Burp MCP Server 最终调用的是 Burp 的 HTTP 发送能力。请求仍然会受 Burp MCP 的目标审批和安全配置约束。

## 它能做什么

PortSwigger 官方描述的 Burp MCP Server 能力包括：

- 从 AI Client 直接发送 HTTP/1.1 和 HTTP/2 请求。
- 访问并过滤 Proxy HTTP history 和 WebSocket history。
- 创建 Repeater tab。
- 把请求发送到 Intruder。
- 控制 Proxy intercept。
- 读取或修改项目配置和用户配置。
- 使用 URL、Base64 等编码工具。
- 生成随机字符串。
- 与 Organizer 条目交互。
- 使用目标审批系统限制 AI 可以访问或请求的目标。
- 在 Burp Professional 中使用 Collaborator 相关能力。

对我们来说，最重要的是前几类：

- 读取真实流量。
- 按 host、path、参数、状态码、响应特征做过滤。
- 重放请求。
- 自动生成变体请求。
- 把有价值的请求送进 Repeater 或 Intruder 做人工复核。
- 把黑盒测试证据变成后续白盒定位的线索。

## Community 版本下的边界

我们当前安装的是 Burp Suite Community。这个选择适合原型阶段，但要清楚边界：

| 能力 | Community 可用性 | 对我们的影响 |
| --- | --- | --- |
| Proxy 抓包 | 可用 | 足够作为黑盒流量入口 |
| HTTP history 分析 | 可用 | 足够做端点聚类和可疑点识别 |
| Repeater | 可用 | 足够做单点验证 |
| Intruder | Community 有限制 | 可以做少量验证，不适合作为大规模 fuzz 引擎 |
| Scanner | 不可作为核心依赖 | 我们不能依赖 Burp Pro 的主动扫描结果 |
| Collaborator | Professional only | OOB 类漏洞需要后续自建替代品或升级 Pro |
| Burp AI | 通常不是 Community 原型的核心能力 | 我们用自己的 AI Agent，不把 Burp AI 当基础依赖 |

这对我们的工具设计其实是好事：它迫使我们把核心能力建在“代理流量 + 可控重放 + 自己的推理和验证逻辑”上，而不是依赖 Burp Pro 扫描器。

## Burp 内置 AI 与这个 MCP 的关系

Burp 内置 AI 和 Burp MCP 是两条不同路线。

Burp 内置 AI 的价值在于它在 Burp UI 内部提供局部辅助，例如解释请求、辅助生成 payload、辅助分析某些扫描或手工测试上下文。它更像是 Burp 产品内部的一项智能功能。

而 MCP 的价值在于开放控制面：

```text
外部 AI Agent -> Burp 工具能力
```

对我们这个项目来说，MCP 更重要，因为我们的目标不是只在 Burp UI 里做一次审计，而是开发一个可复用的灰盒审计系统。这个系统要能：

- 从 Burp 读取流量。
- 自己维护测试状态和证据链。
- 自己决定下一步 probe。
- 在必要时读代码。
- 形成跨项目可复用的方法论和报告结构。

因此，在“Codex + Burp MCP”的架构里，Burp 内置 AI 不是核心依赖。它可以作为人工审计时的辅助功能存在，但不应该成为自动化链路的必要条件。

## 为什么不是直接写浏览器自动化

我们当然可以用 Playwright、Selenium 或 Puppeteer 直接操作浏览器。但它们解决的是另一个层面的问题：

| 工具 | 擅长的层面 |
| --- | --- |
| Playwright / Selenium | 模拟用户在浏览器里的交互 |
| Burp Suite | 观察、修改、重放、组织 HTTP/WebSocket 安全测试流量 |
| Burp MCP | 让 AI Agent 程序化使用 Burp 的安全测试能力 |

未来我们的工具可能同时使用浏览器自动化和 Burp MCP：

```text
Playwright 负责走业务流程
Burp 负责沉淀和操作安全测试流量
Codex/Agent 负责分析、规划、调度、归因
```

对于灰盒审计，Burp 的优势是它天然处在 HTTP 流量层。它能保留完整请求响应、cookie、header、重定向、WebSocket 消息、重复请求和人工修改痕迹。这比单纯浏览器自动化更适合作为安全审计的主工作台。

## 在我们灰盒工具里的定位

我们要做的是 Web2 + Web3 交叉场景的灰盒审计工具，但方法论上黑盒优先。

在这个架构里，Burp MCP 应该被当作“黑盒证据采集与验证执行层”：

```text
用户/浏览器/脚本产生流量
        |
        v
Burp Proxy 记录真实请求响应
        |
        v
Codex 通过 MCP 读取和分析流量
        |
        v
Agent 生成测试假设和变体请求
        |
        v
Burp MCP 发送请求或创建 Repeater/Intruder 任务
        |
        v
Agent 根据响应差异形成发现
        |
        v
必要时进入源码定位
```

白盒代码阅读只在这些情况下介入：

- 黑盒观察到了可疑行为，但不确定根因。
- 需要确认权限模型、签名校验、业务状态机或链上交互逻辑。
- 需要判断某个异常响应是前端校验、后端校验、网关限制还是链上合约限制。
- 需要为报告提供可修复的代码位置。
- 需要生成更精确的验证 payload。

这样可以避免纯白盒审计在大代码库里“从入口迷路”的问题，也能避免纯黑盒审计只看到现象、难以给出工程级修复建议的问题。

## 安全边界和风险控制

MCP 的能力越强，越要把边界设清楚。Burp MCP 能发送请求、读取历史、甚至在配置允许时修改 Burp 配置。因此我们应该默认采用保守配置：

- MCP 服务只监听 `127.0.0.1`。
- 不暴露到公网或共享网络。
- 默认关闭“允许修改 Burp 配置”的工具。
- 只给明确授权的目标配置 auto-approve。
- 对非本地、非测试环境目标保留人工审批。
- 记录每一次由 Agent 发起的 probe。
- 对破坏性测试、批量 fuzz、转账/下单/状态修改请求设置额外确认。
- 不把客户敏感流量发送给不受控的外部模型或日志系统。
- 报告里区分“观察到的现象”“自动化验证过的事实”“源码推断出的根因”。

尤其要注意 prompt injection 风险。Burp HTTP history 里的响应内容来自被测应用，理论上可能包含诱导 AI 执行危险操作的文本。Agent 读取这些内容时，必须把它们当作不可信数据，而不是系统指令。

## 我们当前机器上的部署状态

当前这台机器已经准备好的部分：

```text
Burp Suite:
  /home/ret2basic/.local/opt/BurpSuite

Burp 启动命令:
  /home/ret2basic/.npm-global/bin/burpsuite

Burp MCP extension:
  /home/ret2basic/.local/share/burp/extensions/burp-mcp-all.jar

MCP stdio proxy:
  /home/ret2basic/.local/share/burp/extensions/mcp-proxy-all.jar

Codex MCP server name:
  burp

Expected Burp MCP endpoint:
  http://127.0.0.1:9876
```

还需要在 GUI 里完成的动作：

1. 打开 Burp Suite。
2. 进入 `Extensions -> Installed -> Add`。
3. Extension type 选择 `Java`。
4. 加载 `/home/ret2basic/.local/share/burp/extensions/burp-mcp-all.jar`。
5. 打开 Burp 的 `MCP` tab。
6. 启用 MCP Server。
7. 确认 host 是 `127.0.0.1`，port 是 `9876`。
8. 先不要启用配置编辑工具。

启用以后，可以用下面命令验证：

```bash
curl --max-time 2 http://127.0.0.1:9876
curl --max-time 2 http://127.0.0.1:9876/sse
codex mcp list
codex mcp get burp
```

## 对后续工具设计的直接影响

基于这个原理，我们后续不应该把工具设计成“一个替代 Burp 的扫描器”。更合理的方向是：

```text
Burp 负责抓包、重放、承载人工工作流
Agent 负责分析、规划、生成 probe、维护证据链
代码索引器负责在必要时做源码定位
Web3 helper 负责链上状态、钱包签名、合约调用、事件日志等上下文
报告器负责把黑盒证据和白盒根因合并成可交付结论
```

第一阶段最有价值的功能不是“自动挖所有漏洞”，而是：

1. 从 Burp HTTP history 抽取端点、参数、身份态、响应特征。
2. 聚类出认证、资产、交易、钱包、管理、回调、链上交互相关接口。
3. 为每个接口生成传统 Web 安全测试假设。
4. 通过 Burp MCP 发起最小化、可回滚、可审计的 probe。
5. 把有异常差异的请求标成 suspicion。
6. 对每个 suspicion 再决定是否进入源码查看。

这就是我们要的“黑盒优先灰盒审计”。

## 参考资料

- PortSwigger BApp Store: [MCP Server](https://portswigger.net/bappstore/9952290f04ed4f628e624d0aa9dccebc)
- PortSwigger GitHub: [Burp Suite MCP Server Extension](https://github.com/PortSwigger/mcp-server)
- Model Context Protocol: [What is MCP?](https://modelcontextprotocol.io/docs/getting-started/intro)
- PortSwigger Montoya API: [MontoyaApi Javadoc](https://portswigger.github.io/burp-extensions-montoya-api/javadoc/burp/api/montoya/MontoyaApi.html)
- OpenAI Codex: [Configuration Reference](https://developers.openai.com/codex/config-reference)
