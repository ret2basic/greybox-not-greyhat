# greybox-not-greyhat

Local Burp-first greybox testing tool workspace. `infrafi-web` is the default
regression target used to develop and verify the reusable workflow.

## Current Target

`infrafi-web` is a Next.js app under:

```bash
./infrafi-web
```

The checked-in app expects Node 22+. On this machine the system `node` is Node
18, so use the cached Node 22 binary that is already present:

```bash
cd infrafi-web
PORT=3100 HOSTNAME=127.0.0.1 \
  /home/ret2basic/.npm/_npx/52027bd8fc0022aa/node_modules/node/bin/node server.js
```

Health check:

```bash
curl http://127.0.0.1:3100/health
```

## InferForge Local Runner

`scripts/inferforge.py` is the local repeatable runner for this prototype. It
does safe HTTP/WebSocket probes, source-peek mapping, endpoint clustering, and
report generation without extra Python dependencies.

Target-specific routing, source references, Burp observation requests, enabled
strategy sets, and cluster metadata are described by a target profile. The
default profile is:

```text
profiles/infrafi-web.json
```

Materialize the effective profile and endpoint clusters without probing:

```bash
python3 scripts/inferforge.py profile
```

For a new Next.js target, start with static route discovery. This does not send
HTTP requests; it scans App Router handlers
`src/app/**/route.{ts,tsx,js,jsx}` and `app/**/route.{ts,tsx,js,jsx}`,
Pages Router API files
`src/pages/api/**/*.{ts,tsx,js,jsx}` and `pages/api/**/*.{ts,tsx,js,jsx}`,
root or `src/` `middleware.*` / `proxy.*` files, statically readable
`next.config.*` rewrites, redirects, headers, simple custom-server WebSocket
upgrade handlers, and files with Next.js `'use server'` Server Action
directives. Rewrite phases such as `beforeFiles`, `afterFiles`, and `fallback`,
plus static `has` / `missing` conditions, are preserved as source context.
Static `basePath`, `trailingSlash`, and `i18n.locales` configuration is also
preserved and applied to generated runtime paths, while the original framework
path is kept as `source_path` for source attribution. Server Actions are source
context only; they do not create clusters or active probes. During `audit`,
discovered Server Action files are also copied into manual-review evidence gaps
and verification queue items so mutation boundaries can be reviewed from source
without invoking actions or submitting forms. Discovery then writes a
route/rewrite/middleware/server-action/route-policy/server-entrypoint inventory
plus a starter profile for review:

```bash
python3 scripts/inferforge.py --source-root ./some-nextjs-app discover-profile
```

To promote the generated starter profile into `profiles/`, pass an explicit
output path:

```bash
python3 scripts/inferforge.py --source-root ./some-nextjs-app discover-profile \
  --name some-nextjs-app \
  --display-name "Some Next.js App" \
  --output profiles/some-nextjs-app.json
```

Use `--profile`, `--target`, and `--source-root` to onboard another similar
application while keeping the same tool pipeline:

```bash
python3 scripts/inferforge.py --profile profiles/infrafi-web.json profile
python3 scripts/inferforge.py --profile profiles/infrafi-web.json audit --include-external
```

The profile's `strategy_sets` list controls which built-in bounded strategies
are active for the run. The current registry includes:

```text
nextjs-api-routes
solana-json-rpc-proxy
quote-transaction-decoder
fixed-upstream-proxy
```

`profile`, `plan`, and `audit` write `.greybox/strategy-registry.json`, which
records the enabled strategies, their cluster ownership, and the safety boundary
for each strategy set. They also write `.greybox/profile-validation.json`, which
fails on unknown strategy sets, duplicate cluster IDs, missing required cluster
fields, or a profile that filters down to no effective clusters.

Profiles separate endpoint discovery from concrete probe paths:

- `clusters` describe the attack surface and how traffic/source evidence should
  be classified.
- `probe_targets` describe the bounded HTTP paths that built-in strategies are
  allowed to request, such as the health endpoint, quote endpoint, RPC cluster
  path, RPC root path, and invalid Orca address paths.
- `websocket_observation: null` explicitly disables WS observation for targets
  that do not expose a WebSocket route.
- `review_observation_candidates` contains generated review-only templates for
  surfaces that are known from source but not safe to probe blindly. These
  candidates are copied into evidence gaps and the verification queue, but they
  are not executed by `burp-sync --observe` until a concrete approved path is
  promoted into `burp_observation_plan`.
- `review-candidates` lists these inert templates and writes
  `.greybox/review-observation-candidates.json`; use `--no-write` to print an
  approval-focused summary without writing artifacts. The dry-run output shows
  path templates, source refs, fixed upstreams, approval requirements,
  promotion placeholders, command safety totals, and labeled generated command
  templates so the human review step can approve one concrete local read-only
  path without opening the JSON artifact. After review, use
  `promote-observation-candidate` to write a separate reviewed profile.
  Promotion is a profile edit only; it does not send HTTP traffic.
- Generic `nextjs-api-routes` clusters with concrete probe paths receive only
  low-risk HEAD, OPTIONS preflight, and GET method-confusion or availability
  probes. Dynamic routes with unresolved `{param}` segments are skipped until
  the profile supplies a concrete `probe_targets.<cluster_id>.path`.
