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
