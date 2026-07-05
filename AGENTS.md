# Agent Runtime Guardrails

This repository is used from an environment where port `2455` is the AI API
load balancer path. Treat the process/container behind `2455` as critical
control-plane infrastructure, not as a test target.

Hard rule:

- Do not kill, stop, restart, signal, or otherwise manage the process,
  container, service, or port behind `2455`.
- Do not use `2455` as a memory-reclaim candidate.
- Do not add `2455` to watch-port lists, health checks, readiness checks,
  resource checks, or active probes.
- If `2455` appears unhealthy, report it to the user and wait for explicit
  authorization before taking any action.

This rule was added after an accidental `kill -TERM` interrupted the user's
AI/API load balancer on 2026-07-05.