- Unexpected generic route probe results are attributed back to their profile
  cluster and source refs, then flow through the finding gate as hardening
  notes instead of remaining only as raw probe failures.
- Statically readable `next.config.*` rewrites are included as
  `rewrite-proxy` clusters with source refs, path-prefix matching, and fixed
  upstream hints. Discovery records these for classification and source context;
  active probes for arbitrary rewrite upstreams still require profile review.
  Generated profiles add review-only Burp observation candidates for these
  rewrites so the required approval and promotion step is explicit.
- Custom server WebSocket upgrade handlers with static path-prefix constants are
  included as WebSocket clusters with source refs, path-prefix matching, and
  upgrade-handler line refs. This covers common `server.on('upgrade')` +
  `WebSocketServer({ noServer: true })` setups without executing server code.

This keeps `infrafi-web` as a regression target instead of hardcoding its
`/api/quote`, `/api/rpc/solana/devnet`, `/api/orca/pools/{address}`, and
`/api/infrafi/:path*` rewrite into the reusable tool behavior.

Review-only candidates can be promoted without hand-editing JSON:

```bash
python3 scripts/inferforge.py --profile .greybox/discovered-profile.json review-candidates --no-write

python3 scripts/inferforge.py \
  --profile .greybox/discovered-profile.json \
  promote-observation-candidate \
  --candidate-id review_observe_route_api_infrafi_path_approved_path \
  --path /api/infrafi/status \
  --no-write

python3 scripts/inferforge.py \
  --profile .greybox/discovered-profile.json \
  promote-observation-candidate \
  --candidate-id review_observe_route_api_infrafi_path_approved_path \
  --path /api/infrafi/status \
  --output .greybox/reviewed-profile.json
```

The `--path` value must be a concrete local path that matches the candidate
template; replace the example with the actual approved read-only path. Full
URLs, placeholders, braces, angle brackets, whitespace, and non-matching
prefixes are rejected. Use `--no-write` to validate the path, preview the
promoted observation, and print the follow-up `burp-sync --observe` and `audit`
commands before writing profile artifacts. Use the reviewed profile with
`burp-sync --observe` only after the path has been approved.

When a rewrite observation gap is present, `verification-queue` also emits the
same promotion sequence as manual-review command templates:

1. preview the promotion with `promote-observation-candidate --no-write`;
2. promote the approved path into `.greybox/reviewed-profile.json`;
3. run `burp-sync --observe` with that reviewed profile;
4. rerun `audit` with the reviewed profile.

The placeholder `REPLACE_WITH_APPROVED_CONCRETE_LOCAL_PATH` in the queue is
deliberately rejected by the promote command until a human replaces it with one
reviewed local path.

Active `burp_observation_plan` entries are validated as executable traffic.
They must use a concrete local path beginning with `/`; full URLs,
`REPLACE_WITH_*` placeholders, `{param}` templates, `<placeholder>` text, and
whitespace are profile-validation errors. Keep unresolved paths in
`review_observation_candidates` until one reviewed concrete path is promoted.

When a separate profile file omits target-specific fields such as `clusters`,
`probe_targets`, `burp_observation_plan`, or `websocket_observation`, InferForge
uses neutral empty defaults and emits profile-validation warnings. It does not
borrow `infrafi-web` clusters or probe paths for another target. Use the static
routing self-test to guard this invariant:

```bash
python3 scripts/inferforge.py self-test-profile-routing
```

The self-test builds a synthetic profile with non-`infrafi-web` paths, including
a generic API route, generates probe/warmup/Burp observation plans, and fails if
default regression-target paths leak into those plans. It writes
`.greybox/profile-routing-selftest.json` and does not send HTTP requests or call
Burp.

Use the discovery coverage self-test to guard static surface classification:

```bash
python3 scripts/inferforge.py self-test-discovery-coverage
```

It builds a synthetic route inventory and profile that exercise Burp-history
coverage, probe-result coverage, active observation coverage, profile-cluster
coverage, review-gated rewrites, source-only contexts, and uncovered routes. It
writes `.greybox/discovery-coverage-selftest.json` and does not send HTTP
requests or call Burp.

Run the current greybox workflow:

```bash
python3 scripts/inferforge.py audit --include-external
```

`audit` automatically warms the local Next.js dev routes before the measured
probe run and writes the preflight results to `.greybox/warmup-results.json`.
The warm-up covers `/health`, quote validation, Solana RPC policy handling, and
Orca route/not-found handling. Measured HTTP probes keep the first attempt in
their result metadata and retry once only for local transport timeouts or the
known Next dev manifest-load transient `500`; warm-up checks are not counted as
findings.

On a clean artifact directory, `audit` writes empty or not-run placeholders for
Burp history, Burp observation, and quote collection artifacts so the report
manifest remains complete. Missing Burp browser-flow evidence is still recorded
as an evidence gap and coverage open item; run `burp-sync --observe` when you
want Burp Proxy history attached to the same artifact directory.

Use `--include-external` only when a bounded set of low-risk M0 quote validation
probes is acceptable. Omit it for a purely local run; the local run still covers
missing fields, malformed JSON, wrong primitive types, RPC controls, WS controls,
and Orca path validation. Use `plan --no-write` to preview endpoint selection,
probe ranking counts, the top selected probes with rank reasons, and WebSocket
enablement without writing probe-plan, ranking, strategy, or manifest artifacts.

