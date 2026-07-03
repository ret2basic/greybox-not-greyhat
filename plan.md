# Burp-First Greybox Agent Development Plan

## 0. Goal

Build a black-box-first greybox audit tool for large Web2/Web3 applications.

The first target is `infrafi-web`, but the software must be designed for future targets with similar architecture:

- Browser-heavy frontend.
- Burp Suite as the main black-box testing workspace.
- HTTP, WebSocket, API, and wallet-related traffic visible through Burp.
- Local source code available for targeted confirmation.
- Codex as the orchestration agent.
- MCP as the bridge between Codex and Burp.

The intended audit ratio is:

```text
70% black-box testing through Burp Suite
30% targeted white-box source reading when black-box evidence needs explanation
```

The tool should not become a pure source-code scanner. Source access is used only after black-box observations produce a concrete question.

## 1. Operating Model

The desired workflow is:

```text
Burp traffic / Repeater / WebSocket history
    -> Codex reads observations through MCP
    -> Codex clusters attack surfaces
    -> Codex proposes focused black-box tests
    -> Codex sends or prepares requests through Burp
    -> suspicious behavior is recorded
    -> Codex performs a narrow source peek only when needed
    -> Codex combines black-box evidence and source evidence
    -> verified findings or hardening notes are produced
```

The core loop is:

```text
Observe -> Suspect -> Probe -> Source Peek if needed -> Verify -> Report
```

## 2. Important Scope Decisions

Use Burp Suite Community Edition for the initial prototype.

Community Edition constraints must shape the first version:

- Do not depend on Burp Scanner.
- Do not depend on Burp Collaborator payload generation.
- Do not depend on Burp AI credits or Burp Professional-only AI features.
- Use Burp Proxy, HTTP history, WebSocket history, Repeater-style request sending, and extension/MCP access as the primary interface.
- If an MCP tool is Professional-only, detect the failure and continue without that capability.

The first version should prefer assisted manual testing over blind automation:

- No uncontrolled fuzzing.
- No broad active testing outside the configured target scope.
- No destructive actions.
- No automatic report finding unless the evidence chain is complete.

## 3. Burp Suite MCP Setup

### 3.1 Install Burp Suite Community

1. Download and install Burp Suite Community Edition.
2. Launch Burp.
3. Create a temporary project.
4. Confirm the proxy listener is active, normally:

```text
127.0.0.1:8080
```

5. Configure the browser or Playwright to use Burp as the proxy.
6. Install Burp's CA certificate in the browser profile used for testing HTTPS targets.

### 3.2 Install the Official MCP Server Extension

Use PortSwigger's official BApp Store extension:

```text
MCP Server
```

Install path:

```text
Burp -> Extensions -> BApp Store -> MCP Server -> Install
```

If BApp Store installation is unavailable:

1. Download the BApp from PortSwigger's BApp Store page.
2. Or build from the official source repository:

```bash
git clone https://github.com/PortSwigger/mcp-server.git
cd mcp-server
./gradlew embedProxyJar
```

3. Load the generated Java extension JAR in Burp:

```text
Burp -> Extensions -> Installed -> Add -> Extension type: Java -> select JAR
```

### 3.3 Configure the MCP Extension in Burp

After installation, open:

```text
Burp -> MCP tab
```

Recommended initial settings:

```text
Enabled: true
Host: 127.0.0.1
Port: 9876
Config editing tools: disabled
Auto-approve targets: only explicit in-scope hosts
History access: enabled only for current project/testing scope
```

Keep the MCP server bound to localhost. Do not expose it on `0.0.0.0`.

The expected MCP endpoint is usually one of:

```text
http://127.0.0.1:9876
http://127.0.0.1:9876/sse
```

### 3.4 Connect Codex to Burp MCP

Codex currently supports MCP server registration through:

```bash
codex mcp add
```

First try direct HTTP registration:

```bash
codex mcp add burp --url http://127.0.0.1:9876
```

If discovery fails, try the SSE path:

```bash
codex mcp add burp --url http://127.0.0.1:9876/sse
```

Verify registration:

```bash
codex mcp list
codex mcp get burp
```

If Codex cannot speak directly to Burp's SSE MCP endpoint, use the stdio proxy packaged by the Burp MCP extension:

```bash
codex mcp add burp -- /path/to/java -jar /path/to/mcp-proxy-all.jar --sse-url http://127.0.0.1:9876
```

The exact Java path and proxy JAR path should be copied from the MCP extension's installer/export UI or the built extension output.

### 3.5 Smoke Test the MCP Connection

With Burp running and the MCP extension enabled:

