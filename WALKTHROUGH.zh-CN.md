# InferForge 中文 Walkthrough

这份文档解释当前仓库里的工具已经具备哪些主要功能，以及这些功能在代码里是怎么实现的。它面向后续开发和审计协作，不是漏洞报告，也不是运行授权书。

当前工具主体是：

```text
scripts/inferforge.py
```

默认测试靶场是：

```text
infrafi-web/
profiles/infrafi-web.json
```

默认本地目标是：

```text
http://127.0.0.1:3100
```

这里的 `3100` 是 `infrafi-web` 这个 Next.js 应用的本地目标端口，不是 Burp Proxy，也不是 Burp 内置浏览器端口。Burp Proxy 通常是 `127.0.0.1:8080`，Burp MCP 通常是 `127.0.0.1:9876`。

非常重要的运行限制：

- 不要碰端口 `2455`。它是当前环境里的 AI API load balancer 控制面路径，不是测试目标。
- 不要把 `2455` 加进 watch port、health check、readiness check、resource check、probe、reclaim candidate 或任何自动化测试参数。
- 不要停止、重启、kill、探测或健康检查 `2455` 背后的进程、容器、服务或端口。
- 不要伪造官方 evidence sidecar。没有真实授权证据时，工具只能生成 draft、template、preflight、readiness、blocked preview 和 handoff。

## 1. 总体定位

InferForge 不是一个普通源码扫描器，也不是 Burp Scanner 的包装器。它现在更像一个 Burp-first 的灰盒/黑盒漏洞研究工作流控制器。

它的核心目标有两套：

```text
greybox 模式：
  审计覆盖率优先。目标是覆盖所有危险 source-derived surface，尽量找全危险漏洞。

blackbox 模式：
  赏金有效性优先。目标是找到一个可以提交的 Medium/High/Critical 有效漏洞。
  不追求找全，只追求最高价值、最可证明、最可提交的一条路径。
```

这个分歧由 profile 里的 `assessment_mode` 和命令行全局参数控制：

```bash
python3 scripts/inferforge.py --assessment-mode greybox ...
python3 scripts/inferforge.py --assessment-mode blackbox ...
```

实现入口：

- `load_target_profile()`
- `normalize_target_profile()`
- `assessment_mode()`
- `assessment_mode_policy()`
- `resolve_run_context()`

这些函数负责加载 profile、合并默认值、解析目标 URL、解析源码根目录、解析 artifact 目录，并把 `--assessment-mode` override 写进当前 run context。

## 2. 核心架构

工具的核心抽象是：

```text
profile -> clusters -> strategy_sets -> probe_targets -> artifacts -> gates
```

### 2.1 Profile

Profile 是目标配置文件。默认 profile 是：

```text
profiles/infrafi-web.json
```

它描述：

- 目标名称和类型。
- 默认 URL 和源码根目录。
- 当前启用的策略集。
- endpoint cluster。
- 每个 cluster 的 path、method、kind、priority、source_refs。
- quote 请求体结构、quote 响应 transaction 提取路径、quote intent。
- Burp observation plan。
- WebSocket observation 配置。
- source peek 参考文件和 line pattern。
- 环境 readiness 检查。

当前默认 profile 的主要 cluster 是：

```text
health                  GET /health
quote                   POST /api/quote
solana-rpc-http         POST /api/rpc/solana/{cluster}
solana-rpc-ws           WS /api/rpc/solana/{cluster}
orca-pools              GET /api/orca/pools/{address}
```

实现入口：

- `load_target_profile()`
- `profile_summary()`
- `write_target_profile_artifact()`
- `build_strategy_registry_artifact()`
- `build_profile_validation_artifact()`
- `build_clusters()`

常用命令：

```bash
python3 scripts/inferforge.py --profile profiles/infrafi-web.json profile
```

主要输出：

```text
.greybox/target-profile.json
.greybox/strategy-registry.json
.greybox/profile-validation.json
.greybox/config.json
```

### 2.2 Artifact 目录

所有运行状态和证据索引默认写到：

```text
.greybox/
```

也可以通过全局参数换目录：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/discover-check ...
```

Artifact 是这个工具的记忆层。它不会只在 stdout 里吐结果，而是把每一步转成可被后续命令读取的 JSON、JSONL、Markdown 或 HTML。

常见 artifact：

```text
target-profile.json
endpoint-clusters.json
probe-plan.json
probe-ranking.json
probe-results.jsonl
burp-history-observations.jsonl
burp-mcp-sync.json
traffic-index.json
source-peek-results.json
evidence-gaps.json
evidence-chain.json
finding-gate.json
adjudication.json
verification-queue.json
review-blockers.json
artifact-manifest.json
artifact-health.json
transaction-intent.json
bounty-shortest-path.json
```

实现入口：

- `write_json()`
- `append_jsonl()`
- `load_jsonl()`
- `write_artifact_manifest()`
- `refresh_current_artifact_manifest()`
- `build_artifact_health()`

## 3. 安全边界和资源门禁

这是当前工具最重要的基础能力之一。很多命令不是直接执行动作，而是先判断：

- 当前资源是否健康。
- 命令是否涉及外部 probe。
- 命令是否包含 placeholder。
- 命令是否需要人工 review。
- 命令是否会触碰受保护控制面端口。
- 当前证据是否足够进入 finding gate。

### 3.1 不做的事情

工具默认不做：

- 不签钱包。
- 不提交 Solana transaction。
- 不跑 Burp Scanner。
- 不跑 Intruder 式大流量 fuzz。
- 不做 broad crawling。
- 不做破坏性状态变更。
- 不把 source-only signal 当成漏洞。
- 不把 draft/template 当成官方证据。
- 不在证据不足时生成可提交 findings。

默认 profile 里也有对应 safety 字段：

```json
{
  "no_wallet_signing": true,
  "no_transaction_submission": true,
  "no_burp_scanner": true,
  "no_broad_fuzzing": true
}
```

### 3.2 Resource snapshot

命令：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/discover-check \
  resource-snapshot --watch-port 3100 --strict
```

它读取本机 `/proc`：

- 内存。
- swap。
- TCP listener。
- top RSS process metadata。
- 可选 watch port 是否监听。
- 可疑的资源释放候选。

它不发送网络请求。

实现入口：

- `read_proc_meminfo()`
- `top_rss_processes()`
- `listening_tcp_ports()`
- `build_resource_snapshot()`
- `build_resource_budget()`
- `resource_gate_blocks_work()`
- `run_resource_snapshot()`

关键保护：

- `protected_control_plane_watch_ports()` 会拒绝受保护控制面端口。
- `protected_control_plane_port_for_process()` 会从 process name 和 command preview 里识别受保护端口。
- `resource_snapshot_visible_processes()` 会过滤控制面进程。
- `resource_release_candidates()` 不会把控制面进程作为内存释放候选。

### 3.3 命令安全分类

工具会把生成的命令模板分成：

```text
ready              可以本地运行的 no-write/offline 命令
manual-template    含 REPLACE_WITH_* 之类 placeholder，需要人工替换
review-gated       需要证据、授权或 review 后才能运行
resource-gated     资源门禁未过
external-probe     涉及外部或 active probe，需要额外审查
unsafe-template    含危险 shell 操作符、重定向、受保护端口等
```

实现入口：

- `protected_control_plane_ports_in_command()`
- `classify_verification_command()`
- `validation_command_ref()`
- `command_safety_summary()`
- `format_command_safety_summary()`
- `build_command_safety_selftest()`