Useful checks:

```bash
python3 scripts/inferforge.py collect
python3 scripts/inferforge.py profile
python3 scripts/inferforge.py discover-profile
python3 scripts/inferforge.py burp-sync --observe --ws-upgrade --replace
python3 scripts/inferforge.py burp-observe --ws-upgrade
python3 scripts/inferforge.py import-burp-history --input .greybox/burp-mcp-history.txt
python3 scripts/inferforge.py plan --include-external
python3 scripts/inferforge.py plan --include-external --no-write
python3 scripts/inferforge.py plan --include-external --max-probes 12
python3 scripts/inferforge.py capabilities
python3 scripts/inferforge.py capabilities --no-write
python3 scripts/inferforge.py readiness
python3 scripts/inferforge.py readiness --no-write
python3 scripts/inferforge.py gate
python3 scripts/inferforge.py coverage
python3 scripts/inferforge.py burp-observation-coverage
python3 scripts/inferforge.py response-deltas
python3 scripts/inferforge.py source-peek-requests
python3 scripts/inferforge.py attack-strategy
python3 scripts/inferforge.py attack-strategy --no-write
python3 scripts/inferforge.py evidence-chain
python3 scripts/inferforge.py evidence-appendix
python3 scripts/inferforge.py verification-queue
python3 scripts/inferforge.py verification-queue --no-write
python3 scripts/inferforge.py manifest
python3 scripts/inferforge.py artifact-health --discover-child-runs
python3 scripts/inferforge.py review-candidates --no-write
python3 scripts/inferforge.py regression-suite --include-external --ws-resource-probes
python3 scripts/inferforge.py adjudicate
python3 scripts/inferforge.py audit --no-ws
python3 scripts/inferforge.py audit --ws-resource-probes
python3 scripts/inferforge.py decode-transactions
python3 scripts/inferforge.py self-test-transactions
python3 scripts/inferforge.py self-test-profile-routing
python3 scripts/inferforge.py self-test-discovery-coverage
python3 scripts/inferforge.py self-test-command-safety
python3 scripts/inferforge.py self-test-review-blockers
python3 scripts/inferforge.py self-test-artifact-health
python3 scripts/inferforge.py self-test-manifest-refresh
python3 scripts/inferforge.py self-test-no-write
python3 scripts/inferforge.py review-blockers
python3 scripts/inferforge.py collect-quote --direction buy --wallet EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR --amount-in 1000000
python3 scripts/inferforge.py collect-orca-baseline
```

`decode-transactions` scans quote probe responses and optional sidecar files for
base64 Solana transaction payloads, then uses the app's `@solana/web3.js`
dependency to decode account keys, signer/writable flags, recent blockhash, and
compiled instruction metadata. It can also compare decoded payloads against an
expected swap intent. It never signs or submits transactions. Extra payload
files can be supplied as JSON, JSONL, or text:

```bash
python3 scripts/inferforge.py decode-transactions --input .greybox/transaction-payloads.jsonl
```

Intent checks can be supplied on the command line:

```bash
python3 scripts/inferforge.py decode-transactions \
  --input .greybox/transaction-payloads.jsonl \
  --intent-direction buy \
  --intent-wallet EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR \
  --intent-amount-in 1000000 \
  --intent-allowed-program 11111111111111111111111111111111
```

Or through `.greybox/transaction-intent-policy.json`:

```json
{
  "direction": "buy",
  "wallet": "EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR",
  "amountIn": "1000000",
  "allowedPrograms": [
    "11111111111111111111111111111111"
  ]
}
```

For `buy`, InferForge expects USDC as the source mint and USD.tel as the
destination mint. For `sell`, the expected mints are reversed. The current
checks verify that the decoded transaction has the expected wallet account, the
wallet is a signer, both expected mints appear in static account keys when
available, compiled instructions are present, and all compiled instruction
program IDs are in `allowedPrograms` when that allowlist is configured. Address
table lookups can require manual review because loaded accounts are not expanded
from chain state.

`collect-quote` is the safe quote-corpus helper. It requests `/api/quote`, saves
a successful quote response to `.greybox/transaction-payloads.json`, writes
`.greybox/quote-collection.json`, refreshes `.greybox/transaction-intent.json`,
updates the related evidence/readiness artifacts, and refreshes the managed
artifact manifest. It does not sign transactions or submit them to Solana.
Non-200 responses are recorded as collection metadata without being treated as
transaction payloads. The collection artifact includes
`diagnosis.classification`, for example `m0-config-missing-or-placeholder` when
the local M0 key is absent or still set to the template placeholder.

`capabilities` writes `.greybox/burp-capabilities.json`, checks target health,
Burp MCP readiness, Burp Proxy availability, and Codex MCP registration, then
performs a read-only Burp MCP `tools/list` inventory. The JSON records available
tool names, required capability coverage for Proxy history, WebSocket history,
Intercept control, HTTP sending, and Repeater creation, plus disabled Scanner,
Intruder-style, and Burp configuration/editor state-editing capabilities when
present. The CLI prints concise `Burp tools:` and `Burp MCP tool inventory:`
lines for unattended setup checks. Use `--no-write` to preview these checks
without refreshing capability artifacts.