1. Visit the target through Burp's proxy.
2. Confirm the request appears in Burp Proxy HTTP history.
3. Ask Codex to list recent Burp HTTP history through the MCP server.
4. Ask Codex to retrieve one request/response by identifier.
5. Ask Codex to create or prepare a Repeater-style request if the MCP tool exposes that capability.
6. Confirm that all actions stay within the configured scope.

Minimum success criteria:

```text
Codex can see Burp HTTP history.
Codex can inspect a selected request and response.
Codex can send or prepare a controlled request through Burp MCP.
Codex can record the result in local artifacts.
```

## 4. First Prototype Architecture

Name the software later. For planning, call it:

```text
greybox-burp-agent
```

The initial architecture:

```text
greybox-burp-agent/
├── burp_mcp/
│   ├── client.py
│   ├── capabilities.py
│   └── models.py
├── observations/
│   ├── collector.py
│   ├── endpoint_cluster.py
│   └── traffic_store.py
├── planner/
│   ├── blackbox_plan.py
│   ├── probe_queue.py
│   └── prompt_templates.py
├── probes/
│   ├── http_probe.py
│   ├── websocket_probe.py
│   ├── cors_probe.py
│   ├── auth_probe.py
│   └── input_mutator.py
├── source_peek/
│   ├── resolver.py
│   ├── nextjs_resolver.py
│   ├── code_context.py
│   └── source_notes.py
├── web3/
│   ├── wallet_flow_detector.py
│   ├── solana_tx_decoder.py
│   └── intent_checker.py
├── verifier/
│   ├── evidence_chain.py
│   ├── finding_gate.py
│   └── adjudicator.py
├── reports/
│   ├── markdown.py
│   └── json_report.py
└── cli.py
```

This layout can be simplified during implementation, but the boundaries should remain.

## 5. Artifact Contract

Store all run artifacts under:

```text
.greybox/
```

Initial files:

```text
.greybox/
├── config.json
├── burp-capabilities.json
├── traffic-index.json
├── endpoint-clusters.json
├── observations.jsonl
├── probe-plan.json
├── probe-results.jsonl
├── suspicions.json
├── source-peek-requests.json
├── source-peek-results.json
├── verification-queue.json
├── findings.json
└── report.md
```

Each suspicious item should have this shape:

```json
{
  "id": "SUSP-001",
  "status": "observation | suspicion | needs-source | probing | invalid | verified | blocked",
  "entrypoint": "POST /api/example",
  "blackbox_evidence": [],
  "controlled_inputs": [],
  "hypothesis": "",
  "next_probe": "",
  "source_questions": [],
  "source_refs": [],
  "impact_notes": "",
  "final_classification": ""
}
```

The status model prevents the tool from mixing raw observations with verified findings.

## 6. Development Phases

### Phase 0: Manual Burp MCP Bring-Up

Goal: prove that Codex can operate Burp Community through MCP.

Tasks:

1. Install Burp Community.
2. Install the official MCP Server extension.
3. Enable MCP on `127.0.0.1:9876`.
4. Register the MCP server with Codex.
5. Proxy browser traffic through Burp.
6. Confirm Codex can read recent HTTP history.
7. Confirm Codex can inspect one request/response.
8. Record exact setup steps and any Community limitations.

Deliverables:

```text
.greybox/burp-capabilities.json
.greybox/setup-notes.md
```

Acceptance criteria:

```text
Burp MCP is usable from Codex without Burp Professional.
The tool knows which MCP capabilities are available and which are missing.
```

### Phase 1: Traffic Observation Collector

Goal: collect and normalize Burp black-box observations.

Tasks:

1. Read Burp HTTP history through MCP.
2. Read Burp WebSocket history if exposed by the MCP extension.
3. Normalize request/response records.
4. Deduplicate repeated static assets and polling traffic.
5. Cluster endpoints by path, method, content type, and parameter shape.
6. Identify likely API endpoints.
7. Identify likely sensitive endpoints.
8. Write `traffic-index.json` and `endpoint-clusters.json`.

Important filtering rules:

```text
Ignore obvious static assets unless they expose secrets or source maps.
Deprioritize images, fonts, CSS, and animation files.
Preserve JavaScript bundles for endpoint extraction.
Preserve API, JSON, WebSocket, and wallet-related traffic.
```

Acceptance criteria:

```text
Given a Burp session for infrafi-web, the tool can list API-like surfaces such as /api/quote and /api/rpc.
```

### Phase 2: Black-Box Test Planner

Goal: generate practical test plans from observed traffic.

Tasks:

1. For each endpoint cluster, infer input shape.
2. Classify parameters by type:
   - string
   - number
   - boolean
   - enum
   - URL
   - path
   - wallet address
   - token/mint
   - JSON-RPC method
   - base64 transaction