自测命令：

```bash
python3 scripts/inferforge.py self-test-command-safety
```

这套分类贯穿：

- verification queue。
- review blockers。
- bounty action queue。
- bounty shortest path。
- transaction evidence readiness。
- quote capture handoff。
- rewrite response approval packet。

## 4. 静态发现和灰盒 profile 生成

命令：

```bash
python3 scripts/inferforge.py --source-root ./some-nextjs-app discover-profile
```

它不发 HTTP 请求，只读源码。

它能发现：

- Next.js App Router route handler。
- Pages Router API route。
- `next.config.*` rewrites。
- redirects。
- headers。
- middleware/proxy。
- custom server WebSocket upgrade handler。
- `'use server'` Server Action 文件。
- basePath、trailingSlash、i18n locale 的 runtime path variant。
- 固定 upstream fetch。

实现入口：

- `discover_nextjs_routes()`
- `app_roots()`
- `nextjs_route_path()`
- `pages_api_roots()`
- `nextjs_pages_api_path()`
- `discover_next_config_runtime()`
- `discover_nextjs_rewrites()`
- `discover_nextjs_middleware()`
- `discover_nextjs_server_actions()`
- `discover_next_config_route_policies()`
- `discover_custom_server_entrypoints()`
- `infer_route_strategy()`
- `merge_discovered_clusters()`
- `build_probe_targets_from_clusters()`
- `build_discovered_profile()`

生成的 starter profile 包含：

- `clusters`
- `probe_targets`
- `source_peeks`
- `burp_observation_plan`
- `review_observation_candidates`
- `websocket_observation`

输出：

```text
.greybox/route-inventory.json
.greybox/discovered-profile.json
.greybox/discovered-profile-validation.json
```

### 4.1 Review-only candidate

对 catch-all rewrite、fixed upstream proxy、动态路径等不能盲目跑的 surface，工具会生成 review-only candidate。

命令：

```bash
python3 scripts/inferforge.py \
  --profile .greybox/discovered-profile.json \
  review-candidates --no-write
```

实现入口：

- `build_rewrite_review_observation_candidate()`
- `review_observation_candidates_for_cluster()`
- `collect_review_observation_candidates()`
- `run_review_candidates()`

这些 candidate 不会自动执行。要先选一个具体、只读、in-scope 的本地 path，再 promote：

```bash
python3 scripts/inferforge.py \
  --profile .greybox/discovered-profile.json \
  promote-observation-candidate \
  --candidate-id review_observe_route_api_infrafi_path_approved_path \
  --path /api/infrafi/status \
  --no-write
```

实现入口：

- `validate_candidate_promotion_path()`
- `promote_review_observation_candidate()`
- `run_promote_observation_candidate()`

Promotion 只是 profile edit，不会发送 HTTP 请求。

## 5. Burp 集成和黑盒流量导入

Burp 是这个工具的黑盒证据入口。

当前预期链路：

```text
Burp built-in browser -> Burp Proxy -> Burp HTTP history
Codex/InferForge -> Burp MCP -> history import -> normalized observations
```

Burp 内置浏览器本身已经走 Burp Proxy；自动化重复运行时通常要保持 Proxy Intercept off。Intercept on 适合人工 pause/edit/forward，不适合无人值守同步。

### 5.1 Burp capability 检查

命令：

```bash
python3 scripts/inferforge.py capabilities
```

它检查：

- 目标 health。
- Burp MCP 是否可用。
- Burp Proxy 是否可用。
- MCP 工具列表。
- 是否有 HTTP history、WebSocket history、Intercept 控制等能力。

实现入口：

- `build_capabilities()`
- `McpSseClient`
- `summarize_burp_mcp_tool_inventory()`
- `run_capabilities()`

输出：

```text
.greybox/burp-capabilities.json
```

### 5.2 生成 Burp observation 流量

命令：

```bash
python3 scripts/inferforge.py burp-observe
```

它通过 Burp Proxy 发送 profile 里定义的低流量 observation plan，例如：

- `GET /health`
- `POST /api/quote` 的无效 body 观察。
- `POST /api/rpc/solana/devnet` 的 `getHealth`。
- `GET /api/orca/pools/not-an-address`。
- 可选一次 WebSocket upgrade。

实现入口：

- `build_burp_observation_plan()`
- `run_burp_observe()`
- `http_request_through_proxy()`
- `run_ws_upgrade_observation_through_proxy()`
- `TargetProbeLock`

输出：

```text
.greybox/burp-observation-run.json
```

### 5.3 自动同步 Burp MCP history

命令：

```bash
python3 scripts/inferforge.py burp-sync --replace
```

或者先发送 observation 再同步：

```bash
python3 scripts/inferforge.py burp-sync --observe --replace
```

`burp-sync` 会：

- 做资源门禁。
- 默认把 Proxy Intercept 关掉，除非指定 `--keep-intercept-state`。
- 读取 Burp MCP HTTP history。
- 优先使用 regex history tool。
- fallback 到普通 history tool。
- 按 target host 和 observation regex 过滤。
- 默认不持久化 raw MCP history，只记录 byte count 和 SHA256。
- 导入为标准化 observation。
- 从 quote 响应里抽取 transaction candidate。
- 刷新 traffic index 和 transaction intent。

实现入口：

- `run_burp_sync()`
- `McpSseClient`
- `list_mcp_tools_with_audit()`
- `call_mcp_history_tool_with_inventory()`
- `append_mcp_action_audit()`
- `import_burp_history_inputs()`

输出：

```text
.greybox/burp-mcp-sync.json
.greybox/burp-history-observations.jsonl
.greybox/burp-transaction-candidates.json
.greybox/traffic-index.json
.greybox/transaction-intent.json
.greybox/collection-summary.json
```

### 5.4 离线导入 Burp raw history

命令：

```bash
python3 scripts/inferforge.py import-burp-history --input ./burp-history.txt --replace
```

它适合已有 raw MCP output 的情况。默认每个输入有 byte cap，避免把巨大 Burp export 塞进小 VPS 内存。

实现入口：

- `read_text_file_limited()`
- `parse_burp_mcp_history_items()`
- `normalize_burp_history_items()`
- `extract_transaction_candidates_from_burp_items()`
- `dedupe_observations()`
- `import_burp_history_inputs()`
- `run_import_burp_history()`

## 6. 黑盒 profile 和被动资产发现

### 6.1 从 Burp 历史生成纯黑盒 profile

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-profile \
  --output profiles/in-scope-example-blackbox.json
```

它只读取：

```text
burp-history-observations.jsonl
```

不发请求。

它会：

- 过滤非目标 host。
- 默认跳过静态资源。
- 跳过 WebSocket observation。
- 按 path 聚合 endpoint。
- 保留 query 参数名但去掉 query 值。
- 生成 `blackbox-http-observed` cluster。
- 设置 `assessment_mode: blackbox`。

实现入口：

- `blackbox_profile_path()`
- `blackbox_query_keys()`
- `is_static_asset_path()`
- `blackbox_cluster_id_for_path()`
- `blackbox_endpoint_kind()`
- `blackbox_endpoint_priority()`
- `build_blackbox_profile_from_history()`
- `run_blackbox_profile()`

### 6.2 从页面和同源 JS 中提取候选 endpoint

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-map \
  --scope-host in-scope.example \
  --force
```

它会低流量 GET：

- 目标页面。
- 少量同源 script asset。

它不会请求候选 endpoint。

它会提取：