`readiness` writes `.greybox/environment-readiness.json`, combining target
health, redacted environment configuration state, the last quote collection
diagnosis, and transaction-corpus status, then refreshes the managed artifact
manifest. `self-test-transactions` writes
`.greybox/transaction-decoder-selftest.json`; it generates a synthetic local
Solana versioned transaction to prove the candidate extractor, decoder, and
intent-policy checks work, but it is not a substitute for a real M0 quote corpus.

`burp-sync` is the preferred automatic Burp loop. It can force Proxy Intercept
off, optionally run the deterministic `burp-observe` flow, read matching Burp
Proxy HTTP history directly through Burp MCP, save the raw MCP output to
`.greybox/burp-mcp-history-latest.txt`, import normalized observations, refresh
traffic clustering, write `.greybox/burp-mcp-sync.json`, and refresh the managed
artifact manifest. The sync artifact includes `mcp_actions`, a compact audit log
of Burp MCP tool calls with sensitive request bodies, regex values, tokens, and
secrets hashed or redacted; MCP exception messages are summarized by type,
length, and SHA-256 instead of stored as raw text. `burp-sync` prefers the regex
history tools and falls back to the non-regex HTTP/WebSocket history tools when
a Burp MCP version does not expose or cannot run the regex variant; fallback
imports still apply the local target/profile filters before writing normalized
observations:

```bash
python3 scripts/inferforge.py burp-sync --observe --ws-upgrade --replace
```

Without `--observe`, `burp-sync` only reads/imports existing Burp history. Use
`--keep-intercept-state` only when a human intentionally wants Intercept left as
it is.

`burp-observe` sends only the deterministic, low-volume observation set through
Burp Proxy, writes `.greybox/burp-observation-run.json`, and refreshes the
managed artifact manifest. It is meant to create Burp HTTP history for `/health`,
`/api/quote`,
`/api/rpc/solana/devnet`, Orca pool validation, and optionally one WebSocket
upgrade. It does not read Burp history by itself; `burp-sync` or
`import-burp-history` handles the history import step.

Active probe, observation, and collection commands take a target-scoped lock
under `.greybox/locks/` before sending traffic. This prevents two audits, Burp
observation runs, or single-purpose collectors from hitting the same target at
the same time and creating false positives in resource-control checks,
especially WebSocket connection limit probes. Stale locks from dead processes
are cleaned automatically.

For automation, Burp Proxy should be listening on `127.0.0.1:8080` and Proxy
Intercept should normally be off. The tool needs requests to pass through Burp
and land in HTTP history; pausing every request is useful for manual inspection
but blocks repeatable runs.

`coverage` writes `.greybox/blackbox-coverage.json`, a gate-style summary of
Burp observation, safe probe execution, source context, policy-field coverage,
readiness, and known evidence gaps. The current target can be `covered` or
`covered-with-external-blocker`; the latter is expected while the M0 quote
transaction corpus is blocked by placeholder credentials.
For generated starter profiles, source-discovered surfaces that are intentionally
not actively probed, such as reviewed-only rewrite proxies, are marked
`not-applicable` for safe-probe and policy-field coverage until a Burp
observation or reviewed probe target is added. Their evidence gaps include
review-only observation candidates that state the concrete approval needed
before automation is allowed.

`burp-observation-coverage` writes `.greybox/burp-observation-coverage.json`.
It is a read-only Burp workflow index that shows, per cluster, whether Burp
Proxy history already covers the surface, whether `burp-observe` generated a
flow that still needs history import, whether the profile has an active
observation path ready for `burp-sync --observe`, or whether a review-only
candidate must be promoted first. It does not send requests; use
`burp-sync --observe --ws-upgrade --replace` for deterministic low-volume Burp
traffic after the profile is reviewed.

`discovery-coverage` writes `.greybox/discovery-coverage.json`. It compares the
static `route-inventory.json` surfaces against the current target profile,
active Burp observation plan, imported Burp history, probe results, review-only
observation candidates, and source-only contexts such as middleware, Server
Actions, redirects, and header policies. This catches drift where static
discovery finds a new route, rewrite, or custom-server entrypoint that the
profile does not yet represent. The command does not send requests; it reads
local source/profile/artifacts only. For discovered profiles, review-gated
rewrite proxies normally produce `needs-human-review` until one approved
concrete local path is promoted:

```bash
python3 scripts/inferforge.py \
  --profile .greybox/discovered-profile.json \
  discovery-coverage
```

Use `--strict` in CI when review-gated or source-only surfaces should fail the
job instead of returning a successful `needs-human-review` status.

`response-deltas` writes `.greybox/response-delta-analysis.json`, a read-only
black-box evidence index over `probe-results.jsonl`. It groups probe rows by
cluster and endpoint, records status-code, response-hash, body-shape,
expectation, retry, truncation, and transport-error variants, and marks groups
as `stable`, `expected-deltas`, `interesting`, or `review-needed`. Deltas are
not findings by themselves; any `review-needed` group still has to flow through
the suspicion engine and finding gate before reportability.

`evidence-chain` writes `.greybox/evidence-chain.json`, a machine-readable index
that ties each endpoint cluster to Burp observations, safe probes, source-peek
context, finding-gate decisions, coverage checks, and remaining evidence gaps.
It only reads existing artifacts; it does not run probes, sign wallets, or submit
transactions.