3. Select traditional black-box checks:
   - method confusion
   - CORS and Origin/Referer behavior
   - malformed JSON
   - missing fields
   - wrong types
   - boundary values
   - excessive body size
   - duplicate keys
   - unknown fields
   - auth/session variation
   - rate limit checks
4. Produce `probe-plan.json`.

Acceptance criteria:

```text
The planner produces concrete Repeater/probe actions, not vague advice.
```

### Phase 3: Controlled Probe Runner

Goal: execute safe, scoped black-box probes through Burp MCP.

Tasks:

1. Implement request replay.
2. Implement request mutation.
3. Respect target scope and approval settings.
4. Record request/response pairs.
5. Compare mutated responses against baseline.
6. Detect interesting deltas:
   - status code change
   - auth boundary change
   - validation bypass
   - reflected input
   - upstream error leakage
   - timeout or resource exhaustion signal
   - response body shape change
7. Write `probe-results.jsonl`.

Safety controls:

```text
Default to GET/OPTIONS/low-risk POST mutations.
Do not submit destructive actions automatically.
Require manual approval for transaction submission, account mutation, or high-volume tests.
Keep request rate low.
```

Acceptance criteria:

```text
The tool can replay and mutate a selected /api request and explain what changed.
```

### Phase 4: Suspicion Engine

Goal: convert observations and probe results into source-peek questions.

Tasks:

1. Group probe deltas by endpoint.
2. Generate a concise hypothesis per suspicious behavior.
3. Decide whether more black-box probing is enough or source reading is needed.
4. Create `suspicions.json`.
5. Create `source-peek-requests.json` only for items that need code confirmation.

Example source-peek request:

```json
{
  "suspicion_id": "SUSP-quote-001",
  "entrypoint": "POST /api/quote",
  "blackbox_observation": "Unexpected chain value is forwarded and changes upstream error behavior.",
  "questions": [
    "Does the server restrict source and destination chains?",
    "Does the server validate Solana addresses?",
    "Is the request body forwarded unchanged to the upstream quote API?"
  ],
  "max_files": 5,
  "max_call_depth": 2
}
```

Acceptance criteria:

```text
The tool reads source only after it can name a concrete black-box observation and question.
```

### Phase 5: Source Peek Resolver

Goal: answer narrow code questions without turning the workflow into full white-box audit.

Tasks:

1. Resolve URLs to likely source files.
2. Support Next.js App Router:
   - `src/app/**/route.ts`
   - dynamic path segments
   - `next.config.ts` rewrites
3. Support custom Node server files:
   - `server.js`
   - upgrade handlers
   - proxy handlers
4. Support frontend caller lookup:
   - `fetch(...)`
   - `axios(...)`
   - wallet transaction calls
5. Read only the files needed to answer the suspicion's questions.
6. Write `source-peek-results.json`.

For `infrafi-web`, initial resolvers should handle:

```text
/api/quote -> src/app/api/quote/route.ts, src/lib/m0.ts, src/hooks/useSolanaSwap.ts
/api/rpc -> src/app/api/rpc/_shared.ts
/api/rpc/solana/[cluster] -> src/app/api/rpc/solana/[cluster]/route.ts and server.js
/api/orca/pools/[address] -> src/app/api/orca/pools/[address]/route.ts
/api/infrafi/:path* -> next.config.ts rewrite
```

Acceptance criteria:

```text
For a Burp-observed endpoint, the resolver returns the minimal relevant source context.
```

### Phase 6: Web3 Runtime Helpers

Goal: cover the Web3 behavior that Burp sees only as HTTP or browser traffic.

Tasks:

1. Detect wallet-related browser flows from traffic and frontend artifacts.
2. Capture or import transaction payloads observed during testing.
3. Implement a minimal Solana transaction decoder:
   - legacy transaction
   - versioned transaction
   - account keys
   - signer and writable flags
   - program IDs
   - SPL token transfers where possible
   - unknown instruction preservation
4. Compare decoded transaction intent against the black-box UI action:
   - input asset
   - output asset
   - amount
   - sender
   - recipient
   - unexpected writable accounts
   - unexpected program IDs
5. Do not submit wallet transactions automatically.

Acceptance criteria:

```text
When a quote API returns executable transaction payloads, the tool can decode or flag what it cannot prove.
```

### Phase 7: Verifier and Finding Gate

Goal: prevent raw AI guesses from becoming findings.

Every finding must pass:

```text
Black-box reproduction exists.
The affected endpoint or flow is in scope.
The attacker model is explicit.
The controlled input is explicit.
The impact is explicit.
The behavior is not only a frontend artifact.
The behavior is not a known Community/prototype limitation.
Relevant source confirmation exists when needed.
Counter-evidence has been checked.
```