- API-like path。
- WebSocket URL。
- GraphQL/quote/order/account/trade/market 等高价值 token。
- runtime config host。
- 外部 script host。
- query parameter names。
- source URL hash。

实现入口：

- `html_script_srcs()`
- `extract_blackbox_asset_candidates_from_text()`
- `triage_blackbox_asset_candidate()`
- `build_config_host_map()`
- `config_host_impact_hypotheses()`
- `build_blackbox_asset_map()`
- `run_blackbox_asset_map()`

输出：

```text
.greybox/in-scope-example/blackbox-asset-candidates.json
```

### 6.3 从资产候选生成 profile

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-profile \
  --force
```

默认只 promote 低风险 page-route candidate。API、WebSocket、敏感和 state-changing candidate 仍然留在 review queue。

实现入口：

- `blackbox_route_family()`
- `blackbox_route_variant_rank()`
- `build_blackbox_profile_from_asset_candidates()`
- `run_blackbox_asset_profile()`

输出：

```text
.greybox/in-scope-example/blackbox-asset-profile.json
```

## 7. Scope policy、WebSocket、takeover 和 lead portfolio

### 7.1 Scope policy

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  scope-policy \
  --scope-host in-scope.example \
  --source-url https://example.com/program-scope
```

它把赏金项目的 host scope 转成 local policy artifact。

实现入口：

- `normalize_scope_host()`
- `build_scope_policy()`
- `scope_policy_decision_map()`
- `run_scope_policy()`

输出：

```text
.greybox/scope-policy.json
```

### 7.2 Bounty program profile

命令：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/edgex \
  immunefi-program-profile --program-slug edgex \
  --show-assets --show-impacts --show-techniques --show-links
```

本地页面导入模式：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/edgex \
  immunefi-program-profile --program-slug edgex \
  --input-dir ./program-pages --no-fetch \
  --show-impacts --show-techniques
```

`immunefi-program-profile` 的作用是先读赏金项目页面，再决定黑盒策略。它不是从代码或流量里猜目标，而是先把 Immunefi 风格的公开项目页结构化：

- `information` 页面：项目名、最高赏金、上线时间、更新时间、`Triaged by Immunefi`、`PoC Required`、`KYC required`、奖励等级、项目介绍、PoC/KYC/禁止活动等段落。
- `scope` 页面：`Assets in Scope`、`Impacts in Scope`、`Out of scope`。
- `resources` 页面：文档、审计报告、GitHub、已知问题等链接。

实现入口：

- `BountyProgramHTMLExtractor`
- `bounty_program_extract_text_and_links()`
- `immunefi_program_slug_from_url()`
- `immunefi_program_urls()`
- `read_immunefi_program_pages()`
- `build_immunefi_program_page()`
- `build_immunefi_program_profile()`
- `run_immunefi_program_profile()`

页面读取逻辑：

1. `--program-slug edgex` 会生成三个标准 URL：`/information/`、`/scope/`、`/resources/`。
2. 如果传了 `--information-input`、`--scope-input`、`--resources-input`，优先读取这些本地文件。
3. 如果传了 `--input-dir`，会自动寻找 `information.html/txt/md`、`scope.html/txt/md`、`resources.html/txt/md`。
4. 如果没有本地文件且没有 `--no-fetch`，才会低频读取 Immunefi 公开页面。
5. 如果用了 `--no-fetch` 但缺文件，对应页面标记为 `missing-input`，不会访问网络。

HTML 解析逻辑：

- `BountyProgramHTMLExtractor` 跳过 `script/style/template/noscript`。
- 对 `div/section/table/tr/td/li/h1-h6` 等块级标签插入换行，让页面变成可解析的文本行。
- 对 `<a href>` 解析绝对 URL、host、path、link text 和 URL hash。
- `bounty_program_text_lines()` 统一清理空白、去掉空行。
- `bounty_program_sections()` 按固定标题抽取段落，例如 `Rewards by Threat Level`、`Program Overview`、`Prohibited Activities`、`Assets in Scope`、`Impacts in Scope`、`Out of scope`。

Scope 解析逻辑：

- `extract_immunefi_assets()` 从 `Assets in Scope` 中抽取资产名和添加日期，并把 scope 页里的资产链接按顺序配成 `target_url`、`target_host`、`target_path`。
- `extract_immunefi_impacts()` 从 `Impacts in Scope` 中抽取 severity 和 impact title。
- `extract_immunefi_out_of_scope()` 从 `Out of scope` 中抽取规则条目。
- `bounty_program_declared_total()` 会读取页面声明的 `Total Assets in Scope` 或 `Total Impacts in Scope`。

如果页面声明有 15 个 impact，但静态 HTML 只解析到 5 个，artifact 会标记为：

```text
status=partial-needs-review
impacts_completeness=partial-static-page-or-pagination
manual_input_recommended=true
```

这样工具不会假装已经读完整个赏金范围。正确做法是用浏览器打开页面，点开 `Show all` 或分页后，把渲染后的 HTML/text 存成 `scope.html` 或 `scope.txt`，再用 `--input-dir --no-fetch` 重新导入。

最关键的是 Impact 到攻击技术的逆向映射：

- `Executing arbitrary system commands` 会映射到 command injection、unsafe template/render、upload/render pipeline 等 RCE 路径。
- `Retrieve sensitive data/files` 会映射到 LFI/path traversal、SSRF、object authorization disclosure、cache/tenant 边界。
- `Taking down the application/website` 会映射到 availability/resource-control，但验证边界强制是源码、单请求上界或 operator evidence，不允许压力测试。
- `Taking state-modifying authenticated actions on behalf of other users` 会映射到 BOLA/BOPLA、workflow precondition bypass、stored/reflected XSS 带会话动作等路径。
- `Direct theft of user funds` 或恶意交易类 impact 会映射到 transaction argument integrity、withdrawal/order authorization、nonce/replay、签名校验和 account binding。
- `Subdomain takeover` 会映射到 dangling DNS/provider takeover，但只允许检查显式 in-scope host，不允许接管第三方资源。

实现入口：

- `impact_attack_techniques_for_impact()`
- `impact_out_of_scope_notes()`
- `build_impact_attack_matrix()`

每条 technique 都包含：

```text
id
attack_family
why_this_maps_to_impact
blackbox_signals
greybox_source_signals
safe_validation_boundary
forbidden_actions
out_of_scope_notes
```

这让工具能把“赏金项目愿意付钱的影响”变成“优先找哪些边界”的策略，而不是平均扫描所有问题。对黑盒赏金来说，这比追求全覆盖更符合目标：优先找 valid、高危、能提交的洞。

输出：

```text
.greybox/bounty-program-profile.json
```

这个 artifact 后续应该成为黑盒策略入口之一：先确认哪些 assets 和 impacts 真正在 scope 内，再让 lead portfolio、methodology review、bounty action queue 优先围绕高赏金 impact 组织验证路径。

### 7.3 WebSocket candidate review

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  websocket-candidate-review --no-write
```

可选 `--handshake-baseline` 时只做 handshake，不发送 WebSocket frame、subscription、wallet payload 或 trading message。

实现关注点：

- 静态资产里的 WebSocket URL。
- scope 状态。
- 同源/跨域。
- header forwarding 源码 review。
- sensitive client header 风险。
- handshake-only baseline。

### 7.4 Host takeover baseline

命令：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  host-takeover-baseline \
  --host in-scope.example
```

它只检查显式 host，不枚举子域。

实现入口：