`source-peek-requests` writes `.greybox/source-peek-requests.json`, a read-only
index that explains why source context was consulted. Requests can be triggered
by Burp/probe-observed endpoints, concrete suspicions, evidence gaps, or
source-only Server Action discovery. This artifact does not send traffic or read
more than the existing source resolver context; it records the question,
black-box evidence refs, source refs, and answer artifact for review.

`attack-strategy.json` is the machine-readable strategy contract for the run. It
records the active methodology, specific strategy coverage for each endpoint
cluster, next-development-action status counts, and a top-level status such as
`ready-for-regression`, `needs-external-evidence`, or `needs-strategy-review`.
It is generated from local run context only; it does not execute probes. Use
`attack-strategy --no-write` to preview the same coverage, uncovered clusters,
and cluster-relevant waiting actions without writing `attack-strategy.json`,
target-profile artifacts, or refreshed manifests.

`source-peek-results.json` also includes an `endpoint_resolver` section. The
resolver statically maps observed HTTP endpoints back to matching Next.js App
Router route files or `next.config.*` rewrite definitions, including source
refs, relevant handler/rewrite lines, fixed-upstream hints, and method-mismatch
notes for safe method-confusion probes. It also attaches matching Next.js
middleware/proxy context for HTTP endpoints when static matchers can be resolved,
and marks complex matcher expressions as possible unresolved context instead of
claiming a hard match. Redirect and header rules from `next.config.*` are
attached as route-policy context so response behavior and security headers can
be reviewed without adding active probes. The traffic index keeps a redacted
request context summary for observed endpoints: method, path, host, header
names and safe values, query parameters, and cookie names with cookie values
redacted. Rewrites, redirects, and headers with `has` / `missing` conditions are
then classified as `condition-satisfied`, `condition-not-satisfied`, or
`condition-unknown` against those observed request contexts. If a condition
depends on a redacted sensitive value, the resolver preserves that as unknown
rather than guessing. For apps with static `basePath`, `trailingSlash`, or
`i18n` locale prefixes, the resolver matches observed runtime paths such as
`/console/fr/api/widgets/` back to their source path, for example
`/api/widgets`, and records match reasons like `basePath:/console`,
`locale-prefix:fr`, and `trailingSlash:canonical`. Statically discovered Server
Actions are included as source context with action export names and `'use
server'` line refs, but they are not probed or treated as HTTP endpoints.
Statically discovered custom-server WebSocket upgrade paths map back to their
upgrade handler and proxy source lines; WebSocket paths are not forced through
unrelated HTTP route files.

`evidence-appendix` writes `.greybox/evidence-appendix.json`, a compact,
redacted request/response evidence package grouped by endpoint cluster. It keeps
representative probe examples, Burp observations, response hashes, request body
hashes, and coverage checks so report claims can be reproduced without rerunning
the probes.

`verification-queue` writes `.greybox/verification-queue.json` and
`.greybox/reproduction-steps.md`. It translates the current evidence appendix,
coverage gate, adjudication, and evidence gaps into concrete low-volume replay
commands, read-only refresh commands, and explicit external blockers.
Use `verification-queue --no-write` to preview the queue status, command safety
totals, top queue items, and labeled command previews without writing queue
artifacts, reproduction steps, review blocker outputs, or refreshed manifests.
Manual-review or external-blocker items that have no generated command template
also print compact follow-up details, including reason, prerequisites, review
candidates, evidence refs, and safety notes, so commandless review work is
visible without opening `verification-queue.json`.
Server Action gaps are emitted as source-only `manual-review` items with no
runnable command templates; the queue points back to `source-peek-results.json`
and lists the action names, source file, and review questions. The read-only
evidence index refresh command also rebuilds `source-peek-requests.json` so
source-review rationale stays in sync with the evidence chain.

Each queue item also contains `command_safety` metadata. Commands are classified
as `ready`, `manual-template` when they still contain `REPLACE_WITH_*`,
`review-gated` when they depend on an approved/manual-review step, or
`unsafe-template` when shell-sensitive placeholder syntax such as `<...>` or
control operators are present. The CLI and reproduction steps print command
safety totals for runnable, manual-input, external-blocked, unsafe, and
placeholder counts so unattended runs can tell whether commands are ready to
execute. `verification-queue` returns a non-zero status if unsafe command
templates are generated. Human-review and external-configuration states are
encoded in the JSON artifacts; use `review-blockers --strict` when those states
should fail a CI job.

`review-blockers` writes `.greybox/review-blockers.json` plus
`.greybox/review-blockers.md`, a read-only summary of the human-review,
profile-update, and external blockers currently spread across discovery
coverage, Burp observation coverage, verification queue, source-peek requests,
environment readiness, and artifact health. `audit` and `verification-queue`
refresh it automatically.
The Markdown playbook is useful as the first artifact to inspect after a
regression run because it keeps the approved-path, source-only review, missing
profile coverage, external-configuration actions, and gated command templates in
one list. The JSON also includes grouped blockers so repeated runs can preserve
per-run evidence while the playbook shows de-duplicated next actions. Grouped
human-review blockers preserve compact review-candidate path templates and
command templates so the next manual approval step is visible without opening
every individual blocker. The CLI prints the grouped blocker summaries first,
including count, cluster, candidate ids, and next action. In `--no-write` mode,
top groups with queued commands also print compact command safety totals and
per-command classification labels such as `manual-template` and `review-gated`
so the approval step can be previewed without writing artifacts. Commandless
groups print compact follow-up context, including split next actions, artifact
dirs, source artifacts, evidence refs, and per-source counts, so external or
manual blockers remain actionable without opening the JSON artifact. When
artifacts are written, the JSON stores the same per-command classification refs
and the Markdown playbook renders them as shell comments before each command.
When `--check-dir` is repeated, it builds a root-level rollup across multiple
artifact directories:

