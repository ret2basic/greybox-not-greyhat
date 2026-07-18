# Agent Runtime Guardrails

This repository is used from an environment where port `2455` is the AI API
load balancer path. Treat the process/container behind `2455` as critical
control-plane infrastructure, not as a test target.

Hard rule:

- Do not kill, stop, restart, signal, or otherwise manage the process,
  container, service, or port behind `2455`.
- Do not manage the AI API load balancer by process name, container name,
  service name, supervisor unit, or any other identifier, even if the port is
  not mentioned directly.
- Do not inspect, probe, curl, `ss`, `lsof`, `pgrep`, health-check, or
  supervisor-query `2455` or the AI API load balancer as an operational target.
- Do not use `2455` as a memory-reclaim candidate.
- Do not add `2455` to watch-port lists, health checks, readiness checks,
  resource checks, or active probes.
- Do not run commands, tests, examples, or automation that pass `2455` as an
  argument, even if the code is expected to block it safely.
- If `2455` appears unhealthy, report it to the user and wait for explicit
  authorization before taking any action.

This rule was added after an accidental `kill -TERM` interrupted the user's
AI/API load balancer on 2026-07-05.

## InferForge v2 Product Invariants

InferForge v2 is a source-required white-box Web security evidence engine.
Changes in this repository must preserve these invariants:

- Do not add a source-free, remote-target, bounty-discovery, or black-box mode.
- Do not make Burp Suite, a browser, a proxy, MCP, or a running target a core
  dependency.
- Scanner commands must remain offline and must not execute target code,
  package scripts, services, containers, or active probes.
- Scanner alerts are candidates, not findings. Confirmation requires source
  evidence, independent verification, explicit Impact and Likelihood, and
  freshness checks.
- Missing static signals are coverage gaps, not proof that a control is absent.
- Preserve artifact integrity, source-root path confinement, secret redaction,
  and evidence-digest invalidation.
- Synthetic vulnerable fixtures must never be started or exposed as services.