- `dns_records_for_host()`
- `takeover_provider_hints()`
- `takeover_http_fingerprints()`
- `build_host_takeover_baseline()`
- `run_host_takeover_baseline()`

### 7.5 Lead portfolio

命令：

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  lead-portfolio --no-write
```

它离线合并：

- asset candidates。
- WebSocket candidates。
- runtime config hosts。
- external script hosts。
- scope policy。
- takeover baseline。
- generated asset profile。

这是线索队列，不是 evidence。

实现入口：

- `build_lead_portfolio()`
- `run_lead_portfolio()`

## 8. Probe plan 和 audit 引擎

### 8.1 Plan

命令：

```bash
python3 scripts/inferforge.py plan --no-write
```

它只生成 probe plan，不执行 probe。

实现入口：

- `Probe`
- `build_probe_plan()`
- `build_probe_ranking()`
- `apply_probe_ranking()`
- `select_cluster_ids()`
- `run_plan()`

`Probe` 包含：

```text
id
label
method
path
body
origin
content_type
expected_statuses
category
external
policy_field
risk
strategy_set
```

当前 probe 覆盖：

- Next.js generic route 的 HEAD、OPTIONS、GET method confusion。
- Quote API 本地 schema/policy validation。
- Solana RPC source/origin/method/content-type/body/batch/duplicate-key controls。
- Invalid transaction payload 的本地拒绝或 JSON-RPC error gate。
- Orca fixed-upstream route 的 address shape、traversal、extra segment、method confusion。
- 可选 external quote provider validation。
- 可选 WebSocket probe。

### 8.2 Audit

命令：

```bash
python3 scripts/inferforge.py audit --no-ws
```

`audit` 是综合运行入口，会：

1. 写 target profile artifact。
2. 做资源门禁。
3. 读取已有 Burp observations。
4. 构建 endpoint clusters。
5. 选择 cluster。
6. 构建 probe plan 和 ranking。
7. 拿 target lock。
8. 做 warmup。
9. 执行 HTTP probe。
10. 可选执行 WebSocket probe。
11. 写 probe results。
12. 生成 response delta、traffic index、source peek、transaction intent、RPC method policy、deployment review、suspicions、finding gate、coverage、evidence chain、adjudication、verification queue、review blockers、report 和 manifest。

实现入口：

- `run_audit()`
- `run_audit_warmup()`
- `run_http_probes()`
- `run_ws_probes()`
- `run_ws_resource_probes()`
- `build_probe_results_summary()`
- `build_response_delta_analysis()`
- `build_traffic_index()`
- `build_suspicions()`
- `build_finding_gate()`
- `build_findings()`
- `build_hardening_notes()`
- `build_adjudication()`
- `generate_report()`

输出很多，最关键是：

```text
probe-results.jsonl
probe-results-summary.json
response-delta-analysis.json
traffic-index.json
source-peek-results.json
transaction-intent.json
rpc-method-policy.json
suspicions.json
finding-gate.json
findings.json
hardening-notes.json
blackbox-coverage.json
evidence-chain.json
adjudication.json
verification-queue.json
review-blockers.json
report.md
index.html
artifact-manifest.json
```

## 9. Source peek 和 evidence chain

Source peek 不是全量源码审计。它的目标是：黑盒证据或 evidence gap 提出一个具体问题后，读取有限源码片段回答这个问题。

### 9.1 Source peek request

命令：

```bash
python3 scripts/inferforge.py source-peek-requests
```

它解释为什么需要看源码：

- Burp/probe 观察到 endpoint。
- suspicion 需要定位。
- evidence gap 需要解释。
- Server Action 是 source-only surface。

输出：

```text
.greybox/source-peek-requests.json
```

### 9.2 Source peek result

命令：

```bash
python3 scripts/inferforge.py source-peek --no-write
```

它按 profile 里的 `source_peeks` 和 source-peek-requests 读取有限源码片段。

输出：

```text
.greybox/source-peek-results.json
```

实现入口：

- `build_source_peek_requests()`
- `build_source_peeks()`
- `source_ref_to_path()`
- `source_ref_for_artifact()`

### 9.3 Evidence chain

命令：

```bash
python3 scripts/inferforge.py evidence-chain
```

它把 cluster、Burp observations、safe probes、source peek、finding gate、coverage、evidence gaps 串起来。

输出：

```text
.greybox/evidence-chain.json
```

实现入口：

- `build_evidence_chain()`
- `run_evidence_chain()`

## 10. Coverage、response delta、verification queue 和 blockers

### 10.1 Coverage

命令：

```bash
python3 scripts/inferforge.py coverage
python3 scripts/inferforge.py burp-observation-coverage
python3 scripts/inferforge.py discovery-coverage
```

分别回答：

- 黑盒证据覆盖是否足够。
- Burp observation 是否覆盖 profile cluster。
- 静态发现的 surface 是否被 profile、probe、Burp observation 或 review gate 覆盖。

实现入口：

- `build_blackbox_coverage()`
- `build_burp_observation_coverage()`
- `build_discovery_coverage()`

输出：

```text
blackbox-coverage.json
burp-observation-coverage.json
discovery-coverage.json
```

### 10.2 Response delta

命令：

```bash
python3 scripts/inferforge.py response-deltas
```

它基于 `probe-results.jsonl` 分析 status、hash、body shape、retry、transport error 变化。

输出：

```text
response-delta-analysis.json
```

实现入口：

- `build_response_delta_analysis()`
- `run_response_deltas()`

### 10.3 Verification queue

命令：

```bash
python3 scripts/inferforge.py verification-queue --no-write --show-commands
```

它把 evidence appendix、coverage、adjudication、evidence gaps 变成下一步队列。

队列项会区分：

- ready offline command。
- active follow-up。
- blocked-resource。
- manual-review。
- blocked-external。
- profile update。

输出：

```text
verification-queue.json
reproduction-steps.md
```

实现入口：

- `build_verification_queue()`
- `write_reproduction_steps()`
- `run_verification_queue()`
- command safety 相关函数。

### 10.4 Review blockers

命令：

```bash
python3 scripts/inferforge.py review-blockers --no-write
```

它把各种人工/外部/证据 blocker 聚合：

- discovery coverage blocker。
- Burp observation blocker。
- verification queue blocker。
- source-peek request。
- environment readiness。
- artifact health。
- blocked finding-gate preview。

输出：

```text
review-blockers.json
review-blockers.md
```

实现入口：

- `build_review_blockers()`
- `write_review_blockers_markdown()`
- `run_review_blockers()`

## 11. Finding gate 和 adjudication

工具不会把 suspicion 直接变成 finding。路径是：

```text
suspicion -> finding gate -> adjudication -> findings / hardening notes
```

### 11.1 Finding gate

命令：

```bash
python3 scripts/inferforge.py gate --no-write --show-items
```

它判断 candidate 是否具备：

- 具体 entrypoint。
- 可复现证据。
- 影响证明。
- scope 和授权上下文。
- 对应 validation oracle。
- 缺失证据 blocker。

输出：

```text
finding-gate.json
```

实现入口：

- `build_finding_gate()`
- `run_gate()`

### 11.2 Adjudication

命令：

```bash
python3 scripts/inferforge.py adjudicate
```

它执行最终 reportability contract：

- 只有 finding gate 通过的 `valid-finding` 能进 `findings.json`。
- hardening note 单独放进 `hardening-notes.json`。
- evidence 不足时保持 no finding。

输出：

```text
adjudication.json
findings.json
hardening-notes.json
```

实现入口：

- `build_adjudication()`
- `build_findings()`
- `build_hardening_notes()`
- `run_adjudicate()`

## 12. Bounty 工作流

这是最近扩展最多的部分。它的目标是：在 blackbox 赏金模式里，不追求全覆盖，而是找最短路径到一个可提交的 Medium/High/Critical 报告。

当前状态要明确：

```text
还没有可提交的 Medium/High/Critical 漏洞。
当前最高价值路径是 POST /api/quote -> transaction integrity。
当前 blocker 是缺少官方授权的最小 quote capture 和配套 sidecar。
```

### 12.1 Methodology review

命令：

```bash
python3 scripts/inferforge.py methodology-review \
  --no-write --show-commands --show-poc-plan --skip-current-resource-check