```bash
python3 scripts/inferforge.py review-blockers
python3 scripts/inferforge.py review-blockers \
  --check-dir .greybox/regression-default \
  --check-dir .greybox/regression-discovered
python3 scripts/inferforge.py review-blockers \
  --check-dir .greybox/regression-default \
  --check-dir .greybox/regression-discovered \
  --no-write
```

Use `--discover-child-runs` to roll up child artifact directories under
`.greybox` that already contain `review-blockers.json`, `--no-write` to print
the same grouped summary without writing `review-blockers.json`,
`review-blockers.md`, or refreshed manifests, and `--strict` when any remaining
blocker should fail a CI job.

`manifest` writes `.greybox/artifact-manifest.json`, an integrity snapshot with
SHA256 hashes, sizes, modification timestamps, generated-at timestamps, JSONL row
counts, key status summaries, and missing-required-artifact checks. `audit`
generates this manifest as its final write so the manifest covers the rendered
report and index page. Standalone local refresh commands that rewrite existing
top-level artifacts, such as `profile`, `plan`, `collect`, `burp-observe`,
`burp-sync`, `import-burp-history`, `coverage`, `burp-observation-coverage`,
`discovery-coverage`, `response-deltas`, `source-peek-requests`,
`evidence-chain`, `evidence-appendix`, `verification-queue`, `review-blockers`,
`gate`, `adjudicate`, `artifact-health`, `review-candidates`,
`promote-observation-candidate`, `discover-profile`, `capabilities`,
`readiness`, `decode-transactions`, `collect-quote`, `collect-orca-baseline`,
and the static `self-test-*` commands, also refresh the manifest when their
output lands in the managed artifact directory.

`artifact-health` writes `.greybox/artifact-health.json`, a local health summary
over one or more artifact directories. It parses every top-level JSON and JSONL
artifact, checks the manifest's missing-required list, verifies that manifest
SHA256/size entries still match current files and that no new top-level artifact
is missing from the manifest, detects stale derived outputs such as
`report.md`, `index.html`, `reproduction-steps.md`, and `review-blockers.md`,
checks `mcp_actions` audit records for raw sensitive arguments, raw result text,
or raw exception messages,
carries forward key gate statuses such as black-box coverage, discovery
coverage, verification queue, review blockers, response deltas,
source-peek requests, and Burp observation coverage, and
classifies each run as `healthy`, `ready-with-external-blockers`,
`needs-human-review`, or `failed`. When it writes `artifact-health.json` inside
a managed artifact directory, it refreshes that directory's manifest so the
health artifact does not make the next integrity check stale. When stale inputs
exist, the CLI prints the first few affected files with their reason, newer
inputs, and suggested refresh command. It is useful after regression runs:

```bash
python3 scripts/inferforge.py artifact-health \
  --check-dir .greybox/regression-default \
  --check-dir .greybox/regression-discovered

python3 scripts/inferforge.py artifact-health --discover-child-runs
python3 scripts/inferforge.py artifact-health --discover-child-runs --no-write
```

When `regression-suite.json` is present, `--discover-child-runs` checks the
suite, default, and discovered artifact directories recorded by that run before
falling back to raw child-directory manifest discovery. Recorded regression
directories are still checked when their manifest or directory is missing, so a
broken managed run fails health instead of being silently skipped.

By default the command returns non-zero only for failed or missing artifact
sets. Use `--strict` in CI when human-review or external-configuration blockers
should also fail the job.

`regression-suite` runs the repeatable local regression workflow that is used to
develop the tool against `infrafi-web`: run static profile-routing, discovery
coverage, command-safety, review-blocker, artifact-health, and
manifest-refresh, and transaction-decoder self-tests, refresh static discovery,
check that the discovered profile covers every static surface or review gate,
run deterministic Burp observe/sync for the checked-in profile and discovered
profile, collect one source-known Orca pool baseline, run both audits, write
artifact health, and then generate a root-level review-blocker
rollup, `regression-suite.json`, and a refreshed root `artifact-manifest.json`. The
suite also prints the top grouped review blockers at the end so unattended runs
surface the next action directly. It clears only
generated `probe-results.jsonl` files in the selected regression artifact
directories before audit so reruns do not accumulate stale probe rows. It does
not run Burp Scanner, fuzz broadly, invoke Server Actions, sign wallets, or
submit transactions.

```bash
python3 scripts/inferforge.py regression-suite --include-external --ws-resource-probes
```

