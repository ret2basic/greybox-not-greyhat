# InferForge v1 → v2 迁移

## 不兼容结论

v2 是纯白盒重建，不是 v1 的新增 mode。不存在兼容开关，也不会在缺少源码时回退。

以下产品能力已删除：

- greybox/blackbox assessment mode；
- 远程 target 和 host scope；
- Burp MCP discovery、history import/sync、observation 和 request replay；
- blackbox asset/page/bundle mapping；
- bounty program、Immunefi catalog、ROI ranking 和 watcher；
- takeover/DNS/远程 runtime host probe；
- 目标 profile 和内置 InfraFi fixture；
- 主动 HTTP/WebSocket audit probe；
- 资源监控、进程回收和 watch-port 逻辑；
- 针对单一 Web3 应用的 quote/RPC/transaction 专用流水线；
- 研究 handoff 和提交模板。

这些命令没有 v2 等价命令，因为它们属于另一个黑盒赏金工具的职责。

## 新的命令面

| v2 命令 | 作用 |
| --- | --- |
| init | 创建 source-required 配置 |
| doctor | 检查源码、预算、artifact 和可选 SAST 工具 |
| scan | 构建 inventory、entrypoint、topology、signals、candidate 和 plan |
| context | 为一个 candidate/task/route 生成有界源码包 |
| review | 用证据关闭或重开 coverage task |
| triage | 管理 candidate 生命周期 |
| report | 只渲染 confirmed finding |
| status | 查看 scan、triage 和 review 状态 |
| verify-artifacts | 验证派生 artifact hash |
| rules | 查看原生规则 |

## 配置迁移

v2 配置根必须使用 schema_version 2。旧键 target、assessment_mode、blackbox、
burp、burp_mcp、scope_hosts 和 bounty_program 会直接报错。

不要把旧 profile 自动转换。应在目标源码根运行 init，然后只迁移：

- 真正的 generated/vendor exclude；
- 单文件和全仓预算；
- 需要禁用或调级的白盒规则；
- 业务 trust boundary。

## Artifact 迁移

旧 .greybox 内容不会被 v2 读取。它可能包含历史研究和敏感证据，保留或清理由用户
自行决定。v2 默认写 .inferforge。

不要把旧 finding/lead 状态直接复制进 candidates.json。重新扫描源码，再用 triage
引用当前源码位置和当前回归测试。这样可以避免旧版本、旧 scope 和旧部署假设污染。

## 历史恢复

重构前公开安全工作树保存在 commit 6eff034。它只用于审计历史或提取独立工具，不应
恢复到 v2 main。

如果未来需要复用旧黑盒能力，正确方式是从历史 commit 提取到另一个仓库，而不是在
v2 中重新加入 mode flag。