```

它把当前 artifacts 映射到业务逻辑测试维度：

- data validation。
- request forgery。
- integrity checks。
- workflow circumvention。
- misuse/function-use limits。
- transaction intent mismatch。
- provider impact。
- resource control。

实现入口：

- `build_methodology_review()`
- `build_bounty_harness_alignment()`
- `build_bounty_validation_funnel()`
- `build_bounty_iteration_strategy()`
- `run_methodology_review()`

### 12.2 Lead dossier

命令：

```bash
python3 scripts/inferforge.py lead-dossier \
  --no-write --show-commands --show-evidence --skip-current-resource-check
```

它生成 bug-bounty 风格 lead file：

- source refs。
- path/method。
- expected severity。
- evidence gap。
- validation oracle。
- objective alignment。
- safe offline commands。
- forbidden actions。

实现入口：

- `build_lead_dossier()`
- `run_lead_dossier()`

### 12.3 Harness loop 和 hypothesis matrix

命令：

```bash
python3 scripts/inferforge.py harness-loop --no-write --skip-current-resource-check
python3 scripts/inferforge.py hypothesis-matrix --no-write --show-next
```

`harness-loop` 看整体阶段：

```text
discovery/recon
lead generation
finding identification
issue validation
PoC/reporting
```

`hypothesis-matrix` 排序下一批研究问题：

- transaction-flow-review。
- credential-proxy-review。
- resource-abuse-review。
- rewrite-response-review。
- WebSocket header-forwarding。

实现入口：

- `build_harness_loop()`
- `build_hypothesis_matrix()`
- `run_harness_loop()`
- `run_hypothesis_matrix()`

### 12.4 Validation plan 和 iteration decision

命令：

```bash
python3 scripts/inferforge.py validation-plan --no-write --show-commands
python3 scripts/inferforge.py iteration-decision --no-write --show-commands
```

它们把 hypothesis 变成有 gate 的下一步：

- allowed commands。
- required evidence。
- stop conditions。
- forbidden actions。
- resource gate。
- command safety。
- active/offline 分流。

实现入口：

- `build_validation_plan()`
- `build_iteration_decision()`
- `run_validation_plan()`
- `run_iteration_decision()`

### 12.5 Bounty lane pipeline

这组命令是赏金路径的多层门禁：

```bash
python3 scripts/inferforge.py bounty-frontier --no-write
python3 scripts/inferforge.py bounty-validation-gates --no-write
python3 scripts/inferforge.py bounty-invalidity-review --no-write --show-reasons
python3 scripts/inferforge.py bounty-readiness-rollup --no-write
python3 scripts/inferforge.py bounty-evidence-workorders --no-write
python3 scripts/inferforge.py bounty-source-invariants --no-write
python3 scripts/inferforge.py bounty-lane-priorities --no-write --show-lanes
python3 scripts/inferforge.py bounty-evidence-authorization --no-write
python3 scripts/inferforge.py bounty-evidence-intake --no-write
python3 scripts/inferforge.py bounty-action-queue --no-write --show-actions --show-commands
python3 scripts/inferforge.py bounty-shortest-path --no-write --show-requests --show-commands
```

各层职责：

```text
bounty-frontier:
  找 Medium+ frontier，仍然只是候选边界。

bounty-validation-gates:
  把 frontier 映射成严格 validation gate。

bounty-invalidity-review:
  反向审查现在提交为什么会 invalid。

bounty-readiness-rollup:
  汇总 lane readiness、invalidity、adjudication。

bounty-evidence-workorders:
  把 blocker 变成 bounded 官方证据工单。

bounty-source-invariants:
  说明本地源码能证明什么，不能证明什么。

bounty-lane-priorities:
  按 severity、source strength、evidence distance、invalidity risk 排序 lane。

bounty-evidence-authorization:
  生成给人工/operator 的授权问题和 evidence request。

bounty-evidence-intake:
  检查证据文件是否存在、格式是否正确、是否有 redaction 风险。

bounty-action-queue:
  产出下一步 agent/human action queue。

bounty-shortest-path:
  用最短路径视角告诉我们离一个有效 Medium+ 报告还差什么。
```

实现入口：

- `build_bounty_frontier()`
- `build_bounty_validation_gates()`
- `build_bounty_invalidity_review()`
- `build_bounty_readiness_rollup()`
- `build_bounty_evidence_workorders()`
- `build_bounty_source_invariants()`
- `build_bounty_lane_priorities()`
- `build_bounty_evidence_authorization()`
- `build_bounty_evidence_intake()`
- `build_bounty_action_queue()`
- `build_bounty_shortest_path()`
- `build_bounty_platform_submission_gate()`

关键规则：

- source-positive 不是 finding。
- missing official evidence 时，validation command 只能作为 blocked preview。
- `autorunnable_*_commands` 只有在 evidence gate 通过后才暴露。
- platform submission gate 必须看到 evidence、finding gate、adjudication、invalidity、severity、redaction hygiene 都通过，才会允许提交。

### 12.6 Bounty evidence prep

命令：

```bash
python3 scripts/inferforge.py bounty-prep-package --no-write
python3 scripts/inferforge.py bounty-prep-sync --no-write --show-checks --show-details
python3 scripts/inferforge.py bounty-evidence-request --no-write
python3 scripts/inferforge.py bounty-evidence-templates --no-write
python3 scripts/inferforge.py bounty-template-safety --no-write
```

它们用于生成人类可读 brief、draft template 和 safety check。

实现入口：

- `build_bounty_prep_package()`
- `build_bounty_prep_sync()`
- `build_bounty_evidence_request_brief()`
- `build_bounty_evidence_templates()`
- `build_bounty_template_safety()`

重点：

- templates 是 draft-only。
- drafts 不能复制成 official sidecar。
- template safety 会阻止把 placeholder 当成证据。

## 13. `/api/quote -> transaction integrity` 专线

这是当前最高价值路径。工具已经围绕它实现了完整证据链，但是缺少真实授权 quote capture。

目标证明模型：

```text
用户发起一个明确的 quote intent:
  wallet
  buy/sell direction
  source mint
  destination mint
  raw amountIn
  optional minDestinationAmount
  maxNumQuotes

服务端返回 executable Solana transaction payload。

工具离线 decode payload，验证：
  signer 是不是预期 wallet
  source/destination mint 是否符合 intent
  source/destination token account 是否符合预期
  transfer amount 是否符合 amountIn/minDestinationAmount
  compiled instruction program 是否在 allowlist
  priority fee 是否在 policy 上限
  address lookup / token metadata 是否需要补充 public metadata