Use `--skip-self-tests`, `--skip-discovery-coverage`, `--skip-review-blockers`,
`--skip-burp-sync`, `--skip-orca-baseline`, `--skip-audit`, or
`--skip-discovered` for narrower local checks. Use `--strict` when human-review
or external-configuration blockers should fail the command.

`adjudicate` writes `.greybox/adjudication.json` and refreshes
`.greybox/findings.json` plus `.greybox/hardening-notes.json`. The adjudicator
enforces the reportability contract: only `valid-finding` items whose finding
gate passed are allowed into `findings.json`; accepted hardening notes are kept
separate and must not be reported as exploitable vulnerabilities.

`import-burp-history` is the manual/offline fallback when raw MCP output has
already been saved. For normal runs, prefer `burp-sync`.

`import-burp-history` accepts the raw text returned by Burp MCP
`get_proxy_http_history` / `get_proxy_http_history_regex`. It understands MCP
text wrapper JSON, a JSON array of history items, JSONL, and Burp's blank-line
separated JSON object output. By default it filters to the current `--target`
host and writes normalized observations to:

```text
.greybox/burp-history-observations.jsonl
```

HTTP history entries that capture a `101 Switching Protocols` WebSocket upgrade
are normalized as `WS` observations, so a Burp Proxy upgrade record can cover the
Solana RPC WebSocket cluster even when Burp's separate WebSocket-history MCP
query is unavailable or slow.

During import, InferForge also scans full raw Burp response bodies for
`POST /api/quote` transaction payload candidates, writes
`.greybox/burp-transaction-candidates.json`, and refreshes
`.greybox/transaction-intent.json`. This lets a successful quote captured by
Burp's built-in browser feed the transaction intent decoder without copying
payloads by hand. It also refreshes the managed artifact manifest. The decoder
remains inspect-only: it does not sign or submit transactions.

Pipe raw MCP output directly when convenient:

```bash
python3 scripts/inferforge.py import-burp-history --replace --input -
```

Artifacts are written to:

```text
.greybox/
```

Serve the generated local report:

```bash
python3 -m http.server 8765 --directory .greybox
```

Then open:

```text
http://127.0.0.1:8765/
```

Key outputs:

```text
.greybox/index.html
.greybox/artifact-manifest.json
.greybox/artifact-health.json
.greybox/regression-suite.json
.greybox/review-blockers.json
.greybox/review-blockers.md
.greybox/discovery-coverage-selftest.json
.greybox/command-safety-selftest.json
.greybox/review-blockers-selftest.json
.greybox/artifact-health-selftest.json
.greybox/manifest-refresh-selftest.json
.greybox/no-write-selftest.json
.greybox/target-profile.json
.greybox/strategy-registry.json
.greybox/profile-validation.json
.greybox/route-inventory.json
.greybox/discovered-profile.json
.greybox/discovered-profile-validation.json
.greybox/discovery-coverage.json
.greybox/review-observation-candidates.json
.greybox/reviewed-profile.json
.greybox/reviewed-profile-validation.json
.greybox/reviewed-observation-promotion.json
.greybox/attack-strategy.json
.greybox/burp-capabilities.json
.greybox/burp-history-observations.jsonl
.greybox/burp-observation-run.json
.greybox/burp-observation-coverage.json
.greybox/burp-transaction-candidates.json
.greybox/collection-summary.json
.greybox/blackbox-coverage.json
.greybox/adjudication.json
.greybox/finding-gate.json
.greybox/hardening-notes.json
.greybox/probe-plan.json
.greybox/probe-ranking.json
.greybox/probe-results.jsonl
.greybox/response-delta-analysis.json
.greybox/orca-baseline.json
.greybox/quote-collection.json
.greybox/environment-readiness.json
.greybox/rpc-method-policy.json
.greybox/transaction-decoder-selftest.json
.greybox/transaction-intent.json
.greybox/transaction-intent-policy.json
.greybox/traffic-index.json
.greybox/endpoint-clusters.json
.greybox/source-peek-requests.json
.greybox/evidence-gaps.json
.greybox/evidence-chain.json
.greybox/evidence-appendix.json
.greybox/verification-queue.json
.greybox/reproduction-steps.md
.greybox/source-peek-results.json
.greybox/suspicions.json
.greybox/findings.json
.greybox/report.md
```

## Quote API Hardening

`infrafi-web/src/app/api/quote/route.ts` now rejects invalid quote requests
before checking the M0 API key or forwarding upstream. The local policy requires:

- `Content-Type` containing `application/json`.
- A JSON object with only `route`, `amountIn`, `sender`, `recipient`, and
  `maxNumQuotes`.
- `route.source` and `route.destination` on chain `Solana`, with allowed mints
  limited to USDC and USD.tel in either direction.
- `amountIn` as a positive integer string with a bounded digit length.
- `sender` and `recipient` as valid Solana public keys, with `recipient`
  matching `sender`.
- `maxNumQuotes` exactly `1`.

Malformed JSON returns `400`, unsupported content type returns `415`, local
policy failures return `400`, and upstream M0 error bodies are not reflected
back to the client.

Template M0 credentials such as `YOUR_M0_ORCHESTRATION_API_KEY_HERE` are treated
as unconfigured, so local development does not forward placeholder credentials
to M0. `/health` reports `m0KeyPresent: false` for missing or placeholder M0
keys.

## Solana RPC Proxy Hardening

