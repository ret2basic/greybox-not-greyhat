# InferForge v2 source-first roadmap

## Completed in v2

- Replace the 184,891-line Burp-first monolith with a Python package and thin CLI entry point.
- Require a local source root and reject legacy remote/black-box configuration.
- Remove Burp MCP, remote target, bounty catalog, asset mapping, active probing, target profiles, and
  target-specific workflow code.
- Add bounded polyglot inventory and explicit incomplete-coverage semantics.
- Add framework entrypoint adapters for common JavaScript, Python, JVM, PHP, Ruby, Go, and Rust Web
  stacks, including WebSocket, GraphQL, SvelteKit, NestJS, and Next.js Server Actions.
- Add local symbol/import/call topology and route-to-file reachability.
- Add native source/sink/control analysis and unresolved-sink call-path tasks.
- Merge Semgrep, CodeQL, and compatible tools through local-only SARIF.
- Add evidence graph, route coverage ledger, review task lifecycle, candidate lifecycle, Impact /
  Likelihood severity derivation, and confirmed-only reporting.
- Add artifact hashing, source-context redaction, prompt-injection warning, offline tests, fixture scan,
  packaging, JSON schema, CI, architecture, workflow, migration, and security documentation.

## Next adapters

- Framework-aware middleware composition for NestJS, Django, Spring Security, Rails, and Laravel.
- Language-parser plugins using tree-sitter when available, while keeping the no-dependency fallback.
- First-class CodeQL database/result metadata and Semgrep rule-pack provenance.
- Test-framework adapters that generate draft regression-test skeletons without executing them.
- Coverage import from unit/integration tests and endpoint-to-test mapping.
- Incremental scan cache keyed by file digest and rule-catalog version.
- Stable custom organization rule packs with schema validation and signed provenance.
- Optional local UI for the evidence graph and route closure; no remote scanning controls.

## Non-goals

- Reintroducing source-free operation.
- Acting as a bounty target finder.
- Managing Burp, browsers, proxies, services, containers, or control-plane processes.
- Automatically exploiting production deployments.
- Treating a scanner alert or graph edge as proof of a vulnerability.