如果出现 concrete mismatch，才可能进入 finding gate。
```

### 13.1 Source flow review

命令：

```bash
python3 scripts/inferforge.py transaction-flow-review --no-write --top 8
```

它只读源码，寻找：

- remote quote payload。
- `VersionedTransaction.deserialize`。
- wallet `sendTransaction`。
- preview wallet 与 execution wallet 的边界。
- request key allowlist。
- mint/amount/recipient/maxNumQuotes guard。
- credentialed upstream proxy。

实现入口：

- `build_transaction_flow_review()`
- `run_transaction_flow_review()`

输出：

```text
transaction-flow-review.json
```

### 13.2 Quote capture guide

命令：

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  approved-quote-capture-guide --show-commands
```

它告诉 operator 需要准备什么：

- 一个唯一的 `POST /api/quote` request body。
- 匹配 response body。
- 如果有 transaction/payload/swapTransaction 字段，要保留。
- approval reference。
- wallet/test wallet public address。
- buy/sell direction。
- input/output mint。
- raw input amount。

不能包含：

- private key。
- seed phrase。
- wallet signature。
- bearer token。
- cookie。
- raw auth traffic。
- full Burp history。
- unrelated authenticated traffic。
- submitted transaction receipt。

实现入口：

- `build_approved_quote_capture_guide()`
- `run_approved_quote_capture_guide()`

这个命令只读，不写 official sidecar。

### 13.3 Redact approved quote capture

命令：

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  redact-approved-quote-capture \
  --input ./approved-quote.har \
  --show-commands
```

它支持：

- HAR。
- Burp XML item export。
- raw HTTP exchange。
- JSON-wrapped exchange。
- cURL + response。

它会：

- 找唯一 `POST /api/quote` request。
- 找匹配 response。
- 移除 `Cookie`、`Authorization`、`Set-Cookie`、API key、token、secret、private key、seed phrase 风格 headers。
- 默认 preview。
- `--write-redacted-capture` 时只写 supporting redacted capture 到 operator inputs 目录，不写 official sidecar。

实现入口：

- `build_redacted_approved_quote_capture()`
- `run_redact_approved_quote_capture()`

### 13.4 Staged exchange candidate scanner

命令：

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  approved-quote-exchange-candidates --show-commands
```

或者指定文件：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  approved-quote-exchange-candidates \
  --input ./approved-quote.har \
  --show-commands
```

它会：

- 扫描 `.greybox/discover-check/operator-inputs/`。
- 支持子目录，限制深度和文件数。
- 识别 importable exchange。
- 区分 parser importable 和 hygiene passed。
- 如果有 cookie/auth header，则 hygiene 是 `needs-redaction-review`。

实现入口：

- `find_approved_quote_exchange_candidates()`
- `approved_quote_exchange_staging_contract()`
- `approved_quote_exchange_staging_hygiene_summary()`
- `run_approved_quote_exchange_candidates()`

### 13.5 Prepare approved quote operator inputs

命令：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  prepare-approved-quote-operator-inputs \
  --exchange-input ./approved-quote.har \
  --approval-reference APPROVED-QUOTE-001 \
  --no-write --show-preflight --show-commands
```

它把一个 approved exchange 拆成 supporting operator inputs：

```text
approved-quote-request.json
approved-quote-response.json
approved-quote-intent.json
```

默认不写。加 `--write-operator-inputs` 才写到：

```text
.greybox/discover-check/operator-inputs/
```

这仍然不是 official evidence sidecar。

实现入口：

- `read_transaction_corpus_pair_inputs()`
- `build_approved_quote_operator_input_import()`
- `build_generated_approved_quote_intent_input()`
- `write_approved_quote_operator_inputs()`
- `run_prepare_approved_quote_operator_inputs()`

### 13.6 Corpus preflight

命令：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  transaction-corpus-preflight \
  --request-input .greybox/discover-check/operator-inputs/approved-quote-request.json \
  --payload-input .greybox/discover-check/operator-inputs/approved-quote-response.json \
  --intent-input .greybox/discover-check/operator-inputs/approved-quote-intent.json \
  --no-write --show-policy-json --show-checks --show-commands
```

它检查：

- request JSON 是否符合 profile 的 quote_request policy_fields。
- direction 是否能从 mint pair 推导。
- approved intent 是否匹配 request。
- response/payload 是否有唯一 transaction candidate。
- payload type 是否符合 `quote_response.expected_payload_type`。
- amountIn、amountOut、mint、chain、recipient、quote count 是否能绑定。
- official sidecar target path。
- follow-up command safety。

实现入口：

- `build_transaction_corpus_preflight()`
- `run_transaction_corpus_preflight()`

### 13.7 Prepare official transaction sidecars

命令：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  prepare-transaction-corpus-sidecars \
  --request-input .greybox/discover-check/operator-inputs/approved-quote-request.json \
  --payload-input .greybox/discover-check/operator-inputs/approved-quote-response.json \
  --intent-input .greybox/discover-check/operator-inputs/approved-quote-intent.json \
  --approval-reference APPROVED-QUOTE-001 \
  --no-write --show-policy-json --show-checks --show-commands
```

默认只 preview。只有同时满足：

- corpus preflight ready。
- 有 approval reference。
- 指定 `--write-official-sidecars`。
- 不覆盖已有 sidecar，除非显式 `--replace`。

才会写 official sidecars：

```text
transaction-payloads.jsonl
transaction-intent-policy.json
```

实现入口：

- `build_transaction_corpus_sidecar_prepare()`
- `run_prepare_transaction_corpus_sidecars()`

### 13.8 Sidecar review 和 decode

命令：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  transaction-sidecar-review \
  --no-write --show-files --show-commands --show-payload-template-json --show-evidence-contract

python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  decode-transactions --no-write
```

`transaction-sidecar-review` 检查 sidecar 是否 ready for decode。

`decode-transactions` 会：

- 从 sidecar、Burp transaction candidates、probe responses 或 extra input 里找 base64 payload。
- 调用目标 app 的 `@solana/web3.js` 依赖进行本地 decode。
- 解出 account keys、signer/writable、recent blockhash、compiled instructions。
- 尝试解析 SPL Token / Token-2022 transfer。
- 对比 transaction intent policy。
- 输出 reportability review。

它永远不签名、不提交 transaction。

实现入口：

- `build_transaction_intent()`
- `run_decode_transactions()`
- `build_transaction_token_account_metadata_template_package()`
- `run_prepare_transaction_token_account_metadata()`

### 13.9 Token account metadata

当 transaction 里只有 token account，没有直接 mint/owner 信息时，需要 public metadata sidecar。

命令：

```bash
python3 scripts/inferforge.py \
  --artifact-dir .greybox/discover-check \
  prepare-transaction-token-account-metadata \
  --no-write --show-jsonl
```

只有 public、approved、unpolluted、匹配需求的 metadata 才能写 official sidecar：

```text
transaction-token-accounts.jsonl
```

实现入口：

- `build_transaction_token_account_metadata_template_package()`
- `build_transaction_token_account_metadata_preflight()`
- `run_prepare_transaction_token_account_metadata()`

## 14. Rewrite/fixed-upstream response 专线

这条线用于验证 fixed upstream rewrite/proxy 是否造成敏感响应、路径混淆、授权绕过等影响。

命令：

```bash
python3 scripts/inferforge.py rewrite-review --no-write --show-next
python3 scripts/inferforge.py rewrite-validation-checklist --no-write --show-candidates --show-commands
python3 scripts/inferforge.py rewrite-response-review \
  --no-write --show-observations --show-commands \
  --show-observation-contract --show-sidecar-template-json