`infrafi-web/src/app/api/rpc/_shared.ts` now enforces local request policy before
forwarding Solana JSON-RPC upstream. The same shared policy is used by
`/api/rpc/solana/{cluster}` and the `/api/rpc` compatibility route, which maps
to mainnet. InferForge covers:

- Origin and Referer source checks, including allowed, disallowed, and missing
  source cases.
- `POST`/`OPTIONS` method handling and `GET` method confusion.
- `Content-Type` containing `application/json`; `text/plain` JSON is rejected
  with `415`.
- Malformed JSON and duplicate JSON object keys, including duplicate `method`
  keys that would otherwise be collapsed by `JSON.parse`.
- Blocked, unknown, wrong-type, and allowed JSON-RPC methods.
- Empty batches, oversized batches, and mixed batches containing a blocked
  method.
- Invalid, unsigned transaction payloads for high-impact `simulateTransaction`
  and `sendTransaction` methods. These probes only pass when the response is a
  local rejection or a JSON-RPC error; a JSON-RPC `result`, internal error leak,
  timeout, or transport failure is treated as unexpected.
- `/api/rpc` root-route source, method, content-type, blocked-method, and
  transaction-method controls using local-rejection probes that stop before
  upstream forwarding.

Duplicate keys return `400`, blocked or unknown methods return `403`, oversized
batches return `413`, and invalid request sources return `403`.

The default HTTP RPC allowlist is read-only. `sendTransaction` and
`simulateTransaction` are treated as explicit opt-in methods because wallet
adapters can use the configured RPC connection to broadcast signed transactions.
Enable them only after a deployment decision by either setting:

```bash
SOLANA_RPC_PROXY_ALLOW_TRANSACTION_METHODS=true
```

or by explicitly including them in `SOLANA_RPC_PROXY_ALLOWED_METHODS`. InferForge
writes `.greybox/rpc-method-policy.json` to show the source default allowlist,
the transaction-method gate, frontend transaction-send references, proxy
connection references, and the observed high-impact method probe results.

## Solana RPC WebSocket Hardening

`infrafi-web/server.js` handles WebSocket upgrades for
`/api/rpc/solana/{cluster}` and now validates client messages before forwarding
them upstream. InferForge covers:

- Disallowed Origin handshake rejection.
- Binary frames, malformed JSON, wrong-type methods, and blocked methods.
- Duplicate JSON object keys, including duplicate `method` keys that would
  otherwise be collapsed by `JSON.parse`.
- Empty batches, oversized batches, and mixed batches containing a blocked
  method.
- Optional low-volume connection-limit validation with `audit
  --ws-resource-probes`. This opens at most 11 same-origin sockets, sends no
  subscription messages, expects one `429` handshake rejection from the default
  10-connection cap, and closes opened sockets immediately.

Rejected client messages close with policy code `1008`. Disallowed origins fail
the WebSocket handshake with `403`. Pending-message queue and connection-limit
stress tests remain manual/approval-only beyond this bounded connection-limit
check.

## Orca Pool Proxy Hardening

`infrafi-web/src/app/api/orca/pools/[address]/route.ts` is a fixed-upstream
same-origin proxy for Orca pool data. InferForge covers:

- Invalid base58 characters.
- Too-short and too-long address shapes.
- Encoded traversal markers and extra path segments.
- Query injection attempts on invalid address shapes.
- `HEAD` and `POST` method confusion.

Invalid address shapes return `400`, extra path segments return `404`, and
unsupported methods return `405`. The default audit does not enumerate real pool
addresses or perform broad upstream Orca requests.

Use `collect-orca-baseline` to collect exactly one positive baseline from the
source-known DAWN Orca pool list in `src/lib/partners/orca.ts`, or pass one
explicit `--address`. The command records status, cache headers, body hash, and
JSON shape to `.greybox/orca-baseline.json`; it does not enumerate pool
addresses and does not store the full response body. When this baseline is
missing, `verification-queue` includes a manual-review command template for one
approved `--address` rather than trying candidate addresses automatically. The
template uses `REPLACE_WITH_APPROVED_POOL_ADDRESS` so it is shell-safe but still
fails validation until a real approved address is supplied.

## Burp MCP

Burp MCP is expected at:

```text
http://127.0.0.1:9876
```

Check the local setup:

```bash
scripts/check-burp-mcp.sh
```

Current known state:

- Burp MCP is installed and listening on `127.0.0.1:9876`.
- Codex has a `burp` MCP server registered through `mcp-proxy-all.jar`.
- Codex can create Burp Repeater tabs through MCP.
- Codex can send approved MCP HTTP requests to `127.0.0.1:3100`.
- Codex can read Burp Proxy HTTP history after Burp's built-in browser has
  generated traffic.
- Codex can set Burp Proxy Intercept on/off through MCP.
- Burp's built-in browser is already proxied through Burp; use it for browser
  traffic capture.
- Keep Proxy Intercept off for automated InferForge runs. Turn it on only for
  manual pause/edit/forward workflows.
- Configure a separate Proxy listener only if an external browser or Playwright
  profile needs to proxy through Burp.

## Safety Defaults

The local runner does not do wallet signing, transaction submission, high-volume
fuzzing, destructive state changes, Burp Scanner, Burp Collaborator, or Burp AI.