Classifications:

```text
valid-finding
invalid
acknowledged-design
hardening-note
blocked
manual-review
```

Only `valid-finding` entries go into `findings.json`.

Acceptance criteria:

```text
The report separates verified vulnerabilities from suspicions and hardening notes.
```

### Phase 8: Reporting

Goal: produce audit output that a human can review and reproduce.

Report sections:

```text
Scope and setup
Burp MCP configuration used
Observed attack surface
Endpoints tested
Probe summary
Source peeks performed
Verified findings
Hardening notes
Blocked or manual-review items
Appendix: key request/response evidence
```

Every verified finding should include:

```text
Title
Severity
Affected endpoint or flow
Attacker
Preconditions
Reproduction steps
Request/response evidence
Source evidence, if used
Impact
Fix recommendation
```

Acceptance criteria:

```text
The report is usable without re-running the tool, and every claim links back to concrete evidence.
```

## 7. First Target: infrafi-web

Use `infrafi-web` to validate the workflow.

Initial Burp-visible surfaces to prioritize:

```text
GET /health
POST /api/quote
POST /api/rpc
POST /api/rpc/solana/mainnet
POST /api/rpc/solana/devnet
GET /api/orca/pools/{address}
/api/infrafi/:path* rewrite behavior
WebSocket upgrade /api/rpc/solana/{cluster}
```

Initial black-box questions:

```text
Can unauthenticated users access server-side proxy routes?
Are CORS and Origin/Referer checks consistent?
Are JSON-RPC method allowlists enforced for single and batch requests?
Can blocked Solana RPC methods be reached through mutation?
Are request size and batch size limits enforced?
Can server-side proxy routes be abused as open proxies?
Does /api/quote validate chain, mint, sender, recipient, amount, and maxNumQuotes?
Does the app accept third-party executable transaction payloads without local intent checks?
Does WebSocket proxy enforce method, message size, origin, and connection limits?
```

Initial source-peek triggers:

```text
Unexpected status or upstream error from /api/quote.
Inconsistent Origin/Referer behavior on RPC proxy.
Any JSON-RPC method allowlist bypass signal.
Any transaction payload that cannot be tied to UI intent.
Any rewrite/proxy behavior whose upstream target is unclear from black-box traffic.
```

## 8. CLI Design

Initial commands:

```bash
greybox init --target ./infrafi-web --burp-mcp burp
greybox capabilities
greybox collect --from-burp
greybox plan
greybox probe --safe
greybox suspicions
greybox peek
greybox verify
greybox report
```

Later convenience command:

```bash
greybox audit --target ./infrafi-web --burp-mcp burp --safe
```

## 9. MVP Acceptance Criteria

The MVP is complete when:

```text
Burp Community can be connected to Codex through MCP.
The tool can collect HTTP history from Burp.
The tool can cluster endpoints and identify API-like surfaces.
The tool can generate a safe probe plan for observed requests.
The tool can run or prepare selected probes through Burp.
The tool can detect response deltas.
The tool can decide when a source peek is needed.
The tool can map a Next.js route to the relevant source file.
The tool can produce a report separating findings, suspicions, and notes.
```

## 10. Non-Goals for the First Version

Do not implement these in the first version:

```text
Full white-box source audit.
Full active scanner replacement.
High-speed fuzzing.
Automatic exploit execution.
Automatic wallet transaction submission.
Burp Collaborator dependency.
Burp Scanner dependency.
Burp AI dependency.
Multi-user web dashboard.
Cloud synchronization.
Large plugin ecosystem.
```

## 11. Security and Safety Rules

The tool itself has sensitive access. Treat it as audit infrastructure.

Rules:

```text
Bind Burp MCP to 127.0.0.1 only.
Keep Burp MCP target approval enabled.
Do not expose the MCP endpoint to a LAN or remote host.
Store artifacts locally by default.
Redact cookies, bearer tokens, API keys, and wallet secrets in reports.
Never send real customer traffic to external AI providers without explicit approval.
Require manual approval for destructive or state-changing probes.
Require manual approval before any wallet signing or chain transaction submission.
Keep a complete audit log of MCP actions.
```

## 12. References Checked

PortSwigger official MCP Server BApp:

```text
https://portswigger.net/bappstore/9952290f04ed4f628e624d0aa9dccebc
```

PortSwigger official MCP Server source:

```text
https://github.com/PortSwigger/mcp-server
```

Local Codex MCP command discovery:

```bash
codex mcp --help
codex mcp add --help
codex mcp list
```