python3 scripts/inferforge.py response-evidence-readiness --no-write --show-commands
```

它的证据模型：

```text
source rewrite/fixed-upstream context
  -> exactly one approved read-only path
  -> one normalized Burp observation or redacted sidecar
  -> impact indicators
  -> finding gate
  -> adjudication
```

支持 sidecar：

```text
rewrite-response-sidecar.jsonl
```

这个 sidecar 只能存：

- method/path/status/content-type。
- impact indicator。
- sensitive field path。
- short redacted impact summary。
- source boundary。

不能存：

- raw response body。
- raw Burp history。
- cookies。
- bearer tokens。
- API keys。
- private keys。
- seed phrases。
- signatures。

实现入口：

- `build_rewrite_review_run()`
- `rewrite_response_sidecar_template()`
- `rewrite_response_review_observation()`
- `rewrite_response_single_request_approval_packet()`
- `run_rewrite_review()`
- `run_rewrite_validation_checklist()`
- `run_rewrite_response_review()`
- `run_response_evidence_readiness()`

## 15. Deployment、operator evidence、credential/resource/build/secret 专线

这些功能用于处理不是单个 HTTP response 就能证明的影响。

### 15.1 Deployment review

命令：

```bash
python3 scripts/inferforge.py deployment-review --no-write --top 8
```

它只读 allowlisted local config：

- `.env.template`
- Dockerfile
- docker-compose
- vercel config
- README
- Helm chart

如果 `.env` 或 `.env.local` 存在，只记录 key names，不写 value 和 hash。

实现入口：

- `build_deployment_resource_review()`
- `run_deployment_review()`

### 15.2 Operator evidence review

命令：

```bash
python3 scripts/inferforge.py operator-evidence-review \
  --no-write --show-missing --show-template
```

用于 redacted operator-evidence sidecar：

```text
operator-evidence.json
```

覆盖：

- provider quota/billing/rate-limit impact。
- RPC resource control。
- proxy header trust。
- external store。
- monitoring/fallback。
- WebSocket upstream header trust。

实现入口：

- `build_operator_evidence_review()`
- `run_operator_evidence_review()`

### 15.3 Operator impact readiness

命令：

```bash
python3 scripts/inferforge.py operator-impact-readiness --no-write --show-commands
```

它汇总 provider/resource/WebSocket bounty gate 是否有足够 operator evidence。

实现入口：

- `build_operator_impact_readiness()`
- `run_operator_impact_readiness()`

### 15.4 Credential impact checklist

命令：

```bash
python3 scripts/inferforge.py credential-impact-checklist \
  --no-write --show-commands --show-evidence --skip-current-resource-check
```

用于 credentialed upstream cost/quota/billing/availability impact 的证据合约。

实现入口：

- `build_credential_impact_checklist()`
- `run_credential_impact_checklist()`

### 15.5 Build provenance 和 secret exposure

命令：

```bash
python3 scripts/inferforge.py secret-exposure-review --no-write
python3 scripts/inferforge.py build-provenance-readiness --no-write
```

`secret-exposure-review` 看本地 source/config 静态 secret signal。

`build-provenance-readiness` 解析 Dockerfile stage 和 final-stage `COPY --from`，区分：

- final image secret path。
- builder-stage provenance-only risk。
- cache/log/registry provenance risk。

实现入口：

- `build_secret_exposure_review()`
- `run_secret_exposure_review()`
- `build_build_provenance_readiness()`
- `run_build_provenance_readiness()`

## 16. Current target hardening support

这些功能是为了让 `infrafi-web` 作为回归靶场，同时保持工具可迁移。

### 16.1 Quote API hardening

当前工具覆盖：

- content-type 必须是 JSON。
- body 必须只有允许字段。
- route.source / route.destination 必须是 Solana 且 mint pair 在允许范围。
- amountIn 是正整数 string。
- sender/recipient 是 Solana public key。
- recipient 必须等于 sender。
- maxNumQuotes 必须为 1。
- M0 placeholder key 视为未配置。
- upstream error body 不反射。

工具对应：

- `quote_request.body_template`
- `quote_request.policy_fields`
- `quote_intent.directions`
- `quote_provider.diagnostics`
- quote probes。
- transaction corpus pipeline。

### 16.2 Solana RPC HTTP proxy hardening

当前工具覆盖：

- Origin/Referer。
- OPTIONS。
- GET method confusion。
- content-type。
- malformed JSON。
- duplicate JSON key。
- blocked/unknown/wrong-type method。
- batch size。
- mixed batch。
- invalid transaction payload。
- transaction method gate。

相关 artifact：

```text
rpc-method-policy.json
```

### 16.3 Solana RPC WebSocket hardening

当前工具覆盖：

- disallowed Origin handshake。
- binary frame。
- malformed JSON。
- wrong-type method。
- blocked method。
- duplicate key。
- batch size。
- optional low-volume connection limit check。

注意：除了明确的 bounded connection-limit probe，不做 stress、flood 或 DoS。

### 16.4 Orca pool proxy hardening

当前工具覆盖：

- invalid base58。
- too short/too long address。
- encoded traversal。
- extra path segment。
- query injection on invalid address。
- HEAD/POST method confusion。
- single approved/source-known pool baseline。

命令：

```bash
python3 scripts/inferforge.py collect-orca-baseline
```

实现入口：

- `collect_orca_baseline` 相关函数。
- `run_collect_orca_baseline()`

## 17. Manifest、artifact health 和 regression suite

### 17.1 Manifest

命令：

```bash
python3 scripts/inferforge.py manifest
```

它记录：

- SHA256。
- size。
- mtime。
- generated_at。
- JSONL row counts。
- key status summaries。
- missing required artifacts。

实现入口：

- `write_artifact_manifest()`
- `run_manifest()`

输出：

```text
artifact-manifest.json
```

### 17.2 Artifact health

命令：

```bash
python3 scripts/inferforge.py artifact-health --discover-child-runs
```

它检查：

- JSON/JSONL parse health。
- manifest hash/size 是否匹配。
- 新 artifact 是否缺 manifest entry。
- stale derived outputs。
- raw Burp history 是否被不安全持久化。
- MCP action audit 是否泄露 raw argument/result/error。
- probe/warmup/Burp observation 是否泄露 raw bodies 或 raw errors。
- coverage/gate/readiness 状态。

实现入口：

- `build_artifact_health()`
- `run_artifact_health()`

输出：

```text
artifact-health.json
```

### 17.3 Regression suite

命令：

```bash
python3 scripts/inferforge.py regression-suite
```

它用于本工具自身回归：

- 跑静态 self-test。
- 跑 discovery。
- 跑 Burp observe/sync。
- 跑 Orca baseline。
- 跑 default/discovered profile audit。
- 写 root-level rollup。
- 写 regression-suite.json 和 artifact manifest。

资源门禁 warning 时默认阻断，除非显式 `--allow-resource-warning`。

实现入口：

- `run_regression_suite()`

## 18. Self-tests

当前有多组自测：

```bash
python3 scripts/inferforge.py self-test-transactions
python3 scripts/inferforge.py self-test-profile-routing
python3 scripts/inferforge.py self-test-discovery-coverage
python3 scripts/inferforge.py self-test-command-safety
python3 scripts/inferforge.py self-test-review-blockers
python3 scripts/inferforge.py self-test-artifact-health
python3 scripts/inferforge.py self-test-manifest-refresh
python3 scripts/inferforge.py self-test-no-write
python3 scripts/inferforge.py self-test-rewrite-response-review
python3 scripts/inferforge.py self-test-burp-sync-failures
python3 scripts/inferforge.py self-test-bounty-template-safety
python3 scripts/inferforge.py self-test-bounty-prep-package
python3 scripts/inferforge.py self-test-bounty-evidence-intake
python3 scripts/inferforge.py self-test-build-provenance-readiness
```

其中几个关键自测：

```text
self-test-profile-routing:
  验证新 target profile 不会泄漏 infrafi-web 默认 path 或 quote mint。

self-test-command-safety:
  验证 ready/manual/review-gated/external/unsafe/protected-port 分类。

self-test-transactions:
  生成 synthetic Solana versioned transaction，验证 candidate extractor、decoder、intent policy、sidecar review、no-write decode、finding-gate handoff。

self-test-no-write:
  验证 --no-write 不产生不该产生的文件。

self-test-bounty-evidence-intake:
  验证官方证据 intake 的 approval/template blocker。
```

## 19. 当前最重要的操作路径

### 19.1 查看当前最短赏金路径

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  bounty-shortest-path \
  --no-write --show-requests --show-commands --top 8
```

预期当前还是：

```text
blocked-missing-official-evidence
first_missing=transaction-payloads.jsonl
```

这不是坏事，说明门禁没有把源码信号误当成可提交漏洞。

### 19.2 获取 quote capture handoff

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  approved-quote-capture-guide --show-commands
```

### 19.3 检查 operator inputs 目录是否已有可导入 capture

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  approved-quote-exchange-candidates --show-commands --top 6
```

### 19.4 如果 capture 带 cookie/auth，先 redaction

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  redact-approved-quote-capture \
  --input ./approved-quote.har \
  --show-commands
```

确认 preview 后才加：

```bash
--write-redacted-capture
```

### 19.5 从一个 approved exchange 预览 operator input import

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  prepare-approved-quote-operator-inputs \
  --exchange-input ./approved-quote.har \
  --approval-reference APPROVED-QUOTE-001 \
  --no-write --show-preflight --show-commands
```

### 19.6 预检 request/response/intent 三件套

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  transaction-corpus-preflight \
  --request-input .greybox/discover-check/operator-inputs/approved-quote-request.json \
  --payload-input .greybox/discover-check/operator-inputs/approved-quote-response.json \
  --intent-input .greybox/discover-check/operator-inputs/approved-quote-intent.json \
  --no-write --show-policy-json --show-checks --show-commands
```

### 19.7 official sidecar preview/write gate

```bash
python3 scripts/inferforge.py \
  --profile profiles/infrafi-web.json \
  --assessment-mode blackbox \
  --artifact-dir .greybox/discover-check \
  prepare-transaction-corpus-sidecars \
  --request-input .greybox/discover-check/operator-inputs/approved-quote-request.json \
  --payload-input .greybox/discover-check/operator-inputs/approved-quote-response.json \
  --intent-input .greybox/discover-check/operator-inputs/approved-quote-intent.json \
  --approval-reference APPROVED-QUOTE-001 \
  --no-write --show-policy-json --show-checks --show-commands
```

只有经过人工确认后才考虑：

```text
--write-official-sidecars
```

## 20. 新目标 onboarding 流程

### 20.1 有源码的 Next.js 目标

```bash
python3 scripts/inferforge.py \
  --source-root ./some-nextjs-app \
  discover-profile \
  --name some-nextjs-app \
  --display-name "Some Next.js App" \
  --output profiles/some-nextjs-app.json
```

然后：

```bash
python3 scripts/inferforge.py \
  --profile profiles/some-nextjs-app.json \
  profile

python3 scripts/inferforge.py \
  --profile profiles/some-nextjs-app.json \
  plan --no-write

python3 scripts/inferforge.py \
  --profile profiles/some-nextjs-app.json \
  review-candidates --no-write
```

如果有 review-only rewrite/path，先 promote 一个 approved concrete local path，再跑 Burp observation。

### 20.2 纯黑盒 bounty 目标

先用 Burp 内置浏览器走 in-scope 流程，然后：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  burp-sync --replace

python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-profile \
  --output profiles/in-scope-example-blackbox.json

python3 scripts/inferforge.py \
  --profile profiles/in-scope-example-blackbox.json \
  --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  plan --observed-only --no-write
```

如果要从静态资产补线索：

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-map \
  --scope-host in-scope.example \
  --force

python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-profile --force
```

## 21. 代码阅读索引

主脚本很大，阅读时建议按功能跳：

```text
profile/context:
  load_target_profile
  normalize_target_profile
  resolve_run_context
  write_target_profile_artifact

static discovery:
  discover_nextjs_routes
  build_discovered_profile
  merge_discovered_clusters
  build_probe_targets_from_clusters

blackbox history/profile:
  build_blackbox_profile_from_history
  build_blackbox_asset_map
  build_blackbox_profile_from_asset_candidates

resource/safety:
  build_resource_snapshot
  build_resource_budget
  resource_gate_blocks_work
  classify_verification_command
  command_safety_summary

Burp:
  run_burp_observe
  run_burp_sync
  import_burp_history_inputs
  run_import_burp_history

plan/audit:
  Probe
  build_probe_plan
  run_plan
  run_audit

coverage/evidence:
  build_blackbox_coverage
  build_burp_observation_coverage
  build_discovery_coverage
  build_evidence_chain
  build_verification_queue
  build_review_blockers

finding/reportability:
  build_finding_gate
  build_adjudication
  build_findings
  build_hardening_notes

bounty:
  build_bounty_frontier
  build_bounty_validation_gates
  build_bounty_invalidity_review
  build_bounty_readiness_rollup
  build_bounty_evidence_workorders
  build_bounty_lane_priorities
  build_bounty_evidence_authorization
  build_bounty_evidence_intake
  build_bounty_action_queue
  build_bounty_shortest_path
  build_bounty_platform_submission_gate

transaction:
  build_transaction_flow_review
  build_transaction_corpus_preflight
  build_transaction_corpus_sidecar_prepare
  build_transaction_intent
  run_decode_transactions
  run_prepare_transaction_token_account_metadata

quote capture:
  build_approved_quote_capture_guide
  build_redacted_approved_quote_capture
  find_approved_quote_exchange_candidates
  build_approved_quote_operator_input_import
```

## 22. 当前结论

当前工具已经不是简单脚本，主要能力包括：

- profile 驱动的多目标配置。
- Next.js 静态发现。
- Burp MCP/Proxy history 自动同步。
- 黑盒历史和静态资产 profile 生成。
- 低流量 safe probe 计划和 audit。
- source peek 和 endpoint resolver。
- coverage/evidence chain/report 生成。
- finding gate/adjudication/reportability 控制。
- command safety 和 resource gate。
- 赏金模式下的 lead、oracle、workorder、evidence intake、action queue、shortest path、platform submission gate。
- Solana quote transaction evidence pipeline。
- rewrite/fixed-upstream response evidence pipeline。
- credential/operator/resource/build provenance evidence pipeline。
- artifact manifest/health/regression/self-test。

当前没有可提交漏洞，并不能证明目标没有漏洞。更准确地说，当前最高价值路径已经有 source-positive signal，但是还缺一份真实授权、最小化、已脱敏、可绑定的 `/api/quote` request/response/intent evidence package。没有这个包，工具会继续正确地卡在 `blocked-missing-official-evidence`，不会把假设升级成 Medium/High/Critical 报告。
