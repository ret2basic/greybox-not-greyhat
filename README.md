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

InferForge treats `assessment_mode` as an optimization target, not only as a
data-source switch:

- `greybox` is audit/coverage-first. The goal is maximum dangerous-surface
  coverage across source-derived routes, rewrites, Server Actions, RPC methods,
  transaction flows, resource controls, and evidence gaps. A single finding does
  not end the review if other high-risk surfaces remain uncovered.
- `blackbox` is bounty/validity-first. The goal is to produce at least one
  in-scope, valid, reproducible, high-impact report with the strongest expected
  payout. Complete coverage is secondary; low-impact, weakly reportable,
  uncertain-scope, or high-traffic leads should be parked when a better
  high-confidence bounty lead exists.

The active policy also carries a machine-readable `objective_model`: greybox's
completion unit is `all-dangerous-source-derived-surfaces`, while blackbox's
completion unit is `one-valid-medium-high-critical-report`. The same model also
records `coverage_requirement` and `bounty_validity_policy`, so unattended runs
can distinguish exhaustive audit closure from non-exhaustive bounty pursuit.
Use the global `--assessment-mode greybox|blackbox` option to override the
profile's mode for a single run without editing the profile JSON. Follow-up
commands generated during that run preserve the override, so a blackbox bounty
loop does not silently fall back to coverage-first greybox ordering.

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

For a pure black-box bounty target where you do not have source, start from
Burp built-in browser history instead of static discovery. Exercise only
in-scope user flows in Burp, keep Proxy Intercept off for repeatable automation,
then import or sync the normalized history:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  burp-sync --replace
```

Generate a black-box profile from those observed requests:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-profile \
  --output profiles/in-scope-example-blackbox.json
```

`blackbox-profile` does not send HTTP traffic. It reads
`burp-history-observations.jsonl`, skips likely static assets by default,
groups concrete observed paths into `blackbox-http-observed` clusters, strips
query values from the profile while keeping query parameter names, and marks
`assessment_mode: "blackbox"` so later artifacts do not try to read local
source code.

For black-box lead generation, map endpoint and WebSocket candidates from the
target page and same-origin JavaScript assets:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-map \
  --scope-host in-scope.example \
  --force
```

`blackbox-asset-map` sends only low-volume `GET` requests for the selected page
and same-origin script assets. It does not request the candidate endpoints and
does not persist raw HTML or JavaScript. The output
`blackbox-asset-candidates.json` stores path candidates, query parameter names,
source URLs, and source hashes; query values are stripped. Candidate endpoints
are added to verification/review blockers as leads, not as findings, until
scope, authentication context, and business-operation risk are reviewed.
Live page and asset fetches are blocked by the local resource gate while memory
or swap pressure is warning; use `--input-html` for offline parsing, or pass
`--allow-resource-warning` only after explicit review with narrow limits.
If the page references script assets on other hosts, the tool records their
hosts, counts, hashes, and stripped paths as scope-review leads without fetching
those external scripts.
It also builds a passive runtime URL host map from the page and fetched
same-origin assets so API, RPC, quote, prod, or testnet host references can be
reviewed for scope before any request is sent to them. Service-like sibling
hosts are prioritized above static/analytics-style hosts in the review queue.
Each runtime host triage item now includes `impact_hypotheses` and a
`reportability_gate` so leads stay aligned to concrete Web/App bounty impacts:
confidential user-data disclosure, unauthorized authenticated action,
wallet/transaction argument manipulation, production/testnet boundary
confusion, persistent static-content modification, or subdomain takeover.
These mappings are hypotheses only. A configuration reference is not reportable
without confirmed scope and a concrete PoC for the listed impact.

Each candidate is triaged before it reaches the review queue:

- `passive-page-route-review`: page-route-like leads that may be suitable for
  reviewed `HEAD` / `GET` promotion.
- `api-read-candidate-review`: API-like leads without mutation hints; review
  auth and read-only semantics before probing.
- `state-changing-api-review` and `sensitive-api-review`: do not probe
  automatically.
- `websocket-handshake-review`: at most one handshake-only connection after
  scope and message semantics are reviewed.

After reviewing low-risk page-route candidates, promote only those candidates
into a profile:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  blackbox-asset-profile \
  --force
```

`blackbox-asset-profile` is profile-only and sends no HTTP traffic. By default
it promotes only `passive-page-route-review` candidates, strips query values,
keeps query parameter names, and leaves API, WebSocket, sensitive, and
state-changing candidates in the review queue. Use `--allow-triage-class` only
after a candidate class has a safe, read-only reproduction plan.
For promoted page-route candidates, the generated profile also includes a
minimal Burp observation plan: one `HEAD` request per promoted route. This lets
`burp-sync --observe` collect Proxy history automatically after scope review
without requiring a manual browser click path for static page-route evidence.
Locale-style route variants such as `/de-DE/trade/BTCUSD` and
`/en-US/trade/BTCUSD` are collapsed to one representative route family by
default to keep low-resource probe plans small; pass `--include-route-variants`
only when scope and runner capacity justify probing every variant.
Verification queues generated from this asset-candidate profile use a
conservative audit replay by default: `audit --max-probes 6 --no-ws`. They do
not add `--include-external` or `--ws-resource-probes`, and promoted
`reviewed-profile.json` follow-up commands inherit the same restriction from
the profile's asset-candidate safety marker.

Preview the promoted route probes without sending them:

```bash
python3 scripts/inferforge.py \
  --profile .greybox/in-scope-example/blackbox-asset-profile.json \
  --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  plan --no-write
```

Do not add `--observed-only` for this preview: asset profiles are generated from
reviewed static candidates, not Burp-observed traffic, so observed-only planning
will select no clusters until those routes have been observed separately.

After scope review, collect those page-route observations through Burp Proxy:

```bash
python3 scripts/inferforge.py \
  --profile .greybox/in-scope-example/blackbox-asset-profile.json \
  --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  burp-sync --observe --allow-nonlocal-target --replace
```

The observation flow supports HTTPS targets through Burp Proxy CONNECT, forces
Proxy Intercept off by default, does not persist raw MCP history, and filters
history by both target `Host` and the InferForge observation signal so old local
traffic cannot crowd out the current target.

When a bounty program has an explicit host list, turn that scope into a local
policy artifact before reviewing runtime or external hosts:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  scope-policy \
  --scope-host in-scope.example \
  --source-url https://example.com/program-scope
```

`scope-policy` reads existing asset-candidate artifacts only. Listed hosts are
marked `in-scope-explicit-host`; every observed but unlisted host is
`out-of-scope-by-default` unless `--allow-unlisted-review` is set. Verification
queues use this artifact to avoid turning passive runtime config or external
script references into manual blockers when the explicit scope already excludes
them.

For Immunefi-style programs, ingest the public program pages before building a
black-box bounty strategy:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/edgex \
  immunefi-program-profile --program-slug edgex \
  --show-assets --show-impacts --show-techniques --show-links
```

`immunefi-program-profile` reads the standard `information`, `scope`, and
`resources` pages, extracts rewards/KYC/PoC/prohibited-activity sections,
assets in scope, impacts in scope, out-of-scope rules, and documentation or
audit links, then writes `bounty-program-profile.json`. The impact list is also
reverse-mapped into safe planning techniques: for example, authenticated action
impacts map to authorization and browser-mediated action paths, while direct
fund-theft impacts map to transaction argument integrity and withdrawal/order
authorization boundaries. This command fetches only public Immunefi pages; it
does not probe in-scope assets and it does not authorize exploitation.

If the static page fetch is incomplete or blocked, export the rendered pages
from a browser and feed local files instead:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/edgex \
  immunefi-program-profile --program-slug edgex \
  --input-dir ./program-pages --no-fetch \
  --show-impacts --show-techniques
```

The input directory can contain `information.html`, `scope.html`,
`resources.html`, or the same names with `.txt`/`.md`. Prefer HTML exports when
you need asset URLs and resource links preserved; plain text is enough for
impact/out-of-scope parsing when links are not present. If Immunefi declares
more impacts or assets than the parser can see, the artifact is marked
`partial-needs-review` and `manual_input_recommended` so later strategy steps do
not pretend the scope is complete.

For source-first local triage, run an offline source risk review before active
testing:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --top 12 --show-signals --show-workbook
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --top 12 --show-signals --show-workbook
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --top 8 --surface shared-library --show-dependencies
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --top 8 --signal wallet-transaction-payload-boundary --dependency-status client-reachable-source
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --top 8 --surface nextjs-app-route --show-route-guards
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --top 8 --show-config-context --config-status public-secret-env-review
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus wallet --top 6 --show-packet --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus external-deps --top 8 --show-external-deps
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus imported-invocation --top 8 --show-imported-invocation --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus input-shape --top 8 --show-input-shape --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus object-key-trust --top 8 --show-object-key-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus csrf-origin --top 8 --show-csrf-origin --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus cors-origin-trust --top 8 --show-cors-origin-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus control-order --top 8 --show-control-order --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus control-effect --top 8 --show-control-effect --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus response-exposure --top 8 --show-response-exposure --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus download-response-trust --top 8 --show-download-response-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus cache-policy --top 8 --show-cache-policy --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus path-trust --top 8 --show-path-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus upload-trust --top 8 --show-upload-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus auth-token-trust --top 8 --show-auth-token-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus auth-flow-trust --top 8 --show-auth-flow-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus account-recovery-trust --top 8 --show-account-recovery-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus role-permission-trust --top 8 --show-role-permission-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus cookie-trust --top 8 --show-cookie-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus message-trust --top 8 --show-message-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus client-rendering-trust --top 8 --show-client-rendering-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus security-header-trust --top 8 --show-security-header-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus client-storage-trust --top 8 --show-client-storage-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus randomness-trust --top 8 --show-randomness-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus crypto-primitive-trust --top 8 --show-crypto-primitive-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus business-value-trust --top 8 --show-business-value-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus tenant-scope-trust --top 8 --show-tenant-scope-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus workflow-precondition-trust --top 8 --show-workflow-precondition-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus resource-fanout-trust --top 8 --show-resource-fanout-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus sensitive-logging-trust --top 8 --show-sensitive-logging-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus error-disclosure-trust --top 8 --show-error-disclosure-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus debug-surface-trust --top 8 --show-debug-surface-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus code-exec-trust --top 8 --show-code-exec-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus server-template-trust --top 8 --show-server-template-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus deserialization-trust --top 8 --show-deserialization-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus archive-extraction-trust --top 8 --show-archive-extraction-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus xml-parser-trust --top 8 --show-xml-parser-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus regex-complexity-trust --top 8 --show-regex-complexity-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus query-trust --top 8 --show-query-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus graphql-resolver-trust --top 8 --show-graphql-resolver-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus ssrf-trust --top 8 --show-ssrf-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus redirect-trust --top 8 --show-redirect-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus webhook-trust --top 8 --show-webhook-trust --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus identity --top 8 --show-identity-binding --show-triage
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  source-risk-review --no-write --focus client-exposure --top 8 --show-client-exposure --show-triage
```

`source-risk-review` reads bounded local source files only and writes
`source-risk-review.json`. It looks for code boundaries that deserve manual
review, including mutation routes, Server Actions, credential/header forwarding,
fixed-upstream fetches, wallet transaction construction, GraphQL resolver maps,
file write/upload sinks, dynamic HTML rendering, origin/CORS controls, resource
fanout limits, sensitive logging or telemetry boundaries, account-recovery
lifecycle trust, and error response disclosure boundaries.
The output is a prioritized lead list, not a finding: each lead keeps source
refs, signal ids, inferred source surface metadata such as Next.js route paths,
HTTP methods, dynamic segments, source kind, review lanes, a structured offline
review workbook, heuristic control context, reportability gates, stop
conditions, evidence requests, and a safe next step. The control context indexes
same-file auth/session guards, authorization or ownership checks, request
validation, method/content-type checks, origin/CSRF hints, rate limits, and error
boundaries so mutation leads can be separated into `no-obvious-controls`,
`validation-controls-only`, or `access-control-context-indexed` buckets.
It also indexes direct local imported helper controls for each lead. If a route
or helper imports a checked-in guard module, `source-risk-review` can show
`imported-access-control-context-indexed`,
`imported-validation-controls-only`, or `no-imported-controls-indexed` without
executing the import. Imported controls are context only: they do not prove the
guard is called before the sensitive operation or that the policy is correct.
The review also indexes static imported guard invocation context for direct
local imports. It resolves imported callable names from local import syntax,
looks for same-file calls, and compares call lines to sensitive sink lines so
statuses such as `imported-invoked-control-before-sink-indexed`,
`imported-invoked-control-after-sink-review`,
`imported-control-not-invoked-review`, and
`imported-control-invocation-unresolved` can separate likely useful context
from stale imports or late guard calls. Imported callable names are also
filtered before line-order promotion: ordinary helper or SDK-like calls such as
store accessors, transaction classes, and derivation helpers are kept as
`imported-control-callables-not-control-like` context instead of being treated
as guard-order evidence. This is source triage only: it does not execute
imports, prove branch reachability, prove authorization semantics, invoke
routes, send requests, or prove exploitability.
The review also indexes request-shape context for mutation boundaries. It looks
for `await req.json()`, schema parsing, strict or permissive schema handling,
explicit field allowlists, request-body object spread such as `{ ...body }`,
direct body writes such as `data: body`, dynamic field keys, and local
database/service mutation calls. Statuses such as
`input-shape-mass-assignment-review`, `input-shape-spread-review`,
`input-shape-unvalidated-mutation-review`,
`input-shape-strict-validation-indexed`, and
`input-shape-validation-context-indexed` help queue manual review of unknown
field handling, mass-assignment-style writes, and request body allowlists. These
are static hints only: they do not prove a mass assignment bug, validation
correctness, runtime reachability, or reportability.
The review also indexes static object-key trust context. It looks for
caller-controlled request objects, URLSearchParams entries, form entries, object
keys, and dynamic field names near `Object.assign`, object spread, deep merge,
lodash merge/set, `defaultsDeep`, `Object.fromEntries`, and bracket property
writes, then correlates them with key allowlists, schema strictness,
own-property checks, reserved-key rejection, `Object.create(null)`, and `Map`
safe-container controls. Statuses such as
`object-key-untrusted-merge-review`, `object-key-dynamic-write-review`,
`object-key-control-context-indexed`,
`object-key-safe-container-context-indexed`, and
`object-key-context-indexed` help queue manual review of broad merge/set and
dynamic property-write assumptions. These are static source hints only: they do
not construct prototype-mutation payloads, fuzz keys, execute merge behavior,
invoke routes, prove exploitability, or prove reportability.
The review also indexes static browser-session mutation origin and CSRF context.
It correlates mutation routes and Server Actions with cookie/session identity
refs, bearer/API-key/JWT refs, same-file origin/referer/CSRF controls,
content-type/method controls, imported local guard context, and matched route
middleware controls. Statuses such as `csrf-origin-cookie-mutation-review`,
`csrf-origin-safe-method-mutation-review`,
`csrf-origin-missing-origin-review`,
`csrf-origin-contextual-control-indexed`,
`csrf-origin-context-indexed`, and
`csrf-origin-non-cookie-auth-context-indexed` help queue review of browser
session mutation assumptions, including GET/HEAD/OPTIONS routes that appear to
mutate state with cookie/session identity, without treating missing source keywords as proof
of a CSRF issue. These are static source-review hints only: they do not issue
cross-site requests, invoke Server Actions, prove browser reachability, prove
origin policy correctness, prove exploitability, or prove reportability.
The review also indexes static CORS origin response trust context. It looks for
wildcard `Access-Control-Allow-Origin`, credentialed CORS material, request
`Origin` reflection, literal `null` origins, allowed/dynamic origin checks,
permissive substring or regex-like origin allowlists, `Vary: Origin`, preflight
and response-header context, and nearby auth/session/private route material.
Statuses such as `cors-origin-wildcard-credentials-review`,
`cors-origin-null-credentials-review`,
`cors-origin-permissive-allowlist-review`,
`cors-origin-reflection-review`, `cors-origin-missing-vary-review`,
`cors-origin-sensitive-credentials-review`, and
`cors-origin-controlled-context-indexed` help queue manual review of CORS origin
and credential assumptions. These are static source-review hints only: they do
not send cross-origin requests, run browser CORS checks, probe endpoints, replay
traffic, collect or replay cookies/credentials, attempt cache poisoning, prove
runtime headers, prove exploitability, or prove reportability.
The review also indexes same-file control-order context for sensitive sinks. It
compares static line positions for auth/session, authorization, ownership,
request validation, content-type/origin checks, rate-limit hints, and sinks such
as database/service mutations, persistent writes, transaction material, header
forwarding, upstream requests, broad body writes, and resource fanout. Statuses
such as `control-order-access-after-sink-review`,
`control-order-validation-after-sink-review`,
`control-order-rate-limit-after-fanout-review`,
`pre-sink-access-and-validation-indexed`, and
`pre-sink-access-control-indexed` help queue review of code where a control-like
ref appears after a sink or where pre-sink controls may reduce noise. These are
line-order hints only: they do not prove branch execution, call order,
authorization correctness, validation correctness, exploitability, or
reportability.
The review also indexes same-file control-effect context for obvious guard
effect mistakes. It looks for denial response lines such as
`Response.json(..., { status: 401 })` that are not returned or thrown, guard-like
results assigned before sensitive sinks without an obvious branch/assertion,
and guard-like calls before sinks without obvious `await`, `return`, `throw`,
`if`, or assignment context. Statuses such as
`control-effect-denial-fallthrough-review`,
`control-effect-ignored-result-review`,
`control-effect-floating-call-review`, and
`control-effect-enforced-context-indexed` help queue review of controls that may
look present but not actually stop execution. These are static source hints only:
they do not prove framework semantics, branch reachability, runtime behavior,
authorization bypass, exploitability, or reportability.
The review also indexes static JSON response exposure context. It looks for
`Response.json`, `NextResponse.json`, `res.json`, object-return patterns, and
nearby sensitive-looking fields such as user/session identifiers, account or
tenant data, owner fields, email, credential names, wallet/transaction data,
balances, and internal error details. Enriched statuses such as
`response-exposure-sensitive-unguarded-review`,
`response-exposure-cors-sensitive-review`,
`response-exposure-identity-binding-review`,
`response-exposure-sensitive-context-indexed`, and
`response-exposure-context-indexed` combine response shape hints with route
guard, imported control, identity binding, and config/CORS context. These are
static source-review hints only: they do not prove actual response content,
branch reachability, authorization correctness, data exposure, exploitability,
or reportability.
The review also indexes static cache and response-header policy context for
sensitive JSON responses. It looks for `Cache-Control` headers, public/shared
cache directives such as `public`, `s-maxage`, and positive `max-age`, private
or no-store directives, Next.js `revalidate`, `dynamic`, and `cache` settings,
`unstable_cache`, `noStore`, and matching Next.js route headers from checked-in
config. Statuses such as `cache-policy-sensitive-public-cache-review`,
`cache-policy-sensitive-missing-no-store-review`,
`cache-policy-sensitive-private-context-indexed`, and
`cache-policy-context-indexed` help queue review of sensitive response caching
and static rendering assumptions. These are static source/config hints only:
they do not fetch responses, inspect browser or CDN caches, prove runtime
headers, prove cacheability, prove data exposure, or prove reportability.
The review also indexes static download response trust context. It looks for
checked-in `Content-Disposition` and filename response material, framework
download helpers, CSV/spreadsheet export builders, download `Content-Type`
headers such as `text/csv`, spreadsheet MIME types, `text/html`, and
`application/octet-stream`, and correlates those sinks with caller-controlled
filename and export-content sources from query, body, form data, and route
params. It indexes filename sanitization, basename/path stripping, extension or
MIME allowlists, attachment/content-type context, `nosniff` hints, and
CSV/spreadsheet formula escaping helpers. Statuses such as
`download-response-dynamic-filename-review`,
`download-response-csv-formula-review`,
`download-response-html-inline-review`,
`download-response-controlled-context-indexed`, and
`download-response-context-indexed` help queue manual review of export
filenames, disposition/MIME policy, and spreadsheet handling assumptions. These
are static source hints only: they do not request downloads, open exported
files, execute spreadsheet or browser payloads, fetch runtime headers, prove
download behavior, prove exploitability, or prove reportability.
The review also indexes static file path and storage object-key trust context.
It looks for filesystem sinks such as `readFile`, `createReadStream`,
`writeFile`, `unlink`, and `rm`, plus object storage key sinks such as
`PutObjectCommand`, `GetObjectCommand`, `putObject`, `upload`, `download`, and
signed URL helpers. It correlates those sinks with caller-controlled filename,
path, and object-key sources from query, body, form data, and route params, then
indexes normalization, base-directory containment, traversal or absolute-path
checks, extension/content-type allowlists, and tenant/user/project object-key
prefix controls. Statuses such as
`path-trust-user-controlled-path-review`,
`path-trust-traversal-control-context-indexed`,
`path-trust-extension-allowlist-context-indexed`,
`path-trust-literal-context-indexed`, and `path-trust-context-indexed` help
queue manual review of path traversal, arbitrary file access, upload/write, and
object-key trust assumptions. These are static source hints only: they do not
read, write, delete, upload, download, execute routes, prove traversal behavior,
prove exploitability, or prove reportability.
The review also indexes static file upload persistence trust context. It looks
for multipart/form-data, request array buffers, body upload fields, `File`,
`Blob`, and `Buffer.from` upload sources, then correlates them with filesystem
write sinks and object-storage upload sinks such as `writeFile`,
`createWriteStream`, `PutObjectCommand`, `putObject`, storage `upload`, and
Vercel Blob `put`. It indexes MIME/content-type and extension allowlists, byte
limits, private ACL or signed-access controls, tenant/user/project key binding,
and public-serving or cache hints. Statuses such as
`upload-trust-public-write-review`,
`upload-trust-unvalidated-content-review`,
`upload-trust-type-size-controls-indexed`,
`upload-trust-access-control-context-indexed`,
`upload-trust-literal-context-indexed`, and
`upload-trust-context-indexed` help queue manual review of unbounded uploads,
public object writes, type/size validation, ACLs, overwrite, retention, and
serving policy assumptions. These are static source hints only: they do not
upload, read, write, delete, fetch public objects, execute routes, prove upload
behavior, prove exploitability, or prove reportability.
The review also indexes static auth token trust context. It looks for bearer
headers, cookie tokens, API keys, signatures, JWTs, and session-token sources,
then correlates them with decode-only operations such as `jwt.decode`,
`decodeJwt`, `jwtDecode`, `atob`, and token payload parsing, verification
helpers such as `jwt.verify`, `jwtVerify`, `verifyJwt`, `verifyIdToken`, and
`getToken`, unsafe verification options such as disabled expiry/not-before checks
or allowing the JWT `none` algorithm, hardcoded verification-secret literals,
issuer/audience/algorithm/expiry/nonce claim checks, and constant-time
comparison helpers such as `timingSafeEqual` or `safeCompare`.
Statuses such as `auth-token-decode-without-verify-review`,
`auth-token-unsafe-verification-options-review`,
`auth-token-hardcoded-secret-review`,
`auth-token-secret-compare-review`,
`auth-token-missing-claim-controls-review`,
`auth-token-query-source-review`,
`auth-token-claim-controls-context-indexed`,
`auth-token-verification-context-indexed`,
`auth-token-source-context-indexed`, and `auth-token-context-indexed` help queue
manual review of decode-only token trust, API-key comparison, JWT verification
key sourcing, JWT claim validation, URL/query token transport, missing
issuer/audience/algorithm/expiry claim controls, unsafe verification options,
expiry/revocation, and caller/object binding assumptions.
These are static source hints only: they do not mint, forge,
replay, brute-force, submit, or validate authentication tokens at runtime,
execute routes, prove auth bypass, prove exploitability, or prove reportability.
The review also indexes static OAuth/OIDC/SAML/SSO auth-flow trust context. It
looks for callback sources such as `code`, `state`, `nonce`, `provider`,
`redirect_uri`, `callbackUrl`, `returnTo`, `id_token`, `SAMLResponse`, and
`RelayState`, then correlates them with token exchange, callback/session
creation, cookie, redirect, and assertion sinks. It indexes state, nonce, PKCE
or `codeVerifier`, provider/IdP allowlists or expected-provider binding,
redirect allowlist or same-origin checks, issuer/audience, JWKS, id-token
verification, and SAML signature/assertion validation controls.
Statuses such as `auth-flow-missing-state-review`,
`auth-flow-unvalidated-redirect-review`,
`auth-flow-provider-binding-review`, `auth-flow-token-claim-review`,
`auth-flow-pkce-review`, `auth-flow-controlled-context-indexed`, and
`auth-flow-context-indexed` help queue manual review of callback CSRF, open
redirect, provider/IdP mix-up, id-token/assertion claim validation, missing
PKCE/code_verifier handling, provider binding, and session creation
assumptions. These are
static source hints only: they do not invoke login or callback routes, generate,
collect, replay, or validate OAuth/OIDC/SAML tokens or assertions, switch
accounts, submit SSO forms, replay authorization codes, prove auth bypass, prove
exploitability, or prove reportability.
The review also indexes static account-recovery, magic-link, invite, OTP, MFA,
two-factor, verification-code, and recovery-code lifecycle trust context. It
correlates reset tokens, magic tokens, invite tokens, OTP/TOTP/code values,
recovery codes, new passwords, and password fields with password update/reset,
OTP verification, MFA enable/disable, account verification, session creation,
and token consumption sinks. It indexes expiry/TTL/max-age controls,
single-use/revocation/consumption controls, token hashing or constant-time
comparison, account/email/user binding, and attempts/rate-limit/lockout
controls, and can separately queue review when token lifecycle controls are
present but reset, magic-link, invite, or recovery-code material lacks obvious
token-hash or safe-compare context or is transported through URL query or route
parameter context near recovery sinks.
Statuses such as `account-recovery-lifecycle-review`,
`account-recovery-otp-attempt-review`,
`account-recovery-reauth-review`,
`account-recovery-token-hash-review`,
`account-recovery-query-token-review`,
`account-recovery-controlled-context-indexed`, and
`account-recovery-context-indexed` help queue manual review of reset-token
lifecycle, magic-link consumption, invite acceptance, OTP/MFA attempt limits,
recovery-code handling, current-password or step-up re-authentication for
password/MFA changes, token storage or comparison, URL/query token transport,
password update binding, and session creation assumptions. These are static
source hints only: they do not generate, guess, brute-force, replay, submit, or
validate real reset tokens, magic links, invite codes, OTPs, MFA codes, recovery codes, passwords,
or sessions, prove auth bypass, prove exploitability, or prove reportability.
The review also indexes static role, permission, admin flag, invite, and
membership mutation trust context. It correlates caller-controlled `role`,
`roles`, `permission`, `permissions`, `scope`, `isAdmin`, invite role,
membership role, target user, member, organization, and tenant material with
role assignment, permission grant/revoke, membership update, invite creation or
acceptance, and admin-state mutation sinks. It indexes admin policy checks, role
and permission allowlists, role hierarchy, self-escalation protections,
target-subject binding, and same-tenant or same-organization scope controls.
Statuses such as `role-permission-admin-flag-review`,
`role-permission-self-assignment-review`,
`role-permission-role-allowlist-review`,
`role-permission-assignment-review`,
`role-permission-controlled-context-indexed`, and
`role-permission-context-indexed` help queue manual review of privilege grants,
admin flag writes, role changes, grantable-role allowlists, membership updates,
and invite authority assumptions. These are static source hints only: they do not create users, send
invites, change roles, grant permissions, replay membership flows, validate live
privilege changes, prove auth bypass, prove exploitability, or prove
reportability.
The review also indexes static session cookie trust context. It looks for
`Set-Cookie`, `cookies().set`, `res.cookie`, `setCookie`,
`cookie.serialize`, and `document.cookie` writes, classifies cookie names as
session/auth/JWT/CSRF/API-key sensitive, preference-like, or unknown, then
correlates them with `HttpOnly`, `Secure`, `SameSite`, `Max-Age`/`Expires`,
`Path`, `Domain`, `__Host-`, and `__Secure-` controls, including static
`__Host-` requirements for `Secure`, `Path=/`, and no `Domain`, plus
`__Secure-` requirements for `Secure`. Statuses such as
`cookie-trust-client-readable-session-review`,
`cookie-trust-missing-flags-review`,
`cookie-trust-prefix-scope-review`,
`cookie-trust-samesite-none-without-secure-review`,
`cookie-trust-domain-scope-review`,
`cookie-trust-long-lifetime-review`,
`cookie-trust-cross-site-context-indexed`,
`cookie-trust-secure-flags-context-indexed`,
`cookie-trust-non-sensitive-cookie-context-indexed`, and
`cookie-trust-context-indexed` help queue manual review of client-readable
session cookies, missing security flags, prefix-scope gaps, `SameSite=None`
without `Secure`, sensitive cookies scoped with `Domain`, cross-site cookie
intent, long static `Max-Age` lifetimes, scope, and prefix assumptions. These
are static source hints only: they do not
collect, replay, forge, brute-force, submit, or validate real cookies or
sessions at runtime, execute routes, prove session bypass, prove exploitability,
or prove reportability.
The review also indexes static browser message trust context. It looks for
`addEventListener('message', ...)`, `window.onmessage`, `postMessage`,
`MessageChannel`, and `BroadcastChannel` boundaries, then correlates them with
`event.origin`, `event.source`, allowed-origin sets, non-wildcard target
origins, and message schema/type controls. Statuses such as
`message-trust-wildcard-target-review`,
`message-trust-missing-origin-review`,
`message-trust-dynamic-target-review`,
`message-trust-origin-control-context-indexed`,
`message-trust-target-origin-context-indexed`, and
`message-trust-context-indexed` help queue manual review of wildcard
`targetOrigin`, dynamic target-origin derivation without obvious allowlist
context, missing sender-origin checks, message schema assumptions,
iframe/parent contracts, and cross-window trust boundaries. These are static
source hints only: they do not create, send, replay, fuzz, or validate browser
messages at runtime, execute routes, prove message-origin bypass, prove
exploitability, or prove reportability.
The review also indexes static client rendering trust context. It looks for raw
HTML/DOM sinks such as `dangerouslySetInnerHTML`, `__html`, `innerHTML`,
`outerHTML`, `insertAdjacentHTML`, `document.write`, `DOMParser`, markdown
renderers, and HTML parser helpers, then correlates them with props, URL/search
params, browser storage, API/CMS/rich-text/markdown sources, DOMPurify,
`sanitize-html`, output encoding, Trusted Types, and markdown sanitization
controls. Statuses such as `client-rendering-unsanitized-html-review`,
`client-rendering-markdown-html-review`,
`client-rendering-sanitized-context-indexed`, and
`client-rendering-static-literal-context-indexed` help queue manual review of
content provenance, sanitizer policy, allowed tags/attributes, URL protocols,
and output context. These are static source hints only: they do not generate XSS
payloads, run a browser, invoke pages or routes, replay content, prove XSS,
prove exploitability, or prove reportability.
The review also indexes static client-side storage trust context. It looks for
`localStorage`, `sessionStorage`, IndexedDB, `document.cookie`, and
storage-persistence helpers such as `localForage`, idb-keyval-style helper
calls, `createJSONStorage`, and `persist`, then classifies storage keys and
value variables as auth/session/API-key/JWT
sensitive, wallet-secret-like, personal/account data, preference-only, or
unknown. Statuses such as `client-storage-wallet-secret-review`,
`client-storage-sensitive-no-lifecycle-review`,
`client-storage-sensitive-material-review`,
`client-storage-sensitive-read-context-indexed`,
`client-storage-personal-data-context-indexed`,
`client-storage-non-sensitive-context-indexed`, and
`client-storage-context-indexed` help queue manual review of browser-readable
tokens, session state, API keys, wallet private keys or seed phrases, storage
retention, cleanup, validation, and whether stored values are later trusted as
authority. These are static source hints only: they do not open a browser, read
real storage, collect cookies or tokens, forge, replay, submit, exfiltrate, or
validate stored material at runtime, execute routes, prove exploitability, or
prove reportability.
The review also indexes static security-material randomness trust context. It
looks for `Math.random`, time-derived values such as `Date.now`, and
cryptographic sources such as `crypto.randomUUID`, `getRandomValues`,
`randomBytes`, `randomInt`, `nanoid`, and UUID helpers near token, session,
API-key, nonce, CSRF/OAuth state, OTP, reset, magic-link, and invite material.
Statuses such as `randomness-trust-weak-security-material-review`,
`randomness-trust-time-based-material-review`,
`randomness-trust-strong-random-context-indexed`,
`randomness-trust-non-security-context-indexed`, and
`randomness-trust-context-indexed` help queue manual review of predictable
security material generation while keeping ordinary UI/game/animation
randomness out of high-priority findings. These are static source hints only:
they do not generate, guess, brute-force, replay, submit, or validate real
tokens, OTPs, reset links, invite codes, CSRF values, OAuth state values,
sessions, or API keys at runtime, execute routes, prove exploitability, or
prove reportability.
The review also indexes static crypto primitive trust context. It looks for
caller-controlled algorithm, hash, cipher, key, secret, IV, nonce, salt,
signature, MAC, plaintext, and ciphertext material near `createHash`,
`createHmac`, `createCipheriv`, `createDecipheriv`, WebCrypto, CryptoJS,
deprecated Node `createCipher`/`createDecipher`, hash/HMAC/cipher/sign/verify
sinks, non-AEAD modes such as AES-CBC, AES-CTR, AES-CFB, and AES-OFB, weak
primitives such as MD5, SHA-1, DES, RC4, and ECB, static IV or nonce hints, and
literal key, secret, signing/encryption key, or passphrase material near crypto
primitive sinks. It also records same-file AEAD, HMAC/MAC/auth tag, random IV/nonce, KDF,
key-management, algorithm allowlist, and constant-time compare controls.
Statuses such as
`crypto-user-controlled-algorithm-review`,
`crypto-deprecated-cipher-review`,
`crypto-weak-algorithm-review`, `crypto-static-iv-review`,
`crypto-hardcoded-key-review`, `crypto-unauthenticated-cipher-review`,
`crypto-controlled-context-indexed`, `crypto-literal-context-indexed`, and
`crypto-context-indexed` help queue manual review of primitive selection,
deprecated password-derived cipher helpers, unauthenticated encryption modes,
IV/nonce uniqueness, key origin, hardcoded secret handling, signature/MAC
verification, and compare behavior. Literal secret-like samples are redacted in
the review output. These are static source hints only: they do not print raw
secrets, validate keys, compute hashes, encrypt, decrypt, forge tokens or
signatures, brute-force keys, generate chosen-ciphertext or chosen-plaintext
payloads, invoke routes, replay requests, fuzz crypto inputs, run timing tests,
prove exploitability, or prove reportability.
The review also indexes static payment, order, balance, and entitlement
business-value trust context. It looks for caller-controlled `amount`, `price`,
`total`, `quantity`, `discount`, `coupon`, `currency`, `balance`, `credits`,
`points`, and `fee` fields near checkout, payment, order, invoice,
subscription, ledger, wallet, balance, credit, and entitlement writes, then
correlates them with server-side product, plan, catalog, price-book, currency,
quantity, coupon, and numeric-limit controls. Statuses such as
`business-value-client-controlled-amount-review`,
`business-value-client-controlled-discount-review`,
`business-value-client-controlled-quantity-review`,
`business-value-server-derived-context-indexed`,
`business-value-validation-context-indexed`, and
`business-value-context-indexed` help queue manual review of whether client
values are authoritative or merely hints before payment and business-state
writes. These are static source hints only: they do not create orders, charge,
refund, transfer funds, alter balances, redeem coupons, mint credits, replay
checkout sessions, submit payment flows, prove exploitability, or prove
reportability.
The review also indexes static tenant and object scope trust context. It looks
for caller-controlled user, owner, tenant, account, organization, project,
order, invoice, document, file, wallet, and object identifiers near database,
repository, service, mutation, and JSON response boundaries, then correlates
them with caller-to-object ownership, tenant, membership, wallet, imported
policy, auth-only, and scoped-query controls. Statuses such as
`tenant-scope-missing-review`, `tenant-scope-auth-only-review`,
`tenant-scope-client-scope-review`,
`tenant-scope-contextual-control-review`,
`tenant-scope-controlled-context-indexed`, and
`tenant-scope-context-indexed` help queue manual review of IDOR/BOLA and
multi-tenant authorization assumptions, including client-supplied tenant,
account, organization, user, owner, or wallet scope used as a query constraint,
without pretending a source smell is a finding. These are static source hints only: they do not invoke routes,
enumerate ids, switch or act as another user, collect cross-tenant data, replay
requests, mutate tenant objects, prove exploitability, or prove reportability.
The review also indexes static workflow-precondition trust context. It looks
for caller-controlled workflow actions, object ids, amounts, coupons, roles,
account fields, status, and state fields near order, payment, refund, coupon,
balance, credit, role, account, password, and workflow-state mutation sinks,
then correlates them with auth, ownership, role/tenant scope, state-machine,
allowed-transition, transaction, lock/version, idempotency, nonce, and replay
controls. Statuses such as `workflow-precondition-missing-review`,
`workflow-state-transition-review`,
`workflow-replay-idempotency-review`,
`workflow-controlled-context-indexed`, and `workflow-context-indexed` help queue
manual review of whether sensitive mutations have the expected access,
transition, and replay preconditions. These are static source hints only: they
do not invoke actions or routes, submit forms, create orders, payments,
refunds, coupons, or balance changes, replay requests, run stress tests, run
rate-limit tests, mutate state, prove exploitability, or prove reportability.
The review also indexes static batch, pagination, retry, polling, and parallel
resource-fanout trust context. It looks for caller-controlled ids/items arrays,
URLs, recipients, batch sizes, limits, page sizes, cursors, offsets, and retry
inputs near `Promise.all`, async map/forEach fanout, pagination/export/list
queries, retry loops, polling, and interval work, then correlates them with
schema `.max()` bounds, `Math.min` clamps, `slice`/`take` caps, rate-limit
guards, queue/concurrency controls, and retry/time-bound controls. Statuses
such as `resource-fanout-client-controlled-batch-review`,
`resource-fanout-unbounded-pagination-review`,
`resource-fanout-parallel-upstream-review`,
`resource-fanout-loop-retry-review`,
`resource-fanout-rate-limit-context-indexed`,
`resource-fanout-bounded-context-indexed`, and
`resource-fanout-context-indexed` help queue manual review of whether caller
input can amplify backend, database, upstream, export, or messaging work. These
are static source hints only: they do not issue requests, run stress tests,
exhaust rate limits, open WebSocket connections, deplete quotas, broaden
crawls/exports, prove availability impact, prove exploitability, or prove
reportability.
The review also indexes static sensitive logging, telemetry, analytics, and
error-reporting trust context. It looks for auth headers, cookies, API keys,
JWTs, sessions, secrets, wallet or payment material, request headers, request
bodies, payloads, and personal data near `console`, logger, Sentry, analytics,
PostHog, Mixpanel, telemetry, Datadog RUM, and New Relic sinks, then correlates
them with same-file redaction, sanitization, scrubbing, masking, hashing,
safe-logger wrappers, and field allowlist controls. Statuses such as
`sensitive-logging-secret-material-review`,
`sensitive-logging-wallet-payment-review`,
`sensitive-logging-request-context-review`,
`sensitive-logging-personal-data-review`,
`sensitive-logging-redacted-context-indexed`, and
`sensitive-logging-context-indexed` help queue manual review of whether
sensitive material can reach logs or third-party telemetry without redaction and
retention controls. These are static source hints only: they do not retrieve
production logs, collect real tokens, cookies, secrets, or PII, query or
exfiltrate telemetry, submit sensitive material, invoke routes, prove exposure,
prove exploitability, or prove reportability.
The review also indexes static error disclosure trust context. It looks for raw
exceptions, stack traces, causes, debug fields, `rawError`, `rawResponse`,
`response.data`, provider/RPC/upstream error bodies, and status text near
`Response.json`, `NextResponse.json`, `res.json`, `reply.send`, and HTTP
response constructors, then correlates them with same-file public-error shaping,
sanitization, redaction, generic error messages, and allowlisted error-code
controls. Statuses such as `error-disclosure-stack-trace-review`,
`error-disclosure-upstream-error-review`,
`error-disclosure-exception-message-review`,
`error-disclosure-sanitized-context-indexed`, and
`error-disclosure-context-indexed` help queue manual review of whether internal
diagnostics or upstream/provider details can reach client-visible JSON/HTTP
error responses. These are static source hints only: they do not trigger live
errors, replay requests, send malformed traffic, invoke routes, retrieve
production logs, query telemetry, collect raw upstream bodies, prove exposure,
prove exploitability, or prove reportability.
The review also indexes static debug, admin, internal, ops, diagnostic, cron,
seed, backfill, maintenance, and devtools surface context. It looks for
debug/internal route names, diagnostic JSON/HTTP response sinks, environment and
header/cookie/config/build/process/stack material, cache revalidation and
job/backfill/seed-style internal action sinks, then correlates them with
same-file auth, admin/role checks, internal-only headers, cron secrets,
environment gates, and denial responses. Statuses such as
`debug-surface-diagnostics-review`,
`debug-surface-internal-action-review`,
`debug-surface-control-context-indexed`, and
`debug-surface-context-indexed` help queue manual review of whether debug or
internal surfaces are production-isolated and access-controlled. These are
static source hints only: they do not request debug endpoints, trigger jobs,
backfills, seeds, cache purges, or admin actions, read production diagnostics,
prove exposure, prove exploitability, or prove reportability.
The review also indexes static runtime command/code execution trust context. It
looks for `child_process` `exec`, `execFile`, `spawn`, and `fork`, bare imported
process execution helpers, `execa`, `shelljs.exec`, `Bun.spawn`, `Deno.Command`,
`eval`, `Function`, and `vm` sinks, then correlates them with request body,
query, params, form data, command/argv/script/code/template material, command or
script allowlists, argv separation, `shell: false`, admin/internal controls, and
environment gates. Statuses such as `code-exec-user-input-review`,
`code-exec-dynamic-code-review`, `code-exec-shell-review`,
`code-exec-controlled-context-indexed`,
`code-exec-literal-context-indexed`, and `code-exec-context-indexed` help queue
manual source review of command/code execution boundaries. These are static
source hints only: they do not run commands, invoke routes, execute eval/vm
code, fuzz command parameters, generate command-injection payloads, replay
requests, prove exploitability, or prove reportability.
The review also indexes static server-side template rendering trust context. It
looks for render/view/compile sinks such as `res.render`, `reply.view`,
`ejs.render`, `pug.render`, `Handlebars.compile`, `Mustache.render`,
`nunjucks.renderString`, `render_template`, `render_template_string`,
`Template(...).render`, `Environment.from_string`, and similar checked-in
template engine calls. It correlates those sinks with caller-controlled template
names, view names, layouts, partials, template strings, locals/render data,
template allowlists, literal trusted templates, escaping/autoescape settings,
sandbox controls, and raw/safe/no-escape contexts. Statuses such as
`server-template-user-controlled-template-review`,
`server-template-unescaped-data-review`,
`server-template-controlled-context-indexed`,
`server-template-literal-context-indexed`, and
`server-template-context-indexed` help queue manual review of template trust
boundaries. These are static source hints only: they do not render templates,
invoke routes, execute helper code, fuzz template names, generate SSTI or XSS
payloads, replay requests, prove exploitability, or prove reportability.
The review also indexes static deserialization trust context. It looks for
checked-in object restore, YAML load/parse, binary object decode, MessagePack,
CBOR, BSON/EJSON, and v8 deserialization sinks such as `unserialize`,
`deserialize`, `yaml.load`, `YAML.parse`, `v8.deserialize`, `BSON.deserialize`,
`msgpack.decode`, and `CBOR.decode`. It correlates those sinks with
caller-controlled serialized payload, state, object, YAML, base64, binary, body,
query, params, and form-data sources, then indexes schema/type allowlists, safe
loader settings, signature or MAC verification, content-type checks, and size
limits. Statuses such as `deserialization-untrusted-input-review`,
`deserialization-unsafe-format-review`,
`deserialization-controlled-context-indexed`,
`deserialization-literal-context-indexed`, and
`deserialization-context-indexed` help queue manual review of parser and object
restore boundaries. These are static source hints only: they do not deserialize
samples, construct gadget chains, generate parser payloads, invoke routes, fuzz
parser inputs, replay requests, execute restored objects, prove exploitability,
or prove reportability.
The review also indexes static archive extraction trust context. It looks for
checked-in zip, tar, bundle, upload, decompression, archive parser, and entry
write sinks such as `AdmZip`, `extractAllTo`, `unzipper.Extract`,
`unzipper.Parse`, `yauzl.open`, `JSZip.loadAsync`, `decompress`, and
`tar.extract`. It correlates those sinks with caller-controlled archive,
upload, file, bytes, destination, and entry-path material, then indexes
basename/safe-join helpers, destination containment checks, preserve-paths-off
settings, strip/filter settings, preserve-paths-on or strip-zero options,
allowed extensions, size limits, and entry-count limits. Statuses such as
`archive-extraction-preserve-paths-review`,
`archive-extraction-user-controlled-review`,
`archive-extraction-entry-path-review`,
`archive-extraction-controlled-context-indexed`,
`archive-extraction-literal-context-indexed`, and
`archive-extraction-context-indexed` help queue manual review of archive
extraction options, path preservation, and entry path boundaries. These are
static source hints only: they do not unzip or untar files, construct Zip Slip
payloads, upload archives, invoke routes, fuzz archive entries, replay
requests, write extracted files, prove exploitability, or prove reportability.
The review also indexes static XML parser trust context. It looks for checked-in
XML parser sinks such as `parseString`, `parseStringPromise`, `XMLParser.parse`,
`DOMParser.parseFromString`, `libxmljs`, `xmldom`, `sax`, and `saxes`, then
correlates those sinks with caller-controlled XML, SOAP, SAML, SVG, RSS, Atom,
feed, document, body, and upload material. It also indexes same-file DOCTYPE and
entity material, entity-processing settings such as `processEntities`, external
resource handling, schema or content-type controls, and size limits. Statuses such as
`xml-parser-untrusted-input-review`, `xml-parser-entity-expansion-review`,
`xml-parser-controlled-context-indexed`,
`xml-parser-literal-context-indexed`, and `xml-parser-context-indexed` help
queue manual review of XML parsing, entity, and external-resource assumptions.
These are static source hints only: they do not parse XML samples, construct XXE
or entity payloads, fetch external entities, invoke routes, fuzz parser inputs,
read local files, prove exploitability, or prove reportability.
The review also indexes static regex complexity trust context. It looks for
checked-in dynamic `RegExp` or `RE2` construction, regex literal `.test`/`.exec`
usage, and string `match`, `replace`, `search`, and `split` regex sinks. It
correlates those sinks with caller-controlled pattern, search, filter, query,
text, body, route, and form material, then indexes same-file pattern allowlists,
literal trusted patterns, escaping helpers, `RE2` or safe-regex review, input
length bounds, truncation, and schema maximum constraints. Statuses such as
`regex-dynamic-pattern-review`, `regex-complex-input-review`,
`regex-controlled-context-indexed`, `regex-literal-context-indexed`, and
`regex-context-indexed` help queue manual review of ReDoS-style availability
assumptions without running regexes. These are static source hints only: they do
not generate ReDoS payloads, run regex benchmarks, fuzz patterns or inputs,
invoke routes, replay requests, stress-test matching, prove exploitability, or
prove reportability.
The `regex-complexity-trust` focus preset uses indexed regex context, so broad
signal-only files remain visible in lane inventory but do not expand the focused
triage list by themselves.
The review also indexes static database query trust context. It looks for raw
SQL and database client sinks such as `$queryRawUnsafe`, `$executeRawUnsafe`,
`query`, `execute`, and `raw`, plus ORM query and mutation sinks such as
`findMany`, `findFirst`, `findUnique`, `update`, `delete`, `upsert`,
`aggregate`, and `count`. It correlates those sinks with caller-controlled
query, search, filter, where, sort, order, identifier, body, query-string, and
route-param sources, then indexes parameterized query APIs, prepared statement
patterns, tagged SQL templates, field/sort/filter allowlists, and owner,
tenant, account, or project scoping controls. Statuses such as
`query-trust-raw-user-input-review`,
`query-trust-client-filter-review`,
`query-trust-parameterized-context-indexed`,
`query-trust-scoped-orm-context-indexed`,
`query-trust-literal-context-indexed`, and `query-trust-context-indexed` help
queue manual review of raw query construction, dynamic filters, sort/field
selection, and tenant/object scoping assumptions. These are static source hints
only: they do not connect to databases, execute SQL, invoke routes, fuzz query
parameters, prove injection, prove authorization bypass, or prove reportability.
The review also indexes static GraphQL resolver trust context. It looks for
GraphQL server/schema/resolver entrypoints such as `ApolloServer`, `createYoga`,
`graphqlHTTP`, `gql`, `typeDefs`, `resolvers`, `Query`, and `Mutation`, then
correlates resolver `args`/`input` and object, tenant, account, project, role, or
state selector args with context auth, caller-to-object scope controls,
validation or field allowlists, pagination/depth/complexity controls, and
database/repository/service data or mutation sinks. Statuses such as
`graphql-resolver-missing-auth-review`,
`graphql-resolver-object-scope-review`,
`graphql-resolver-unbounded-list-review`,
`graphql-resolver-controlled-context-indexed`, and
`graphql-resolver-context-indexed` help queue manual review of resolver
authorization, object-scope, and list pagination or complexity assumptions.
These are static source hints only: they do not execute GraphQL operations,
introspect live schemas, fuzz fields, replay requests, switch accounts, mutate
data, stress-test list fields, prove authorization bypass, prove exploitability,
or prove reportability.
The review also indexes static server-side outbound URL trust context. It looks
for `fetch`, `axios`, `got`, `ky`, and similar outbound request sinks, query,
body, and route fields that look like upstream URLs, URL parsing and hostname
extraction, host allowlists, protocol checks, and private-network or metadata
address blocking. Statuses such as `ssrf-trust-user-controlled-url-review`,
`ssrf-trust-permissive-host-allowlist-review`,
`ssrf-trust-private-fixed-upstream-review`,
`ssrf-trust-allowlist-context-indexed`,
`ssrf-trust-private-network-control-context-indexed`,
`ssrf-trust-fixed-upstream-context-indexed`, and
`ssrf-trust-context-indexed` help queue review of user-controlled full URL
targets, checked-in private/loopback/link-local/metadata upstream URLs, fixed
upstream hosts with dynamic path/query material, permissive host allowlists
that appear to rely on substring/suffix/prefix/regex matching, and allowlist
assumptions.
These are static source hints only: they do not issue outbound requests, follow
redirects, resolve DNS, probe private networks, prove SSRF, prove
exploitability, or prove reportability.
The review also indexes static redirect and navigation destination trust
context. It looks for server redirect sinks such as `NextResponse.redirect`,
`Response.redirect`, `redirect`, and `permanentRedirect`, client navigation
sinks such as `router.push`, `router.replace`, and `location.href`, and
redirect-like query/body/route fields such as `next`, `redirect`, `returnTo`,
`callbackUrl`, `url`, `to`, and `destination`. It correlates those sources with
same-file path-only, same-origin, and allowlist controls, plus checked-in
Next.js redirect route policies, and labels literal `javascript:`, `data:`, or
`vbscript:` redirect/navigation destinations for review. Statuses such as
`redirect-trust-dangerous-scheme-review`,
`redirect-trust-user-controlled-review`,
`redirect-trust-missing-allowlist-review`,
`redirect-trust-external-destination-review`,
`redirect-trust-same-origin-context-indexed`,
`redirect-trust-allowlist-context-indexed`,
`redirect-trust-literal-context-indexed`, and
`redirect-trust-config-context-indexed` help queue manual review of redirect
trust boundaries. These are static source/config hints only: they do not execute
routes, follow redirects, open browsers, prove redirect behavior,
exploitability, or reportability.
The review also indexes static webhook origin-authenticity context. It looks
for webhook-like route paths, provider signature headers such as
`stripe-signature`, `svix-signature`, `x-hub-signature-256`, and
`x-signature`, raw-body reads such as `req.text()` or `arrayBuffer()`, parsed
body reads such as `req.json()` or JSON body parsers, signature verification
helpers such as `constructEvent`, `verifyWebhook`, `verifySignature`,
`Webhook.verify`, HMAC checks, timing-safe comparisons, webhook secret config,
provider event-id material such as `event.id`, same-file idempotency or replay
controls such as event-log lookups, dedupe helpers, unique/upsert/skip-duplicate
patterns, timestamp freshness or replay-window controls, and side-effect sinks
such as database writes, queues, email, or notifications.
Statuses such as `webhook-trust-missing-signature-review`,
`webhook-trust-json-before-signature-review`,
`webhook-trust-missing-secret-review`,
`webhook-trust-missing-idempotency-review`,
`webhook-trust-missing-replay-window-review`,
`webhook-trust-idempotency-context-indexed`,
`webhook-trust-raw-body-signature-context-indexed`,
`webhook-trust-signature-context-indexed`, and
`webhook-trust-context-indexed` help queue review of webhook signature, raw-body,
secret loading, replay-window, timestamp freshness, event-id idempotency, and
provider-trust assumptions. These are static source/config hints only: they do
not deliver webhook requests, replay provider events, call live routes, forge
signatures, prove signature bypass, prove exploitability, or prove
reportability.
The review also indexes static identity and ownership binding context. It looks
for route, body, query, subject, and object identifiers such as `userId`,
`ownerId`, `tenantId`, `accountId`, `projectId`, `invoiceId`, `walletAddress`,
and `publicKey`, then checks the same file for owner/session comparisons, scoped
queries, or guard calls such as `requireOwnership` or `canAccess`. Statuses such
as `identity-binding-gap-review`, `identity-binding-context-indexed`,
`identity-contextual-binding-review`, `identity-access-context-indexed`, and
`identity-validation-only` help queue manual review of object binding near
mutation routes. The contextual status is used when direct local imports or
route-bound middleware contain ownership-like controls, but the lead itself still
needs manual review for call order, caller/object/action binding, and route
coverage. These are static source triage only: they do not execute routes, send
requests, prove an authorization bug, or prove that a guard is sufficient.
The review also indexes static client/server exposure context. It combines local
surface inference, direct client importers, transitive client reachability
chains, env-name context, external package categories, and sensitive boundary
signals to queue cases where client-visible code contains or imports private env
names, public env names that look secret-like, `server-only` or Node-only
runtime imports, Server Action context, database/storage packages, wallet/web3
packages, or transaction encoding boundaries. Statuses such as
`client-secret-exposure-review`, `client-server-only-import-review`,
`client-storage-database-exposure-review`,
`client-wallet-boundary-context-indexed`, and
`client-exposure-context-indexed` are static review hints only: they do not
inspect built bundles, read runtime env values, execute imports, prove browser
reachability, or prove exploitability.
For Next.js route leads, the review also computes a static route-guard context.
It matches checked-in `middleware.*` or `proxy.*` files against the inferred
route path, indexes auth/session, authorization, ownership, origin/CSRF, rate,
and content-type controls inside matched middleware, and assigns route-bound
statuses such as `same-file-access-control-indexed`,
`route-middleware-access-control-indexed`, `route-middleware-validation-controls-indexed`,
or `no-route-middleware-indexed`. These are prioritization hints only: matched
middleware does not prove authorization, and missing middleware does not prove a
bug.
The review also builds a local import graph for relative and `@/` imports, so
shared libraries and route helpers can be marked as `client-reachable-source`,
`route-reachable-source`, `entrypoint-surface`, or `no-local-importers-indexed`
without executing code or resolving npm packages. The dependency context keeps
direct importers plus bounded transitive reachability chains, so a transaction
helper can show `lib -> hook -> component` or `helper -> route` paths for manual
review while still avoiding runtime validation. When a lead is route-reachable,
the review also summarizes the static guard status of the importer routes, so a
shared helper can be prioritized by whether its route callers have same-file
access control, matched middleware controls, validation-only controls, or guard
gaps.
The import graph also reports coverage gaps: `candidate_file_limit_reached`
when `--max-files` truncates the scan, unresolved local imports, local imports
that point outside the candidate set, and external package imports that were
counted but intentionally not resolved. Treat these as triage quality signals,
not findings. Increase `--max-files` or review unresolved aliases before relying
on dependency reachability.
External package imports are also classified as static context without resolving
or executing packages. `source-risk-review` can label direct external imports and
external imports in direct local helpers as wallet/web3, transaction encoding,
HTML/markdown rendering, validation, auth/session, database, storage/upload,
HTTP client, rate-limit, crypto, framework runtime, or generic external package
context. Statuses such as `wallet-transaction-package-context`,
`rendering-package-context`, `auth-validation-package-context`, and
`mutation-storage-package-context` are review orientation only; server-only or
Node-only imports can also be summarized as `server-runtime-package-context`.
These statuses do not audit the package, prove reachability, or imply
exploitability.
The review also adds single-file source/sink flow hints. It indexes local
caller-input, route/query params, headers/cookies, remote response data, and
rendered content sources, then links them to nearby sinks such as upstream
requests, header forwarding, transaction construction, persistent writes, HTML
rendering, state mutations, and resource fanout. Flow statuses such as
`critical-nearby-source-sink-hints` or `same-file-source-sink-hints` are only
prioritization hints: they do not prove true data flow, runtime reachability,
exploitability, or reportability.
The review also builds a static config context. It indexes local source env
variable names, checked-in env template keys, fixed upstream/RPC/quote URL
literals, and Next.js `headers`, `redirects`, and `rewrites` route-policy hints.
Per-lead statuses include `public-secret-env-review` for public client-exposed
env names that look secret-like, `cors-credential-config-review` for route CORS
policy context near credential/header forwarding, `upstream-config-context-indexed`,
`route-policy-config-indexed`, and `env-config-context-indexed`. The config
context never reads runtime env values, does not execute config files, and sends
no requests; it is only a queueing aid for manual source review.
Finally, each lead gets combined triage explainers. These merge signal severity,
flow hints, request-shape context, same-file control-order context, identity
binding context, response exposure context, client/server exposure context,
route guard gaps, route-importer guard context, config context, dependency
reachability, and import-coverage gaps into statuses such as
`critical-multi-context-review`, `critical-review`, `high-context-review`, or
`standard-review`, with explicit reason ids and review hints. These explainers
are queueing aids only; they do not change the finding gate or prove impact.
`--show-workbook` prints the highest-signal lanes, control refs, checks,
local importer refs, evidence requests, and stop condition for the displayed
leads. `--show-dependencies` prints direct imports, importers, reachability
chains, and per-lead import coverage notes without the workbook checklist.
`--show-imported-controls` prints direct local imported helper controls and
their auth, validation, rate, origin, and ownership refs.
`--show-imported-invocation` prints static imported callable names, same-file
call refs, and line-order context between imported guard calls and sensitive
sinks for displayed leads.
`--show-external-deps` prints classified direct external package import context
and external imports found in direct local helpers. It does not resolve npm
packages or read `node_modules`.
`--show-input-shape` prints request body parsing, schema strictness, explicit
field-copy, request-body spread, direct body-write, dynamic key, and mutation
call context for displayed leads.
`--show-object-key-trust` prints static caller-controlled object/key source
refs, merge/set/spread/dynamic-property-write sink refs, key allowlist,
reserved-key rejection, own-property, schema, null-prototype, and Map safe
container context for displayed leads.
`--show-csrf-origin` prints static cookie/session mutation,
GET/HEAD/OPTIONS state mutation, bearer/API-key/JWT, origin/referer/CSRF,
content-type, imported guard, and route middleware context for displayed leads.
`--show-cors-origin-trust` prints static CORS origin source, response-header
sink, credentials, wildcard, literal `null` origin, request-Origin reflection,
permissive allowlist/control, and `Vary: Origin` context for displayed leads.
`--show-control-order` prints same-file static line-order context between
control-like refs and sensitive sinks, including sink refs, control refs, and
line deltas.
`--show-control-effect` prints same-file static guard result, denial response,
floating call, and sink-order context for displayed leads.
`--show-response-exposure` prints static JSON response sinks, nearby
sensitive-looking refs, response/sensitive pair distances, route access context,
identity-binding context, and CORS/config context for displayed leads.
`--show-download-response-trust` prints static download response sinks,
`Content-Disposition` filename material, content-type context, CSV/spreadsheet
export builders, caller-controlled filename/content sources, filename controls,
extension or MIME allowlists, attachment policy, and spreadsheet formula
escaping context for displayed leads.
`--show-cache-policy` prints static Cache-Control, Next.js cache directive,
route-config header, sensitive-response, and private/no-store/public cache
context for displayed leads.
`--show-path-trust` prints static filesystem/storage path sink refs,
caller-controlled path or object-key source refs, normalization, base-directory
containment, traversal/absolute-path controls, extension allowlists, object-key
prefix controls, and source/sink/control pair categories for displayed leads.
`--show-upload-trust` prints static upload source refs, filesystem/storage
persistence sink refs, MIME/content-type and extension controls, size limits,
private ACL or signed access controls, ownership-key controls, public-serving
hints, and source/sink/control pair categories for displayed leads.
`--show-auth-token-trust` prints static bearer, cookie, URL/query, API-key,
JWT, signature, and session-token source refs, decode and comparison sink refs,
verification helpers, unsafe verification-option hints such as disabled expiry
checks or allowed `none` algorithms, issuer/audience/algorithm/expiry claim
controls, hardcoded verification-secret review pairs, query-token review pairs,
missing-claim-control review pairs,
constant-time comparison controls, and source/sink/control pair categories for
displayed leads.
`--show-auth-flow-trust` prints static OAuth/OIDC/SAML/SSO callback source
refs, token exchange, callback/session creation, cookie, redirect, and assertion
sink refs, state/nonce/PKCE controls, missing PKCE/code_verifier review pairs,
provider allowlist or expected-provider binding controls, redirect allowlist or
same-origin controls,
issuer/audience/JWKS/signature controls, and source/sink/control pair categories
for displayed leads.
`--show-account-recovery-trust` prints static reset, magic-link, invite,
OTP/MFA, verification-code, recovery-code, password, session, expiry,
single-use/revocation, token-hash/safe-compare, account/email/user binding,
attempt-limit, rate-limit, lockout, URL/query token transport, missing
re-auth/current-password review pairs, and missing token-hash review context for
displayed leads.
`--show-role-permission-trust` prints static role, permission, admin flag,
invite, membership, target-subject, admin-policy, role-allowlist,
self-assignment gap, missing grantable-role allowlist review pairs,
self-protection, and tenant or organization scope context for displayed leads.
`--show-cookie-trust` prints static cookie write sinks, inferred cookie-name
sensitivity, `HttpOnly`, `Secure`, `SameSite`, lifetime, path, domain, and
prefix controls, including prefix-scope gaps, sensitive `Domain` scope review,
long static `Max-Age` lifetime review, and `SameSite=None` without `Secure`,
plus source/sink/control pair categories for displayed leads.
`--show-message-trust` prints static browser message handlers, `postMessage`
senders, target-origin categories, dynamic target-origin review pairs,
`event.origin`/`event.source` controls, message schema controls, channels, and
source/sink/control pair categories for displayed leads.
`--show-client-rendering-trust` prints static raw HTML/DOM/markdown/parser
sink refs, props/URL/storage/API/CMS/content source refs, sanitizer/output
encoding/Trusted Types controls, static-literal context, and source/sink/control
pair categories for displayed leads.
`--show-security-header-trust` prints static checked-in CSP,
`Content-Security-Policy-Report-Only`, `X-Frame-Options`, HSTS,
`X-Content-Type-Options`, referrer policy, permissions policy, and cross-origin
isolation header context from same-file header construction and matched Next.js
route header policies. It highlights weak configured values such as
`unsafe-inline`, `unsafe-eval`, wildcard CSP sources, report-only CSP used
without an enforcing CSP on rendering-risk pages, enforcing CSP policies that
omit `base-uri` or `object-src` hardening on rendering-risk pages, weak frame
policies, short HSTS max-age, non-`nosniff` `X-Content-Type-Options`,
`unsafe-url` referrer policy, broad COOP/CORP/COEP isolation values such as
`unsafe-none` or `cross-origin`, and permissions policy wildcards for sensitive
browser features such as camera, microphone, geolocation, payment, USB, serial,
Bluetooth, display-capture, and clipboard access. Statuses such as
`security-header-weak-csp-review`,
`security-header-csp-report-only-review`,
`security-header-frame-policy-gap-review`,
`security-header-csp-hardening-gap-review`,
`security-header-hsts-weak-review`,
`security-header-permissions-policy-wildcard-review`,
`security-header-referrer-policy-leak-review`,
`security-header-xcto-weak-review`,
`security-header-cross-origin-isolation-weak-review`,
`security-header-weak-browser-policy-review`, and
`security-header-controlled-context-indexed` help queue static review. It only
raises missing CSP/frame-policy, report-only CSP, or CSP hardening-gap review
when correlated with a local rendering-risk page or route. It does not fetch
runtime headers, run a browser, execute payloads, or prove exploitability.
`--show-client-storage-trust` prints static localStorage, sessionStorage,
IndexedDB, client cookie, localForage/idb-keyval-style helper, storage
persistence helper, storage-key sensitivity, read/write, expiry, validation,
redaction, encryption-hint, and sensitive-write lifecycle-gap context for
displayed leads.
`--show-randomness-trust` prints static weak, time-derived, and cryptographic
randomness refs, token/session/nonce/OTP/reset/invite material categories,
lifetime/uniqueness controls, and source/material/control pair categories for
displayed leads.
`--show-crypto-primitive-trust` prints static caller-controlled algorithm,
hash, cipher, key, IV/nonce, signature, MAC, plaintext, and ciphertext refs,
weak algorithm/static IV hints, deprecated `createCipher`/`createDecipher`
hints, unauthenticated cipher mode hints, hardcoded key, secret, or passphrase
hints with literal samples redacted, primitive sink refs, AEAD, HMAC/MAC/auth
tag, random IV/nonce, KDF, key-management, allowlist, constant-time compare
controls, and source/sink/control pair categories for displayed leads. It is a
static source view only and does not print raw secrets, validate keys, decrypt
data, brute-force material, invoke routes, or replay requests.
`--show-business-value-trust` prints static caller-controlled amount, price,
total, quantity, discount, coupon, currency, balance, credit, point, and fee
refs, payment/order/ledger/balance/entitlement sink refs, server-side
pricing/catalog controls, numeric and currency limits, and source/sink/control
pair categories for displayed leads.
`--show-tenant-scope-trust` prints static caller-controlled user, owner,
tenant, account, organization, project, order, invoice, document, file, wallet,
and object id source refs, data-access/mutation/response sink refs,
client-supplied tenant/account/user scope review pairs,
ownership/tenant/membership/auth/imported policy controls, and
source/sink/control pair categories for displayed leads.
`--show-workflow-precondition-trust` prints static workflow action, object id,
amount, coupon, role, account, password, status, and state source refs,
order/payment/refund/coupon/balance/role/account/workflow mutation sinks,
auth/ownership/state-machine/idempotency/transaction controls, and
source/sink/control pair categories for displayed leads.
`--show-resource-fanout-trust` prints static caller-controlled ids/items,
batch, limit, page-size, cursor, offset, retry, polling, parallel fanout,
pagination/export sink, bound, rate-limit, and concurrency-control context for
displayed leads.
`--show-sensitive-logging-trust` prints static console/logger/telemetry/
analytics/error-reporting sink refs, sensitive auth/cookie/API-key/JWT/session/
secret/wallet/payment/request/header/body/PII source refs, redaction or
scrubbing controls, and sink/source/control pair categories for displayed leads.
`--show-error-disclosure-trust` prints static raw exception, stack, debug,
upstream/provider/RPC diagnostic, response-body, status-text, JSON/HTTP error
response sink, and public-error shaping/redaction context for displayed leads.
`--show-debug-surface-trust` prints static debug, admin, internal, ops,
diagnostic, cron, seed, backfill, maintenance, devtools, diagnostic response,
internal action, access-control, internal-only header, and environment-gate
context for displayed leads.
`--show-code-exec-trust` prints static process execution, shell execution, eval,
Function, vm, caller-source, allowlist, argv-separation, shell-disabled,
admin/internal, environment-gate, and source/sink/control pair context for
displayed leads.
`--show-server-template-trust` prints static server-side template name/string
source refs, render/view/compile sink refs, render data refs, template
allowlists, escaping, sandbox, literal-template, unescaped-output, and
source/sink/control pair context for displayed leads.
`--show-deserialization-trust` prints static serialized payload source refs,
unserialize/deserialize/YAML/binary parser sink refs, schema or type allowlist
controls, safe-loader settings, signature/MAC checks, content-type and size
controls, and source/sink/control pair context for displayed leads.
`--show-archive-extraction-trust` prints static archive upload/source refs,
unzip/tar/decompress/parser sink refs, archive entry path write refs,
destination containment, preserve-paths/strip-zero option refs, strip/filter
settings, allowlists, size/count controls, and source/sink/control pair context
for displayed leads.
`--show-xml-parser-trust` prints static XML/SOAP/SAML/SVG source refs, XML
parser sink refs, DOCTYPE/entity refs, external-resource or entity-processing
settings, schema/content-type/size controls, and source/sink/control pair
context for displayed leads.
`--show-regex-complexity-trust` prints static dynamic `RegExp`/`RE2`, regex
literal, caller-controlled pattern/input, complex regex, `RE2`/safe-regex,
allowlist, escaping, and length-bound context for displayed leads.
`--show-query-trust` prints static database/ORM query sink refs,
caller-controlled query/filter/sort/where source refs, parameterization
controls, client-controlled ORM filter review context, field allowlists,
ownership/tenant scope controls, and source/sink/control pair categories for
displayed leads.
`--show-graphql-resolver-trust` prints static GraphQL resolver entrypoint,
Query/Mutation, args/input, object selector, context auth, caller-to-object
scope, validation, unbounded list review, pagination/depth/complexity, and
data/mutation sink context for displayed leads.
`--show-ssrf-trust` prints static outbound request sink refs, caller-controlled
URL source refs, URL parser refs, host allowlist controls, protocol controls,
private-network controls, permissive host allowlist review pairs, fixed
private/metadata upstream URL categories, and source/sink/control pair
categories for displayed leads. It is a static source view only and does not
request those URLs, resolve DNS, follow redirects, or probe private networks.
`--show-redirect-trust` prints static redirect/navigation sink refs,
redirect-like source refs, same-origin/path controls, allowlist controls,
dynamic missing-allowlist review pairs, dangerous-scheme literal destinations,
Next.js redirect route-policy context, and source/sink/control pair categories
for displayed leads.
`--show-webhook-trust` prints static webhook entrypoint refs, signature header
reads, raw/parsed body reads, verification refs, secret refs, event-id refs,
idempotency refs, replay-window or timestamp-freshness refs, side-effect refs,
missing-secret context, and signature/body/control-order/idempotency/replay-window
categories for displayed leads. It is a static source view only and does not
deliver or replay webhook events, call routes, or forge provider signatures.
`--show-identity-binding` prints static object/subject identifiers, same-file
binding refs, imported or middleware contextual-control refs, ownership-control
counts, and mutation-like context for displayed leads.
`--show-client-exposure` prints static client reachability, client importer or
transitive chain hints, and client-reachable private env, server-only runtime,
database/storage, wallet, and transaction-boundary refs for displayed leads.
`--show-route-guards` prints matched middleware, static matcher status, and
route-bound control refs for displayed route leads. It also prints importer
route guard summaries for route-reachable helper or library leads.
`--show-flow` prints the static source/sink links, nearest source and sink refs,
line distance, and review question for displayed leads.
`--show-config-context` prints static env/upstream/Next.js config context,
including env variable names, URL categories, direct imported config refs, and
matched route policies for displayed leads.
`--show-packet` prints a compact offline review packet per displayed lead. The
packet combines source refs, surface metadata, context statuses, top triage
reasons, source/sink links, config refs, importer/reachability refs, offline
checks, evidence requests, promotion gates, reportability gates, and stop
conditions. Packets are designed for manual source review and do not authorize
active validation.
`--show-triage` prints the combined triage status, score, reason ids, weights,
and safe review hints for displayed leads.
`--focus` applies display-only presets without changing `source-risk-review.json`.
Available presets include `wallet`, `mutation`, `route-guard-gap`, `flow`,
`config`, `public-env`, `imported-controls`, `imported-invocation`,
`external-deps`, `input-shape`, `object-key-trust`, `csrf-origin`,
`cors-origin-trust`, `control-order`, `control-effect`,
`response-exposure`, `download-response-trust`, `cache-policy`, `path-trust`, `upload-trust`,
`auth-token-trust`, `auth-flow-trust`, `account-recovery-trust`,
`role-permission-trust`, `cookie-trust`, `message-trust`, `client-rendering-trust`, `security-header-trust`, `client-storage-trust`,
`randomness-trust`, `crypto-primitive-trust`, `business-value-trust`, `tenant-scope-trust`, `workflow-precondition-trust`,
`resource-fanout-trust`,
`sensitive-logging-trust`, `error-disclosure-trust`, `debug-surface-trust`,
`code-exec-trust`, `server-template-trust`, `deserialization-trust`,
`archive-extraction-trust`, `xml-parser-trust`, `regex-complexity-trust`, `query-trust`,
`graphql-resolver-trust`, `ssrf-trust`, `redirect-trust`, `webhook-trust`,
`identity`, `client-exposure`, `coverage`, `client`, and `route`.
Display-only filters include `--priority`, `--signal`, `--lane`, `--surface`,
`--control-status`, `--imported-control-status`,
`--imported-invocation-status`, `--imported-invocation-category`,
`--external-dep-status`, `--external-dep-category`, `--route-guard-status`,
`--route-importer-guard-status`,
`--input-shape-status`, `--input-shape-category`,
`--object-key-trust-status`, `--object-key-trust-category`,
`--csrf-origin-status`,
`--csrf-origin-category`, `--cors-origin-trust-status`,
`--cors-origin-trust-category`, `--control-order-status`, `--control-order-category`,
`--control-effect-status`, `--control-effect-category`,
`--response-exposure-status`,
`--response-exposure-category`, `--download-response-trust-status`,
`--download-response-trust-category`, `--cache-policy-status`,
`--cache-policy-category`, `--path-trust-status`, `--path-trust-category`,
`--upload-trust-status`, `--upload-trust-category`,
`--auth-token-trust-status`, `--auth-token-trust-category`,
`--auth-flow-trust-status`, `--auth-flow-trust-category`,
`--account-recovery-trust-status`, `--account-recovery-trust-category`,
`--role-permission-trust-status`, `--role-permission-trust-category`,
`--cookie-trust-status`, `--cookie-trust-category`,
`--message-trust-status`, `--message-trust-category`,
`--client-rendering-trust-status`, `--client-rendering-trust-category`,
`--security-header-trust-status`, `--security-header-trust-category`,
`--client-storage-trust-status`, `--client-storage-trust-category`,
`--randomness-trust-status`, `--randomness-trust-category`,
`--crypto-primitive-trust-status`, `--crypto-primitive-trust-category`,
`--business-value-trust-status`, `--business-value-trust-category`,
`--tenant-scope-trust-status`, `--tenant-scope-trust-category`,
`--workflow-precondition-trust-status`,
`--workflow-precondition-trust-category`,
`--resource-fanout-trust-status`, `--resource-fanout-trust-category`,
`--sensitive-logging-trust-status`, `--sensitive-logging-trust-category`,
`--error-disclosure-trust-status`, `--error-disclosure-trust-category`,
`--debug-surface-trust-status`, `--debug-surface-trust-category`,
`--code-exec-trust-status`, `--code-exec-trust-category`,
`--server-template-trust-status`, `--server-template-trust-category`,
`--deserialization-trust-status`, `--deserialization-trust-category`,
`--archive-extraction-trust-status`,
`--archive-extraction-trust-category`,
`--xml-parser-trust-status`, `--xml-parser-trust-category`,
`--regex-complexity-trust-status`, `--regex-complexity-trust-category`,
`--query-trust-status`, `--query-trust-category`,
`--graphql-resolver-trust-status`, `--graphql-resolver-trust-category`,
`--ssrf-trust-status`,
`--ssrf-trust-category`, `--redirect-trust-status`,
`--redirect-trust-category`, `--webhook-trust-status`,
`--webhook-trust-category`, `--identity-binding-status`,
`--identity-binding-category`, `--client-exposure-status`,
`--client-exposure-category`, `--flow-status`, `--flow-link`,
`--config-status`, `--config-signal`, `--triage-status`, `--triage-reason`,
`--dependency-status`, `--route`, and `--source-file`; they do not remove leads from
`source-risk-review.json`. The command sends no HTTP requests, does not call
Burp, does not sign wallets, does not submit transactions, does not retrieve
production logs, does not collect tokens/cookies/PII, does not query or
exfiltrate telemetry, does not trigger live errors, does not replay requests,
does not execute GraphQL operations, does not introspect live schemas, does not
fuzz GraphQL fields, does not switch accounts, does not send malformed traffic,
does not collect raw upstream bodies, does not construct prototype-mutation
payloads, does not fuzz keys, does not execute merge behavior, does not parse
XML samples, does not construct XXE or entity payloads, does not fetch external
entities, does not read local files from XML parser leads, does not generate
ReDoS payloads, does not run regex benchmarks, does not fuzz regex patterns or
inputs, does not stress-test regex matching, does not request debug
endpoints, trigger jobs/backfills/seeds/cache purges/admin actions, read
production diagnostics, run browser CORS checks, send cross-origin probes,
collect/replay credentials, generate XSS payloads, invoke login or callback
routes, generate or replay OAuth/OIDC/SAML tokens or assertions, submit SSO
forms, replay authorization codes, generate, guess,
brute-force, submit, replay, or validate account-recovery tokens, magic links,
invite codes, OTPs, MFA codes, recovery codes, passwords, or sessions, run
browser page validation, create users, send invites, change roles, grant
permissions, replay membership flows, validate live privilege changes, replay
rendered content, or attempt cache poisoning.

`lead-portfolio` consumes `bounty-program-profile.json` when it is present and
creates `bounty-program-impact` lanes ahead of passive endpoint leads. It also
consumes `source-risk-review.json` when available, so high-value local source
boundaries appear in the same queue as scope, endpoint, WebSocket, and takeover
leads, with route/method/surface summaries when they can be inferred offline.
Source-risk portfolio rows also include the control-context bucket so reviewers
can prioritize unauthenticated-looking mutation boundaries without treating
source heuristics as proof. Dependency buckets show whether a source-only lead is
an entrypoint, imported by a route, imported by client code, or currently
unreferenced in the local import graph; compact reachability counts show whether
route or client chains were found. Config buckets show whether a lead has
public-secret-like env names, upstream/RPC/quote config, CORS route-policy
context, or only lower-signal env/url references. External dependency buckets
show whether a source-risk lead imports wallet/web3, rendering/parser,
validation/auth, storage/database, HTTP/upstream, or generic packages directly
or through a direct local helper. Path-trust buckets show whether a source-risk
lead has caller-controlled file path or object-key material, containment or
traversal controls, extension allowlists, object-key prefix controls, or only
literal path context. Upload-trust buckets show whether a source-risk lead has
caller-controlled upload content, public-serving persistence sinks, missing
MIME/type or size controls, private ACL or ownership-key context, or only
literal upload/write context. Auth-token-trust buckets show whether a
source-risk lead has decode-only token handling, unsafe API-key or signature
comparison, verified JWT/session context, issuer/audience/expiry claim controls,
URL/query token transport, missing claim-control review pairs, or token
source-only context. XML-parser-trust buckets show whether a
source-risk lead has caller-controlled XML/SOAP/SAML/SVG material near parser
sinks, DOCTYPE/entity material, same-file parser controls, or only literal XML
context. Regex-complexity-trust buckets show whether a source-risk lead has
caller-controlled regex patterns, complex regexes over caller-controlled input,
same-file RE2/safe-regex/length controls, or only literal regex context.
Query-trust buckets show whether a source-risk lead has
raw user-influenced database query material, parameterized query context,
field/sort allowlists, scoped ORM ownership or tenant controls, or only literal
query context.
Bounty lanes preserve the original program impact, severity, candidate
in-scope assets, mapped attack techniques, safe validation boundary, and
reportability gates. In black-box mode, if the bounty profile is missing,
`lead-portfolio` emits a `bounty-program-profile-missing` blocker so the run
starts by ingesting program scope instead of spending effort on coverage-first
endpoint work.
`scope-policy` also consumes `bounty-program-profile.json`: asset hosts parsed
from the bounty page are automatically added to the explicit allowlist, and if
no target was supplied the first bounty asset is used as the policy target
instead of the local default target.

Use `lead-portfolio` to turn the passive black-box leads into one prioritized
local artifact before deciding what to validate next:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  lead-portfolio
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  lead-portfolio --no-write
python3 scripts/inferforge.py --artifact-dir .greybox/target-set \
  lead-portfolio --discover-child-runs --no-write
```

`lead-portfolio` reads existing local artifacts only. It combines bounty impact
lanes, source-risk leads, static asset endpoint candidates, WebSocket handshake
candidates, runtime configuration hosts, external script hosts, scope-policy
decisions, generated asset profiles, handshake review results, and takeover
baselines. The output is a triage queue, not evidence of impact: every entry
keeps a reportability gate and a safe next step, and no endpoint, host, source
file, or script is requested by this command. Use
`--check-dir` repeatedly or `--discover-child-runs` to build a root-level rollup
across multiple child runs that already contain `lead-portfolio.json`; this is
also offline and prints per-run status counts plus the top actionable leads.

When `blackbox-asset-map` receives a non-success page response such as 403 or
429, it now writes `page-fetch-non-success` instead of pretending there were no
endpoints. The safe next step is to use `--input-html` with a browser-exported
page or retry later; do not broaden automated fetching after a rate-limit or
block page.

Use `harness-loop` as the high-level autonomous loop dashboard. It maps the
current artifacts into discovery/recon, lead generation, finding identification,
issue validation, and PoC/reporting stages, then prints the safest next steps:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  harness-loop --no-write --skip-current-resource-check
python3 scripts/inferforge.py --artifact-dir .greybox/target-set \
  harness-loop --discover-child-runs --no-write --skip-current-resource-check
```

`harness-loop` is also read-only. It is intended for low-memory unattended runs:
use it after `resource-snapshot --strict` to decide whether to deepen an
existing lead, regenerate passive leads, refresh adjudication, or stop because
there is no reportable evidence yet. If the finding gate only has
`blocked_gate_previews`, the issue-validation stage reports `gate-blockers` and
checks the current `bounty-action-queue` `next_evidence_packet` before selecting
focus commands. When the top packet is still `waiting-official-evidence`, the
focus switches to `official-evidence-first`: ready commands refresh the action
queue, evidence request brief, and evidence intake, while after-evidence lane
validators stay in `gated_followup_commands` until the required sidecars pass
intake. Those previews are the nearest evidence blockers, not reportable
findings. `--top` is accepted as an alias for `--top-steps`.

Use `methodology-review` to align the harness with business-logic testing
methodology before broadening. It maps high-value threads to offline-safe
business logic dimensions such as data validation, request forgery, integrity
checks, workflow circumvention, and misuse/function-use limits. It also prints
an evidence-closure view for each Medium/High/Critical candidate thread, showing
which artifact or sidecar still blocks finding-gate review:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  methodology-review --no-write --show-commands --show-poc-plan --skip-current-resource-check
```

The business-logic map is still a prioritization aid, not a finding. A
Medium/High/Critical claim still requires endpoint-specific evidence proving a
data validation failure, forged request impact, transaction/upstream integrity
mismatch, workflow bypass, or quota/provider/resource misuse. The closure view
is conservative: transaction-integrity, fixed-upstream, RPC-proxy, and
unauthorized-state-change threads get lead-level evidence contracts but still
need decoded corpus/intent review, one approved read-only/RPC observation, or
protected-action impact evidence. Credentialed-upstream threads need redacted
provider/operator impact evidence, and resource-exhaustion threads need
deployment/proxy trust evidence plus non-stress availability impact evidence.
Specialized quote, Solana RPC, and fixed-upstream clusters do not also get a
generic `unauthorized-state-change` lead merely because the route uses `POST`;
that impact stays reserved for routes without a more precise boundary model.
`--show-poc-plan` expands each high-value thread into a minimal reproduction
evidence package: required sidecars or operator inputs, missing evidence,
offline no-write commands, gate entry conditions, and forbidden actions. It is a
planning view only, not an exploit script or approval to run active traffic.
For transaction-integrity packages, the prep view carries the approved quote
operator-input handoff and staging contract as well: target operator-input
directory, present/missing file counts, preflight gate, byte caps, scan limits,
and the same `do_not_stage` rules used by the shorter quote-specific views.
With `--skip-current-resource-check`, `methodology-review` stays fully offline
and reports resource status as `not-run` instead of reading current `/proc`
resource state.
It also builds an in-memory claim witness ladder so the same review shows
whether each atomic claim has a contract, official approved evidence sidecars,
offline verifier commands, and a finding-gate/adjudication path. A witness
ladder is proof-work bookkeeping only: it does not create evidence sidecars and
does not make a finding reportable.
Witness ladder stage commands also carry command-safety labels and autorunnable
lists. Missing upstream evidence keeps verifier and finding-gate commands
classified as `review-gated`, with no autorunnable commands exposed until the
official sidecars pass the local gates.

`bounty-evidence-workorders` turns blocked bounty lanes into bounded official
evidence requests. Its summary and CLI include the top workorder's required
evidence count, preview command count, after-evidence validation count, and
command-safety totals. This lets unattended loops verify that workorders are
still waiting on approved evidence while the post-evidence commands remain
classified as safe no-write validators gated behind evidence arrival.

`bounty-action-queue` consumes the same claim evidence request pack and attaches
matching witness requests to each queued bounty action. The queue shows the
missing official evidence file, claim count, draft-assist path, first offline
verifier command, and whether a shared evidence request is bound to more than
one action. Shared `operator-evidence.json` requests are matched by lane/oracle
type instead of filename alone, so provider/resource/websocket requests do not
accidentally unblock build-secret evidence gates.
`bounty-evidence-intake` is the offline file gate before those queued actions
can move to lane validation. It checks requested evidence presence, format,
approval/template markers, redaction risk, and operator-evidence lane scope.
For transaction-integrity requests, it also treats `transaction-payloads.jsonl`
and `transaction-intent-policy.json` as a required pair: the payload sidecar
must yield a bounded transaction candidate, the intent policy must be valid, and
`transaction-sidecar-review` must be ready for offline decode before the request
is marked ready for lane validation.
When intake does mark a request ready, `bounty-action-queue` keeps the action
agent-offline and attaches an ordered `validation_commands` chain. For
transaction-integrity this runs transaction evidence readiness, offline decode,
finding gate, and adjudication in order; the chain is workflow control only and
does not make the evidence reportable by itself. Intake rows also carry
`after_evidence_validation_gate`,
`after_evidence_validation_command_safety`, and
`autorunnable_after_evidence_validation_commands`: missing or blocked evidence
keeps after-evidence validators `review-gated`, while only
`ready-for-lane-validation` rows can expose autorunnable no-write validators.
`bounty-readiness-rollup` applies the same guard one layer upstream: each lane
row records `validation_execution_gate`, `validation_command_safety`, and
`autorunnable_validation_commands`. Rows still missing official evidence, lane
readiness, or reportability closure keep validation chains such as decode,
finding gate, and adjudication classified as `review-gated`; only rows that
clear official evidence, readiness, invalidity, and safe no-write command checks
can expose autorunnable validation commands.
Each queued action and the
queue summary also record command-safety totals for that validation chain, so an
agent can distinguish runnable no-write validators from manual templates,
external probes, resource-gated commands, or unsafe shell templates before any
automatic execution. `validation_execution_gate` is the final automation guard:
only actions with `ready-offline-validation` expose
`autorunnable_validation_commands`; actions waiting for official evidence,
manual input, external probes, or unsafe templates classify their validation
commands as gated workflow items and are not presented as agent-runnable
validation chains.
With `--show-actions --show-commands`, each printed action command includes its
command-safety classification so blocked validation previews are visible as
`review-gated` rather than bare shell commands.
Each action also carries a `harness_phase` model. This records the current
finder/evidence/intake/triager/adjudication phase, the phase gate blocking
promotion, and whether agent autorun is allowed. Source-positive leads stay in
the finder or official-evidence phase with
`triager-blocked-waiting-official-evidence`; only approved evidence that passes
intake can move to `ready-offline-triager-validation`, and even then Medium+
promotion remains blocked until finding-gate and adjudication accept the
impact. The queue summary and `next_evidence_packet` repeat these phase gates so
unattended loops do not mix lead generation with validation.
The queue also emits `next_evidence_packet`, a compact view of the current
highest-value action's minimum official evidence set, first missing artifact,
claim-witness request, manual handoff/preflight commands, and after-evidence
validation chain. It is an offline handoff summary only: it does not create
sidecars, authorize traffic, or make a candidate reportable.
The same packet and human brief also carry a reviewer invalidity preflight:
source-only context, missing official evidence, unproven pair binding, unchecked
negative controls, blocked offline validation, and missing finding-gate
acceptance are listed as explicit report blockers before any bounty report can
be treated as valid.
`bounty-invalidity-review --show-reasons` mirrors that same packet-level
reviewer preflight into its top invalidity row and summary, so action queue,
human brief, readiness rollup, and invalidity review all explain the same
report-blocking reasons instead of producing separate blocker lists.
Packet handoff commands also carry `handoff_command_refs`, so the same
`manual-template`/`review-gated` classification shown in
`bounty-action-queue --show-actions --show-commands` is available to automation
without inferring command safety from shell text.
When all bounty-valid report paths are waiting on official evidence, the queue
also exposes an offline continuation section. Its local no-write continuation
commands carry `command_refs` and render as `offline_continue=[ready] ...`, so
automation can keep broadening greybox/source coverage while leaving evidence
handoff and reportability gates blocked.
Each packet includes `official_evidence_contracts` for the required sidecars:
artifact name/path, category, format, required fields, reject conditions, paired
evidence dependencies, and no-write validator commands. These contracts are
acceptance criteria for approved evidence handoff; they are not evidence and do
not bypass `bounty-evidence-intake`, finding-gate, or adjudication.
`bounty-evidence-request` brief renders the same handoff for a human/operator
and, when source invariants are available, includes a source-invariant boundary:
the source signal, what the source path proves, negative controls, whether it is
promotable without official evidence, and the official sidecars still required.
It also renders the packet evidence intake manifest: artifact counts, artifact
formats, pair-binding fields, copy policy, and reject rules are visible in the
human handoff brief as well as in `bounty-shortest-path`.
The brief summary and CLI now expose the same top intake manifest counts, so
automation can verify artifact coverage and pair-binding requirements without
parsing Markdown.
The same brief also renders a compact handoff/unblocker summary: whether the
agent can keep working offline, whether a human/operator evidence bundle is
required for Medium+ promotion, the first missing official artifact, and the
current promotion gate. This is status routing only; it does not create evidence
or bypass intake, finding-gate, or adjudication.
This keeps source-positive leads useful for targeting evidence while preventing
them from being treated as bounty-valid findings. The brief also carries a
machine-readable `brief_quality_gate` that checks active requests, required and
missing evidence names, source-boundary rendering, non-promotion while official
evidence is absent, redaction/reportability text, no-write validation commands,
command-safety labels next to InferForge bash blocks, and
placeholder/template boundaries. `--strict` fails if this quality gate is not
passed.
`adjudicate` links that same queue/brief context as `next_evidence_unblocker`,
so a no-finding run can distinguish `waiting-official-evidence` from
`blocked-brief-quality` without promoting the candidate. The unblocker also
carries the evidence intake manifest summary and the harness active phase/phase
gate, such as `official-evidence` and
`triager-blocked-waiting-official-evidence`, so downstream automation can see
which artifacts and pair-binding gates are missing and why the triager is
stopped.
`iteration-decision` prints that unblocker next to the active assessment
objective, including the harness phase and phase gate, and labels
`assessment-mode-split` when the greybox coverage focus and bounty/adjudication
unblocker point at different lanes.
It also emits `assessment_mode_evidence_ledger`, a two-track accounting view for
the active assessment objective and the bounty/adjudication reportability path.
The ledger names each track's lane, first missing official artifact, autorun
eligibility, and reportability gate, so offline loops can close greybox coverage
without mistaking it for a valid Medium+ bounty report.
`methodology-review` carries the same phase and phase-gate fields in its
assessment-mode split and first-gap evidence packet views.
Each contract also has a `validator_execution_gate`, so missing sidecars remain
`waiting-official-evidence` even when their no-write validator commands are
safe to preview. Contract JSON keeps both `validator_command_safety` for the
intrinsic no-write command and `validator_gated_command_safety` for the current
evidence gate; `autorunnable_validator_commands` stays empty until that contract
is `ready-no-write-contract-validation`. The packet-level
`official_evidence_contract_gate` aggregates those contracts and only exposes
`autorunnable_contract_validator_commands` when every required sidecar contract
is ready for no-write validation. Use
`bounty-action-queue --show-contracts --show-intake-manifest` to print the
packet's required fields, reject conditions, paired sidecars, intake artifact
counts, pair-binding fields, and copy policy without opening the JSON.

Use `bounty-shortest-path` when the loop needs the shortest current path to one
valid Medium/High/Critical bounty report instead of a broad coverage queue:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  bounty-shortest-path --no-write --show-contract --show-intake-manifest --show-commands --top 4
```

This command is still an offline workflow-control view. With
`--show-intake-manifest`, each closure action expands the evidence intake
manifest into artifact counts, artifact formats, required pair-binding fields,
copy policy, and reject rules. That makes the next handoff explicit without
copying drafts, creating official sidecars, authorizing traffic, or promoting a
lead past finding-gate/adjudication.
When the lane has a known no-write validation chain, the shortest-path view can
print it before evidence exists as `after_ready_mode=blocked-preview`. Those
preview commands document the exact post-evidence chain, but they remain
`review-gated`, `after_ready_autorun=false`, and blocked on the official
evidence bundle until every required contract is
`ready-no-write-contract-validation`.
The bundle plan keeps both views in JSON: `after_ready_validation_command_safety`
describes the intrinsic no-write commands, while
`after_ready_validation_gated_command_safety` and
`autorunnable_after_ready_validation_commands` reflect the current evidence gate.
Stage commands printed by `bounty-shortest-path --show-stages --show-commands`
carry the same command-safety classifications. Commands in blocked stages remain
`review-gated` or `manual-template`, and only stages whose local no-write
commands all classify as ready expose `autorunnable_commands`.
The top-level `Handoff commands`, `Verify commands`, and `After-ready commands`
sections also print command-safety summaries and per-command labels, so
placeholder handoff templates show as `manual-template` and missing-evidence
verifiers show as `review-gated` instead of bare runnable-looking shell lines.
The same shortest-path artifact now embeds `platform_submission_gate`, a final
offline quality gate for bounty-platform submission readiness. It keeps
`submit_allowed=false` until official evidence is complete and bound, a safe
no-write/offline PoC exists, finding-gate and adjudication both accept a concrete
valid finding, invalidity review is clear, severity is supported by impact, and
the package has redaction/secret hygiene. The CLI prints
`Platform submission: status=... allowed=... first=...`; with
`--show-requests` it also lists the first platform blockers. This is workflow
control only: it does not create evidence, authorize traffic, sign wallets,
submit transactions, or turn a draft/AI-generated allegation into a report.
`bounty-lane-priorities --show-lanes --show-commands` prints the current
lane-level workflow ranking before the frontier/action queue layers. Each row
now includes a `scorecard` and `blackbox_value` block that separates expected
payout weight, source strength, evidence distance, validity-gap penalties, value
tier, and the blackbox completion unit. High/Critical candidates are tagged as
`one-valid-high-impact-finding`, while Medium rows are explicitly secondary when
a stronger valid bounty path is still open. `--show-priorities` is accepted as a
compatibility alias for `--show-lanes`.
`bounty-frontier --show-frontiers --show-commands` prints the same verifier
command labels at the frontier ranking layer: blocked missing-evidence rows keep
their verifier commands `review-gated`, while ready evidence-verification rows
can expose runnable no-write verifiers. This is still workflow control only and
does not create evidence sidecars or bypass finding-gate/adjudication.
`bounty-validation-gates --show-gates --show-commands` mirrors those labels at
the Medium+ validation-gate layer so blocked gates do not expose their verifier
commands as autorunnable.
Both artifacts also carry the same command-safety data in JSON:
`verification_command_refs` / `verification_command_safety` on frontier rows and
`validation_command_refs` / `validation_command_safety` on gate rows, plus empty
`autorunnable_*_commands` lists while official evidence is still missing.

`claim-evidence-ledger` decomposes each claim into required evidence artifacts
and verifier commands. Ledger rows now carry `verification_command_refs`,
`verification_command_safety`, and `autorunnable_verification_commands`; missing
or invalid official evidence keeps verifier commands `review-gated`, while only
ready claim evidence can expose autorunnable no-write verifiers.

`claim-evidence-requests` also uses that queue context for its default ordering:
in bounty mode, evidence for the highest-ranked action comes before a broader
coverage request that merely unblocks more lower-value claims. Each request now
includes source-readiness metadata from local candidate/review artifacts, such as
whether a transaction payload candidate exists locally, whether an intent policy
template is ready, whether a single-observation plan exists, and whether official
approved evidence is still required. For transaction payload requests, the same
source-readiness block carries a compact handoff contract from
`transaction-corpus-checklist`: recommended quote method/path/direction, target
sidecars, required redacted fields, blocked approval steps, and offline verifier
commands. It also prints the offline `transaction-payload-preflight` and
`transaction-corpus-preflight` commands for checking one approved local payload,
or one approved quote request plus its matching response and intent document,
before any official sidecar is created. The contract and preflight result are
still not evidence and do not authorize traffic.
Each request also carries `handoff_command_refs`,
`verification_command_refs`, and after-ready validation refs with command-safety
summaries. `claim-evidence-requests --show-requests` prints those labels so
placeholder handoff commands show as `manual-template` and missing-evidence
verifiers remain `review-gated` instead of appearing as runnable shell snippets.
`bounty-evidence-templates` renders three transaction-integrity templates for
that handoff: `transaction-payloads.jsonl`, `transaction-intent-policy.json`,
and an `approved-quote-intent.draft.json` operator-input template for
`--intent-input`. The approved quote intent template is not an official evidence
sidecar; it exists to bind the reviewer-approved wallet, mints, raw amount,
optional minimum destination amount, chain, direction, payload type, approval
reference, and `maxNumQuotes` before
`prepare-transaction-corpus-sidecars` writes official sidecars.
`evidence-sidecar-drafts` carries the same transaction pair binding metadata in
its non-evidence draft workbook: `approval_reference`, `request_text_sha256`,
`payload_text_sha256`, and `paired_payload_text_sha256`. When transaction
payload/policy sidecars are required, the workbook also includes
`approved-quote-intent.draft.json` as supporting operator input for
`--intent-input`; it is not an official evidence sidecar and cannot satisfy the
finding gate by itself. The draft CLI prints the required binding fields with
`--show-drafts` and now includes an operator-input handoff pointing at
`.greybox/discover-check/operator-inputs/approved-quote-request.json`,
`approved-quote-response.json`, and `approved-quote-intent.json`, plus the
no-write corpus preflight command that consumes those files. The handoff reports
whether each local input file is missing or present, using path metadata only;
it does not read or print request/response content in the workbook view.
The same `--show-drafts` handoff prints the approved quote exchange staging
contract, including byte caps, scan limits, and `do_not_stage` rules, so draft
workbooks do not imply that full Burp history exports or secret-bearing captures
are acceptable evidence inputs.
Placeholders still have to be replaced from one approved quote request/response
pair before anything is copied into official sidecars. SHA-256 binding fields
must be real 64-character hex digests; placeholders, short labels, or other
non-hex metadata block pair binding even when the same invalid value appears in
both files.
`evidence-prep-status --show-details` summarizes the paired sidecar contract
with the first blocker, binding review status, and first pairing issue, so a
bad `approval_reference` or SHA-256 mismatch is visible without opening the JSON.
When official evidence is missing, `bounty-shortest-path --show-commands` also
places `evidence-sidecar-drafts --no-write --show-drafts` at the front of the
handoff commands as a review-gated workbook view before the placeholder
preflight/prepare commands. With `--show-requests`, the same shortest-path view
prints the approved quote operator-input file status so the top bounty lane
shows whether the request, response, and intent files are still missing. With
`--show-requests --show-commands`, it also prints the fixed-path no-write corpus
preflight and sidecar-prepare previews for those operator-input files. The
preflight command remains review-gated while any input file is missing and
becomes ready only after all three local input files are present; the
sidecar-prepare preview remains a manual template until the approval reference
placeholder is replaced. The shortest-path `Next:` line follows the same
operator-input state, pointing to missing files first and to the ready no-write
preflight once all three inputs exist.
For transaction-integrity lanes, the shortest-path view also surfaces the same
approved quote exchange staging contract as `approved-quote-exchange-candidates`:
operator input directory, per-file byte cap, scan limits, preferred single-file
formats, and `do_not_stage` rules. That keeps the top bounty path aligned with
the bounded `/api/quote` handoff and avoids treating full Burp history exports or
secret-bearing captures as acceptable input.
The same operator handoff now carries a one-capture closure plan. It shows the
current active step from staged capture, import preview, local operator-input
write, paired corpus preflight, official sidecar preview/write, readiness,
decode, finding-gate, and adjudication. The plan is workflow control only:
write steps stay manual/review-gated, and the capture still cannot promote a
Medium+ finding until official sidecars, offline decode, gate, and adjudication
all agree.
When the pair reaches `ready-for-decode`, the same contract exposes the gated
no-write validation chain: `transaction-sidecar-review`, `decode-transactions`,
`gate`, and `adjudicate`. Blocked pairs keep that command list empty.
`bounty-prep-sync --show-checks --show-details` also compares the top
`bounty-action-queue` request with the next evidence packet's
`evidence_intake_manifest`, including artifact coverage, pair-binding status,
binding-field count, copy policy, and reject-rule count, before asking anyone to
fill official sidecars.

`methodology-review` also emits `bounty_harness_alignment`, a compact
bug-bounty readiness check derived from the harness pattern of building system
context, ranking high-value leads, validating impact with a concrete oracle,
climbing a witness ladder, assembling the minimal PoC/report package, and
keeping feedback/resource gates closed. This is stricter than broad audit
coverage: a lead is still blocked until the validation oracle, witness ladder,
finding gate, and adjudication prove concrete impact.
The same alignment now includes a `validation_funnel` for unattended loops:
system context, lead selection, impact oracle, witness ladder, and
finding-gate/adjudication are counted as separate stages with survival rates and
the first blocking stage. The funnel is accounting only; it does not collect
evidence or promote a static candidate into a bounty finding. When the first
gap is an impact oracle or witness ladder, the alignment also links it to the
current `next_evidence_packet` from `bounty-action-queue`, including the first
missing sidecar and official evidence contract blocker. The same first-gap
packet now carries `source_invariant_context`, so `--show-funnel` can print the
source invariant, source signal, and negative controls that explain why a
source-positive path is still not promotable without approved official
evidence. It also carries the `evidence_intake_manifest` summary, including
artifact counts, pair-binding status, required binding fields, copy policy, and
reject rules, so the methodology funnel shows exactly what the next approved
evidence handoff must contain.
`bounty_harness_alignment` also emits `iteration_strategy`, a compact routing
decision for unattended work. It separates the human/operator official-evidence
lane from agent-safe offline deepening, names the first missing artifact, tells
whether the agent can continue offline, and records the explicit
`do_not_promote_reason` while Medium+ evidence is absent. This strategy is
workflow control only; it does not create sidecars, collect traffic, or bypass
intake, finding-gate, or adjudication.
It also emits `assessment_mode_comparison`, which scores the same candidates as
both `greybox` and `blackbox` without changing the profile. This makes it clear
when coverage-first and bounty-first modes would pursue different top leads, and
how many secondary candidates blackbox mode would park behind the dominant
bounty path. `assessment_strategy_reconciliation` then compares the validation
plan, methodology high-value queue, and bounty reportability funnel as separate
selection sources. It records the active source, the recommended follow source,
the reportability source, and split reasons such as
`validation-vs-methodology-source`, so unattended loops can follow the active
mode without confusing a greybox coverage target with a bounty-valid evidence
blocker. Add `--show-funnel --show-mode-comparison` to print those stage
blockers, per-mode scores, and reconciliation status directly in the no-write
CLI output.

Use `lead-dossier` when you want the same evidence closure in a tighter
bug-bounty style lead file. It applies the “read code, constrain by
scope/docs, create candidate paths, and write down leads worth checking”
workflow to the current artifacts, then prints source refs, path/method
options, missing evidence, blockers, and safe offline commands for each
Medium/High/Critical thread. For RPC resource-abuse leads, `--show-evidence`
also prints the evidence contract id, required operator decisions, and the first
reportability gates so the next step is an evidence closure rather than a broad
audit. The lead order follows `assessment_mode`: greybox keeps coverage-first
ordering, while blackbox ranks gate-ready and high-payoff reportable leads ahead
of broad coverage gaps. Each lead carries an `assessment_rank` scorecard with
`coverage_pressure`, `bounty_pressure`, `validity_pressure`, a composite score,
and a pursue/park decision. In greybox mode, missing dangerous-surface evidence
raises coverage pressure; in blackbox mode, gate-ready validity and expected
payoff dominate. Blackbox lead sets also include `relative_focus`: when one
dominant bounty candidate is strong enough, weaker broad-coverage leads are
parked behind it until that candidate stalls or closes. Each lead also prints a
machine-readable `objective_alignment` showing the active objective, completion
unit, and whether that lead satisfies the current mode's success condition, plus
a strict validation checklist status for scope, attacker control, concrete
impact, minimal evidence, safe reproduction, counter-evidence,
severity/report path, and the active `assessment_mode` objective. The lead stays
blocked before finding gate until all eight questions are satisfied. Transaction
leads also print a `transaction-evidence-closure` plan that turns payload
sidecar, candidate extraction, payload contract, intent policy, decode review,
and finding-gate blockers into ordered, redacted artifact steps. The dossier
also emits `objective_satisfaction`, a run-level rollup of the same model. In
greybox mode it stays open until every ranked dangerous surface is covered or
closed; in blackbox mode it becomes satisfied as soon as one gate-ready
Medium/High/Critical report path exists, while weaker broad-coverage leads can
remain parked. The rollup includes `top_unblocker`,
`unblocker_lane_counts`, `unblocker_actionability_counts`, and
`unblocker_package_status_counts` so the next loop can distinguish approved
payload capture, provider/operator evidence, deployment resource evidence,
read-only response observation, resource gates, finding-gate review, and whether
the current package is waiting on a sidecar, operator evidence, offline review,
or a resource gate. Each unblocker also carries a `validation_oracle` that names
the exact proof model required for validity, such as `transaction-intent`,
`single-response-impact`, `provider-impact`, `resource-control`, or
`finding-gate`. The oracle lists acceptance checks and rejection conditions so
blackbox mode can pursue one valid bounty path while greybox mode can close each
dangerous surface without treating static suspicion as a finding. Each unblocker
also carries an `evidence_package` with required artifacts, safe no-write review
commands, active-validation gates, and forbidden validation steps for that lane.
When an artifact directory is known, the package's safe reviews are expanded
into command-safety-classified `safe_offline_command_refs`.

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  lead-dossier --no-write --show-commands --show-evidence --skip-current-resource-check
```

The dossier is also offline-only. It does not invoke Burp, read raw Burp
history, send requests, run scanners, sign wallets, or submit transactions.

When the loop is ready but no reportable evidence exists, use
`hypothesis-matrix` to rank the next research questions from current local
artifacts:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  hypothesis-matrix --no-write --show-next
python3 scripts/inferforge.py --artifact-dir .greybox/target-set \
  hypothesis-matrix --discover-child-runs --no-write --show-next
```

The matrix is not a finding list. It labels reportability gates, scope/resource
gates, and impact hypotheses so the harness can choose whether to do offline
review, wait for memory pressure to clear, or run one low-risk validation step.
Each hypothesis also carries business-logic test dimensions and API
authorization evidence profiles. These profiles map leads to concrete proof
models such as transaction-intent mismatch, object-level authorization failure,
object-property exposure or mass assignment, method authorization bypass, and
function-use/resource-boundary abuse. They are oracle hints only: BOLA/BOPLA or
business-logic labels do not become findings without approved endpoint-specific
evidence and finding-gate acceptance.
If `endpoint-clusters.json` has not been written yet, the matrix falls back to
the active target profile or `target-profile.json`, so newly discovered profiles
can still produce offline hypotheses before an audit run exists. Statically
discovered rewrite proxies are ranked as offline review items first: review the
source rewrite, fixed upstream, catch-all path shape, and one approved read-only
concrete path before probing.
When `.greybox/rpc-method-policy.json` or local source shows remotely supplied
transaction material flowing toward wallet signing calls, the matrix adds a
`transaction-flow-review` hypothesis. This is offline-only: the next step is to
collect an approved transaction corpus and run `decode-transactions`, not to
sign or submit a wallet transaction.
If the transaction-flow artifact is missing or from an older schema, matrix and
validation-plan generation rebuild a bounded in-memory source review instead of
propagating stale `quote_contract=missing` context.
When that review finds a server-side credentialed upstream without same-file
auth or rate-limit evidence, the matrix also emits a separate
`credential-proxy-review` hypothesis. This remains offline-only and requires
provider quota, billing, availability, or account-abuse evidence before any
finding claim. Use
`credential-impact-checklist --no-write --show-commands --show-evidence --skip-current-resource-check --show-evidence-contract`
to print the credentialed-upstream evidence contract, including reportability
gates, missing provider/operator decisions, safe evidence sources, and forbidden
validation steps without sending target or provider traffic.
It also emits `credential_impact_approval_packet`, a compact offline packet for
the provider-impact path. The packet names the recommended credentialed
entrypoint, provider, redacted `operator-evidence.json` sidecar, accepted
present statuses, missing quota/rate-limit/billing/monitoring decisions,
resource-gated approval sequence, and current finding-gate blockers. In
`greybox` mode this helps close credentialed-upstream coverage for every
dangerous source-derived route; in `blackbox` mode it keeps the work focused on
the smallest provider/operator evidence package that can support one valid
high-impact bounty report. Credential leads also expose a
`credential-impact-evidence-closure` plan so route context, redacted operator
evidence, provider-impact review, single-request resource gates, and
finding-gate entry stay ordered and blocked until concrete provider impact
evidence exists.
Profiles can attach `quote_provider.public_docs` entries for official provider
documentation. InferForge indexes those references as public context for API-key
authentication and executable transaction-payload behavior, but it does not
treat them as quota, billing, rate-limit, or account-impact evidence unless the
operator/provider sidecar explicitly proves that impact.
The RPC/source policy also records static transaction-intent signals such as
preview-wallet versus execution-wallet paths, remote payload deserialization,
and client-side recent-blockhash refreshes. These signals only define what the
decoded corpus must be compared against; they are not vulnerability findings on
their own.
Use `transaction-flow-review` for the dedicated low-memory source-flow pass:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  transaction-flow-review --no-write --top 8
```

It scans only bounded local TS/JS source files, skips dependency/build
directories, and distinguishes remote quote transaction payloads flowing toward
wallet signing from locally constructed transaction signing helpers. The output
`.greybox/transaction-flow-review.json` lists dataflow refs, required decoded
intent comparisons, forbidden actions, and an intent-policy scaffold derived
from profile `quote_intent` directions. It also indexes source-backed quote
intent contract evidence: client request shape, server request-key allowlists,
mint/direction constraints, sender/recipient binding, amount bounds, quote-count
bounds, and executable payload extraction. When source shows a server-side
credentialed upstream proxy, it also adds a cost/quota review that requires
provider or operator impact evidence before reportability. The scaffold records
which buy/sell mint pairs and `allowedPrograms` are already known and which
runtime values still need an approved quote corpus, wallet, and raw `amountIn`.
The quote source contract also carries `source_intent_guard_summary`, which
collapses those server-side request-key, mint-pair, sender/recipient, amount,
and quote-count guards into a positive-control status such as
`source-intent-guards-indexed`. This lowers false-positive pressure from request
field tampering while keeping the residual blocker explicit:
`approved-payload-decode-required`.
It sends no requests, does not open a wallet, and never signs or submits
transactions.
When RPC source shows client-keyed in-memory rate-limit fallback behavior, the
matrix can add a `resource-abuse-review` hypothesis. This is also offline-only:
review deployment proxy header trust, external rate-limit store configuration,
and bounded key/TTL evidence. Custom-server WebSocket RPC handlers are included
in this offline source review, so client-IP-keyed connection caps, pending
message queues, message-size limits, and batch-size limits can become resource
review signals without opening sockets. Do not validate it with rate-limit
stress, flood, or DoS testing.

Use `deployment-review` to collect that deployment/resource-control context
without traffic:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  deployment-review --no-write --top 8
```

It scans only allowlisted local config/deployment files such as `.env.template`,
Dockerfile, docker-compose files, `vercel.json`, root README, and Helm chart
YAML under `helm/`. If `.env.local` or `.env` exists, it records key names only:
values and file hashes are not written to the artifact. The output
`.greybox/deployment-resource-review.json` summarizes external rate-limit store
configuration, proxy/header trust evidence, key/TTL bounds, fallback monitoring,
and deployment env injection. Missing categories remain operator-evidence
requirements; this artifact is triage, not a reportable resource-exhaustion
finding. `operator-evidence-review --no-write --show-missing --show-template`
prints the redacted `operator-evidence.json` sidecar path plus template item
IDs, evidence questions, accepted present statuses, and redaction reminders for
the missing decisions. Add `--show-template-json` to print the redacted sidecar
template body directly for manual review before creating `operator-evidence.json`.
Add `--show-closure-contract` to group the same sidecar requirements into
credentialed-upstream cost-abuse and RPC resource-exhaustion closure contracts,
including the offline review/gate commands, stop conditions, and evidence
contracts. The credential contract spells out provider quota/rate-limit/billing
impact gates; the RPC contract spells out which operator decisions must be
proven, which header-trust/fallback conditions are reportable, and which safe
evidence sources can support the claim without traffic volume.
Use `operator-impact-readiness --no-write --show-commands` with optional
`--show-checks`, `--show-next`, `--show-gates`, and `--show-contracts` to
summarize the same operator-impact proof path and command-safety totals. The
operator sidecar review, credential impact checklist, and RPC proxy parity review
stay ready as offline checks; bounty validation, invalidity review, finding-gate,
and adjudication commands remain review-gated until the required redacted
operator/provider evidence is present and the relevant operator-impact gate is
ready.
`operator-evidence-review` also emits `resource_control_approval_packet`, a
compact offline packet for the RPC/resource-control thread. It names the
resource entrypoint, redacted operator-evidence sidecar, accepted present
statuses, missing external-store/proxy-trust/IP-key/bounds/monitoring decisions,
the resource-gated approval sequence, and finding-gate blockers. The packet is
explicitly non-stress: it never authorizes floods, rate-limit exhaustion,
Scanner, Intruder, or DoS validation. In `greybox` mode it closes resource
coverage decisions; in `blackbox` mode it keeps the thread parked unless
non-stress deployment/operator evidence can support a valid availability,
quota, or operator-impact report.
Resource-exhaustion leads also expose a `resource-control-evidence-closure`
plan through `lead-dossier --show-evidence`: resource signal context,
deployment review, redacted operator sidecar, resource-control review,
non-stress impact evidence, single-request resource gate, and finding-gate entry
stay ordered and blocked until concrete deployment/operator impact evidence
exists.
RPC proxy abuse leads also emit `rpc_proxy_abuse_approval_packet` through
`validation-plan`, `lead-dossier`, and `iteration-decision`. This packet is
separate from resource exhaustion: it records the exact RPC proxy entrypoint,
the local `rpc-method-policy.json` reference, transaction-method exposure
status, origin/rate-control review status, deployment/operator sidecar path,
missing method/env/origin/resource decisions, and current finding-gate blockers.
Static proxy exposure, public-chain read access, or a configurable method policy
is not enough for a finding. Greybox mode uses the packet to close every
dangerous RPC method, origin, rate-control, and deployment evidence gap; blackbox
mode keeps the work focused on one exact RPC boundary that can support a valid
high-impact, non-DoS bounty report. It never authorizes broad method
enumeration, rate-limit stress, wallet signing, `sendTransaction` submission, or
Burp Scanner/Intruder traffic.
When RPC source shows rate-limit buckets keyed from
`x-forwarded-for`, that template also includes
`rpc-client-ip-header-trust-model`, which asks for production edge/header
overwrite and direct-to-app reachability evidence without rate or DoS testing.

Use `rewrite-review` for the dedicated fixed-upstream rewrite/proxy review:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  rewrite-review --no-write --show-next
```

This command is local and read-only. It flags catch-all rewrites, fixed
upstreams, unconditional routes, and review-only observation candidates, then
lists the evidence required before a static rewrite/proxy hypothesis can become
a reportable issue.
`rewrite-response-review --no-write --show-observation-contract --show-sidecar-template-json`
prints the single approved-path promotion, resource-gate, Burp observe,
response-review, and finding-gate preview sequence without sending requests.
Observation-contract steps carry command-safety refs: only the no-write
promotion preview is `ready`, profile writes and post-observation reviews remain
`review-gated`, resource checks are `resource-gated`, and the single Burp
observe step is non-runnable with `blocked_external` set until the preceding
approval/resource gates are closed.
It also prints a compact single-request approval packet with the recommended
read-only path, sensitivity score, redacted sidecar fields, resource-gated active
steps, and remaining finding-gate blockers. The same command prints a redacted
`rewrite-response-sidecar.jsonl` template for the case where a reviewer has one
approved response shape but does not want to keep raw Burp history or a full
response body in artifacts.
`validation-plan`, `lead-dossier`, and `iteration-decision` carry the same
rewrite-response approval packet so unattended loops can keep this as a
one-request evidence closure instead of broad catch-all path enumeration.
Fixed-upstream leads also expose a `rewrite-response-evidence-closure` plan:
source context, read-only path selection, one redacted response sidecar or
observation, impact classification, and finding-gate entry stay ordered and
blocked until concrete impact evidence exists.
If `endpoint-clusters.json` or the target profile does not list a static
`next.config.*` rewrite, `rewrite-review`, `hypothesis-matrix`, and
`validation-plan` can still merge source-discovered rewrite-proxy clusters into
their in-memory review. This catches profile omissions such as catch-all
same-origin API proxies without changing the checked-in profile or sending
traffic.
Use `rewrite-validation-checklist --no-write --show-candidates --show-commands`
to turn those review items into a one-path validation checklist. It prints
client-derived read-only candidates, blocked dynamic templates, and no-write
`promote-observation-candidate` previews for exactly one approved local path.
Those preview commands carry item-level and top-level command-safety summaries
and `ready` labels because they are local no-write promotion previews, not
traffic or Burp observation steps.
The checklist is still offline: it does not invoke Burp, start a browser, send
HTTP traffic, or enumerate catch-all paths.
After the reviewed profile has produced a normalized observation, use
`rewrite-response-review --no-write --show-observations --show-commands --show-observation-contract --show-sidecar-template-json`
to review only the existing `burp-history-observations.jsonl` rows for that
rewrite and keep the single-path promotion/observe/review contract visible. It
prints command-safety summaries for item-level and top-level follow-up commands,
so no-write promotion previews and later local gate/adjudication previews show
their per-command classifications instead of bare shell lines. It
separates “one approved response observed” from “candidate
sensitive-field or path confusion impact evidence”, redacts response samples,
and still requires a manual finding-gate decision before anything is treated as
reportable. The sidecar template includes `path_options` with candidate path,
cluster, priority, source reference, and sensitivity hints. Choose exactly one
reviewed in-scope read-only path, set `approved: true` only for that response,
and keep the sidecar to method/path/status/content-type, high-level impact
indicators, sensitive field paths, and a short redacted impact summary. Do not
store cookies, bearer tokens, API keys, private keys, seed phrases, signatures,
raw Burp history, or full response bodies. `response-evidence-readiness`
summarizes the same minimum package and now carries command-safety totals: the
sidecar/template review command stays ready, while validation gate,
finding-gate, and adjudication commands remain review-gated until the approved
response sidecar has candidate impact evidence.
If candidate impact is present, `gate --no-write --show-items` imports it as a
redacted manual-review gate item; it does not mark the issue reportable by
itself. When no evidence is ready for gate review, the same command prints
`blocked_gate_previews` from validation-plan approval packets. These previews
list the missing evidence and finding-gate blockers, but they are explicitly not
findings and never appear in `findings.json`.
For source-backed fixed-upstream API routes, it also scans the referenced route
source for fixed upstream fetches, positive route-parameter guards, query
forwarding, credential/header forwarding, upstream status forwarding, and cache
controls. These `source_guard_review` decisions let validation plans keep a
fixed-upstream item in offline review while memory or swap pressure blocks
active baseline requests.
For catch-all rewrites, it also scans local frontend client code for concrete
HTTP `GET` / `HEAD` path literals and maps them to local rewrite paths as
reviewable read-only candidates. Dynamic templates such as ``/users/${id}`` and
non-read-only methods such as `POST` are listed as blocked candidates instead;
they are never promoted into unattended validation traffic by this review step.
To keep rollups usable on small VPS hosts, this client-code scan runs only when
a catch-all rewrite review surface exists and prunes dependency, build,
coverage, and hidden directories while walking source files.

Use `validation-plan` to turn the ranked hypotheses into explicit preconditions,
allowed commands, required evidence, stop conditions, and forbidden actions:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  validation-plan --no-write --show-commands
python3 scripts/inferforge.py --artifact-dir .greybox/target-set \
  validation-plan --discover-child-runs --no-write --show-commands
```

The plan is still read-only. It does not run the commands it prints; it exists
so unattended work can stop at scope, resource, command-safety, and
reportability gates before any validation traffic is sent.
By default it also takes a current local `/proc` resource snapshot and forces
active validation items back behind the resource gate when memory or swap is
unhealthy. Use `--skip-current-resource-check` only for deterministic offline
artifact comparisons.

Use `iteration-decision` as the orchestrator-facing next-step gate. It reads the
validation plan, artifact health, and current resource snapshot, then separates
offline commands that can run now from active validation commands that must wait
behind scope, resource, and command-safety gates:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/target-set \
  iteration-decision --discover-child-runs --no-write --show-commands
```

The decision artifact is still read-only. It does not run the commands it
prints; it exists so unattended loops can choose a safe next action without
guessing from free-form text. It also embeds and prints the active
`assessment_mode` optimization policy: `greybox` keeps the loop
coverage-first until dangerous source-derived surfaces are closed, while
`blackbox` keeps the loop bounty-first and parks broad coverage work once a
stronger valid high-impact report path exists. The artifact includes
`iteration_focus`, a ranked validation-item scorecard using the same
`coverage_pressure`, `bounty_pressure`, `validity_pressure`, and pursue/park
decision fields as `lead-dossier`. Blackbox focus rows also carry
`relative_focus` so an unattended loop can park broad coverage work behind the
dominant bounty candidate; approval packets also carry the matching assessment
scorecard for the validation item that produced them. The iteration summary also
includes `objective_satisfaction`, so unattended runs can tell whether the
active mode still needs coverage closure or a valid Medium+ bounty report path,
which evidence lane is currently blocking it, and which evidence package should
be completed before any active validation. Package commands also appear as an
`objective-evidence-package` offline action so the loop can prioritize the
current blocker before generic planning commands. Those package commands are
deduped out of the generic offline action preview.

`gate --no-write --show-items` carries the same oracle vocabulary into blocked
finding-gate previews. A blocked preview can now say whether it is waiting on a
`transaction-intent`, `single-response-impact`, `provider-impact`, or
`resource-control` oracle, which keeps gate/adjudication output aligned with the
objective rollup.

For in-scope WebSocket candidates extracted from static assets, keep validation
to handshake-only unless a separate message-level plan has been reviewed:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  websocket-candidate-review --handshake-baseline --allow-nonlocal-target
```

`websocket-candidate-review` opens at most one HTTP Upgrade attempt per
in-scope candidate, sends no WebSocket frames, subscriptions, wallet payloads,
or trading messages, and records only response headers plus a hash of the random
`Sec-WebSocket-Key`. Handshake baselines are blocked by the local resource gate
while memory or swap pressure is warning unless `--allow-resource-warning` is
passed after explicit review. It is coverage evidence, not a vulnerability
finding.

The same command also performs a bounded offline source review for WebSocket
proxies that forward client request headers to an upstream socket. A
`needs-source-header-review` result is a lead only: it requires authentication
context, browser/client header constraints, and upstream trust or disclosure
evidence before it can become a reportable finding. The source review also
classifies local cookie/auth context: sensitive or unknown app auth keeps the
lead at `medium`, while non-sensitive preference cookies such as `theme` and
server-to-upstream bearer headers stay `low` until stronger browser auth
material is shown.

For takeover-oriented Web/App scope checks, keep the host list explicit:

```bash
python3 scripts/inferforge.py --target https://in-scope.example \
  --artifact-dir .greybox/in-scope-example \
  host-takeover-baseline \
  --host in-scope.example
```

`host-takeover-baseline` checks only the configured target host and any repeated
`--host` values. It collects DNS CNAME/A/AAAA records and a bounded HTTPS root
response hash for known dangling-provider fingerprints; it does not enumerate
subdomains, claim third-party resources, or store response bodies. DNS and
HTTPS baseline checks are blocked by the local resource gate while memory or
swap pressure is warning unless `--allow-resource-warning` is passed after
explicit review.

The default resource caps are intentionally small: 4 same-origin script assets,
256 KiB per fetched resource, and 80 retained candidates. Raise `--max-assets`,
`--max-bytes`, or `--candidate-limit` only when the runner has enough memory and
the target scope permits the extra page-asset requests.

On memory-constrained VPS runs, snapshot local resource pressure before
starting unattended work:

```bash
python3 scripts/inferforge.py --artifact-dir .greybox/in-scope-example \
  resource-snapshot --watch-port 3100 --strict
```

`resource-snapshot` reads local `/proc` memory, swap, TCP listener, and top RSS
process metadata only; it sends no network requests. With `--strict`, it returns
non-zero when the configured memory or swap warning thresholds are exceeded, so
unattended scripts can stop before launching heavier work. Port `3100` is the
default local target application port for the checked-in profile, not Burp's
proxy or Burp's built-in browser. Keep it closed unless a local app regression
actually needs the dev server.

Do not add control-plane ports such as `2455` to resource-snapshot watch lists,
readiness checks, health checks, resource checks, probes, or memory-reclaim
candidates. In the Codex VPS environment, `2455` is reserved for the AI API load
balancer and must not be observed, signaled, stopped, restarted, or probed by
unattended tooling. If a watch port matches the protected control-plane list,
`resource-snapshot` exits before collecting local process or port data. Self-tests
must use synthetic protected ports for guard verification rather than passing
real control-plane ports as command arguments.

`burp-sync`, `audit`, `blackbox-asset-map`, `websocket-candidate-review`
handshake baselines, `host-takeover-baseline`, `collect-quote`,
`collect-orca-baseline`, `validation-plan`, `iteration-decision`, and
`regression-suite` also take an
internal current-resource preflight before memory-sensitive work. The internal
gate is intentionally conservative (`MemAvailable` below 2048 MiB or used swap
above 1024 MiB is a warning). When an active command hits that gate, it writes a
resource-gate artifact and exits before active probes, Burp history reads, quote
collection, Orca baseline requests, black-box page/script fetches, WebSocket
handshake baselines, DNS/HTTPS takeover baselines, Node transaction decoding,
browser automation, or the full regression step schedule. For pure no-write
planning previews, prefer commands that include `--skip-current-resource-check`;
run an explicit `resource-snapshot --watch-port 3100 --strict` only immediately
before approved active target work. Use `--allow-resource-warning` only after
reviewing local pressure and narrowing the command with limits or skip flags.

Review program scope, authentication context, and endpoint criticality before
any active probes:

```bash
python3 scripts/inferforge.py --profile profiles/in-scope-example-blackbox.json \
  --artifact-dir .greybox/in-scope-example \
  plan --observed-only --no-write
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
blackbox-http-observed
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
  path without opening the JSON artifact. Placeholder promotion commands remain
  `manual-template`, the resource health check is labeled `resource-gated`, and
  the active Burp observation template is `review-gated` with an external
  blocker. After review, use
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
`burp-sync --observe` only after the path has been approved and
`resource-snapshot --strict` is healthy. Reviewed-profile observation follow-up
commands use a narrower Burp history count than the general default, and audit
commands default to `audit --max-probes 6 --no-ws`; add broader external or
WebSocket resource probes only after scope and runner capacity are reviewed.
`promote-observation-candidate` labels those follow-up commands as well: the
resource check is `resource-gated`, the Burp observe step is non-runnable with
`blocked_external`, and post-observation review/audit commands remain
`review-gated` until evidence exists.

When a rewrite observation gap is present, `verification-queue` also emits the
same promotion sequence as manual-review command templates:

1. preview the promotion with `promote-observation-candidate --no-write`;
2. promote the approved path into `.greybox/reviewed-profile.json`;
3. run `resource-snapshot --strict` with that reviewed profile and stop if it is
   not healthy;
4. run narrow `burp-sync --observe` with that reviewed profile;
5. rerun the low-resource `audit --max-probes 6 --no-ws` with the reviewed
   profile.

The placeholder `REPLACE_WITH_APPROVED_CONCRETE_LOCAL_PATH` in the queue is
deliberately rejected by the promote command until a human replaces it with one
reviewed local path.

Active `burp_observation_plan` entries are validated as executable traffic.
They must use a concrete local path beginning with `/`; full URLs,
`REPLACE_WITH_*` placeholders, `{param}` templates, `<placeholder>` text, and
whitespace are profile-validation errors. Keep unresolved paths in
`review_observation_candidates` until one reviewed concrete path is promoted.

When a separate profile file omits target-specific fields such as `clusters`,
`probe_targets`, `quote_intent`, `quote_request`, `quote_response`,
`quote_provider`, `environment_readiness`, `burp_observation_plan`, or
`websocket_observation`, InferForge uses neutral empty defaults and emits
profile-validation warnings. It does not borrow `infrafi-web` clusters, probe
paths, quote mint intent, quote request/response shape, or external readiness
checks for another target. Quote collection and
direction-derived transaction policy checks read mint direction from the target
profile:

```json
{
  "quote_intent": {
    "chain": "Solana",
    "maxNumQuotes": 1,
    "allowedPrograms": [
      "EXPECTED_SOLANA_PROGRAM_ID"
    ],
    "directions": {
      "buy": {
        "sourceMint": "SOURCE_MINT_FOR_BUY",
        "destinationMint": "DESTINATION_MINT_FOR_BUY"
      },
      "sell": {
        "sourceMint": "SOURCE_MINT_FOR_SELL",
        "destinationMint": "DESTINATION_MINT_FOR_SELL"
      }
    }
  }
}
```

Quote request construction is profile-owned too. `body_template` is a JSON
object whose exact placeholder strings are replaced structurally, preserving the
replacement value type. `policy_fields` maps semantic fields to dot paths so
field-specific probes can delete or mutate the correct target-specific field:

```json
{
  "quote_request": {
    "body_template": {
      "swap": {
        "from": {
          "network": "{sourceChain}",
          "mint": "{sourceMint}"
        },
        "to": {
          "network": "{destinationChain}",
          "mint": "{destinationMint}"
        }
      },
      "amount": "{amountIn}",
      "wallet": "{wallet}",
      "receiver": "{recipient}",
      "limit": "{maxNumQuotes}"
    },
    "policy_fields": {
      "route": "swap",
      "source": "swap.from",
      "destination": "swap.to",
      "source_chain": "swap.from.network",
      "destination_chain": "swap.to.network",
      "source_mint": "swap.from.mint",
      "destination_mint": "swap.to.mint",
      "amount": "amount",
      "sender": "wallet",
      "recipient": "receiver",
      "max_num_quotes": "limit"
    }
  }
}
```

Quote response transaction extraction can also be profile-owned. Candidate
paths are simple JSON paths supporting object fields plus array indexes or
wildcards. InferForge tries these configured paths first, then keeps its generic
recursive JSON and base64 scan as a fallback:

```json
{
  "quote_response": {
    "transaction_candidate_paths": [
      "$[*].payloads[*].data.transaction",
      "$.payloads[*].data.transaction"
    ],
    "expected_payload_type": "svm"
  }
}
```

For JSON quote-response sidecars, `expected_payload_type` is a decode-readiness
gate. If a configured transaction path resolves to `payloads[*].data.transaction`
but the sibling `data.type` is missing or does not match the expected value,
`transaction-sidecar-review` keeps the corpus out of `ready-for-decode`.
Text-only extracted base64 sidecars remain allowed after manual approval because
they intentionally do not preserve full provider response context.

Quote provider response diagnosis is profile-owned too. Use
`quote_provider.diagnostics` to map target-specific local/upstream error shapes
to stable classifications without hard-coding a provider globally:

```json
{
  "quote_provider": {
    "name": "ProviderName",
    "diagnostics": [
      {
        "id": "provider-config-missing",
        "classification": "provider-config-missing",
        "statuses": [503],
        "body_contains": ["Provider configuration missing"],
        "summary": "The target rejected quote collection before upstream forwarding because provider credentials are missing.",
        "next_step": "Set PROVIDER_TOKEN, restart the target server, then prepare an approved quote response sidecar and review the transaction evidence contract."
      },
      {
        "id": "provider-upstream-policy-rejected",
        "classification": "provider-upstream-policy-rejected",
        "statuses": [401, 403],
        "body_contains": ["Provider quote failed"],
        "summary": "The target reached the quote provider, but upstream rejected the request after local validation.",
        "next_step": "Verify provider credentials, account permissions, route, wallet, and amount, then prepare an approved quote response sidecar and review the transaction evidence contract."
      }
    ]
  }
}
```

External dependency readiness is profile-owned as well. The default
`infrafi-web` profile declares M0-specific checks, but a different target should
declare its own provider variables or leave this empty:

```json
{
  "environment_readiness": {
    "checks": [
      {
        "id": "provider-token-configured",
        "type": "env",
        "key": "PROVIDER_TOKEN",
        "secret": true,
        "next_step": "Set PROVIDER_TOKEN and restart the target server."
      },
      {
        "id": "health-reports-provider-ready",
        "type": "target_health_field",
        "field": "provider_ready",
        "expected": true,
        "next_step": "Restart the target after configuring provider credentials."
      }
    ],
    "quote_collection_next_step": "Prepare or approve one quote response or extracted transaction payload sidecar, then run `transaction-sidecar-review --no-write --show-files --show-commands --show-payload-template-json --show-evidence-contract` and `transaction-corpus-checklist --no-write --show-commands --show-steps --show-payload-template-json --skip-current-resource-check` before decoding."
  }
}
```

`target_health_field` checks read only the fields named by the active profile
from the target health JSON. Field lookup accepts exact keys and common
snake_case/lowerCamelCase variants such as `provider_ready` and
`providerReady`, including dotted nested fields.

`discover-profile` copies `quote_intent` into the generated starter profile only
when the seed profile passed with `--profile` explicitly declares complete
`buy` and `sell` directions. It copies `quote_request`, `quote_response`, and
`quote_provider` only from an explicit seed profile that declares them. Running
discovery without an explicit profile does not copy the built-in regression
target mint intent, request/response shape, or provider diagnostics into a new
target.

When an explicit seed profile declares a `quote` cluster or
`probe_targets.quote.path`, static discovery also uses that profile-owned path
to classify a non-standard route as `quote-transaction-decoder`. Without
`--profile`, the generated starter profile stays neutral and uses only generic
source/path heuristics.

Use the static routing self-test to guard this invariant:

```bash
python3 scripts/inferforge.py self-test-profile-routing
```

The self-test builds a synthetic profile with non-`infrafi-web` paths and quote
mints, including a generic API route, generates probe/warmup/Burp observation
plans, and fails if default regression-target paths or quote mint intent leak
into those plans. It writes `.greybox/profile-routing-selftest.json` and does
not send HTTP requests or call Burp.

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

Use `--include-external` only when a bounded set of low-risk quote-provider validation
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
python3 scripts/inferforge.py gate --no-write --show-items
python3 scripts/inferforge.py coverage
python3 scripts/inferforge.py burp-observation-coverage
python3 scripts/inferforge.py response-deltas
python3 scripts/inferforge.py source-peek
python3 scripts/inferforge.py source-peek --no-write
python3 scripts/inferforge.py source-peek-requests
python3 scripts/inferforge.py source-risk-review --no-write --top 12 --show-signals --show-workbook
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-dependencies --surface shared-library
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-imported-controls --imported-control-status imported-validation-controls-only
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-route-guards --surface nextjs-app-route
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-route-guards --route-importer-guard-status route-importer-guard-gaps-indexed
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-flow --flow-status critical-same-file-source-sink-hints
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-config-context --config-status public-secret-env-review
python3 scripts/inferforge.py source-risk-review --no-write --focus wallet --top 6 --show-packet --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus external-deps --top 8 --show-external-deps
python3 scripts/inferforge.py source-risk-review --no-write --focus imported-invocation --top 8 --show-imported-invocation --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus input-shape --top 8 --show-input-shape --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus object-key-trust --top 8 --show-object-key-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus csrf-origin --top 8 --show-csrf-origin --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus cors-origin-trust --top 8 --show-cors-origin-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus control-order --top 8 --show-control-order --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus control-effect --top 8 --show-control-effect --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus response-exposure --top 8 --show-response-exposure --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus download-response-trust --top 8 --show-download-response-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus cache-policy --top 8 --show-cache-policy --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus path-trust --top 8 --show-path-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus upload-trust --top 8 --show-upload-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus auth-token-trust --top 8 --show-auth-token-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus auth-flow-trust --top 8 --show-auth-flow-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus account-recovery-trust --top 8 --show-account-recovery-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus role-permission-trust --top 8 --show-role-permission-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus cookie-trust --top 8 --show-cookie-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus message-trust --top 8 --show-message-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus client-rendering-trust --top 8 --show-client-rendering-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus security-header-trust --top 8 --show-security-header-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus client-storage-trust --top 8 --show-client-storage-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus randomness-trust --top 8 --show-randomness-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus crypto-primitive-trust --top 8 --show-crypto-primitive-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus business-value-trust --top 8 --show-business-value-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus tenant-scope-trust --top 8 --show-tenant-scope-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus workflow-precondition-trust --top 8 --show-workflow-precondition-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus resource-fanout-trust --top 8 --show-resource-fanout-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus sensitive-logging-trust --top 8 --show-sensitive-logging-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus error-disclosure-trust --top 8 --show-error-disclosure-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus debug-surface-trust --top 8 --show-debug-surface-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus code-exec-trust --top 8 --show-code-exec-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus server-template-trust --top 8 --show-server-template-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus deserialization-trust --top 8 --show-deserialization-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus archive-extraction-trust --top 8 --show-archive-extraction-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus xml-parser-trust --top 8 --show-xml-parser-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus regex-complexity-trust --top 8 --show-regex-complexity-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus query-trust --top 8 --show-query-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus graphql-resolver-trust --top 8 --show-graphql-resolver-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus ssrf-trust --top 8 --show-ssrf-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus redirect-trust --top 8 --show-redirect-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus webhook-trust --top 8 --show-webhook-trust --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus identity --top 8 --show-identity-binding --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --focus client-exposure --top 8 --show-client-exposure --show-triage
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --show-triage --triage-status critical-multi-context-review
python3 scripts/inferforge.py source-risk-review --no-write --top 8 --signal wallet-transaction-payload-boundary --dependency-status client-reachable-source
python3 scripts/inferforge.py attack-strategy
python3 scripts/inferforge.py attack-strategy --no-write
python3 scripts/inferforge.py evidence-chain
python3 scripts/inferforge.py evidence-appendix
python3 scripts/inferforge.py verification-queue
python3 scripts/inferforge.py verification-queue --no-write
python3 scripts/inferforge.py manifest
python3 scripts/inferforge.py artifact-health --discover-child-runs
python3 scripts/inferforge.py review-candidates --no-write
python3 scripts/inferforge.py regression-suite --offline-only --plan-only
python3 scripts/inferforge.py regression-suite --offline-only
python3 scripts/inferforge.py regression-suite --include-external --ws-resource-probes
python3 scripts/inferforge.py adjudicate
python3 scripts/inferforge.py audit --no-ws
python3 scripts/inferforge.py audit --ws-resource-probes
python3 scripts/inferforge.py lead-dossier --no-write --show-commands --show-evidence --skip-current-resource-check
python3 scripts/inferforge.py rewrite-response-review --no-write --show-observations --show-commands --show-observation-contract --show-sidecar-template-json
python3 scripts/inferforge.py transaction-payload-preflight --input ./approved-payloads.jsonl --no-write --show-records --show-commands
python3 scripts/inferforge.py approved-quote-capture-guide --show-commands
python3 scripts/inferforge.py redact-approved-quote-capture --input ./approved-quote.har --show-commands
python3 scripts/inferforge.py approved-quote-exchange-candidates --show-commands
python3 scripts/inferforge.py approved-quote-exchange-candidates --input ./approved-quote.har --show-commands
python3 scripts/inferforge.py prepare-approved-quote-operator-inputs --request-input ./approved-quote-request.http --payload-input ./approved-quote-response.http --approval-reference APPROVED-QUOTE-001 --no-write --show-preflight --show-commands
python3 scripts/inferforge.py transaction-corpus-preflight --request-input ./approved-quote-request.json --payload-input ./approved-quote-response.json --intent-input ./approved-quote-intent.json --no-write --show-policy-json --show-checks --show-commands
python3 scripts/inferforge.py prepare-transaction-corpus-sidecars --request-input ./approved-quote-request.json --payload-input ./approved-quote-response.json --intent-input ./approved-quote-intent.json --approval-reference APPROVED-QUOTE-001 --no-write --show-policy-json --show-checks --show-commands
python3 scripts/inferforge.py transaction-sidecar-review --no-write --show-files --show-commands --show-payload-template-json --show-evidence-contract
python3 scripts/inferforge.py transaction-corpus-checklist --no-write --show-commands --show-steps --show-payload-template-json --skip-current-resource-check
python3 scripts/inferforge.py decode-transactions
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
python3 scripts/inferforge.py self-test-bounty-program-profile
python3 scripts/inferforge.py self-test-source-risk-review
python3 scripts/inferforge.py self-test-regression-offline-safety
python3 scripts/inferforge.py review-blockers
python3 scripts/inferforge.py collect-quote --direction buy --wallet EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR --amount-in 1000000
python3 scripts/inferforge.py collect-orca-baseline
```

`decode-transactions` scans quote probe responses and optional sidecar files for
base64 Solana transaction payloads, then uses the app's `@solana/web3.js`
dependency to decode account keys, signer/writable flags, recent blockhash, and
compiled instruction metadata. It also parses SPL Token and Token-2022
`Transfer` / `TransferChecked` instructions enough to compare decoded source
mint transfer amounts against the requested `amountIn` when reliable
`TransferChecked` mint evidence is present. It can compare decoded payloads
against an expected swap intent. It never signs or submits transactions. Extra payload
files can be supplied as JSON, JSONL, or text. Each sidecar input is capped at
4 MiB by default so large Burp exports or response dumps do not create a memory
spike; skipped inputs are recorded in `transaction-intent.json.warnings`, and
the cap can be changed with `--max-input-bytes` when the input is explicitly
approved:

When the active profile declares `quote_response.transaction_candidate_paths`,
those simple JSON paths are applied before the generic recursive/base64 scan so
candidate summaries retain the provider-specific response location.
When `quote_response.expected_payload_type` is set, JSON sidecars must also show
that payload type before the sidecar is marked ready for decode.
Responses that mix the expected transaction candidate with incompatible sibling
payload shapes, such as EVM executable payloads, alternate transaction-shaped
fields, or Solana payload records without `data.transaction`, are held for review
before any official sidecar is prepared.
`transaction-payload-preflight --input ./approved-payloads.jsonl --no-write --show-records --show-commands`
is the offline intake check for a single approved local quote response or extracted
payload before it is copied into `transaction-payloads.jsonl`. It accepts JSON,
JSONL, text, or stdin, enforces the same 4 MiB default cap, reports only hashes,
shape records, candidate summaries, payload-type contract state, and redaction
hits, and never writes the official sidecar. A `ready-for-approved-sidecar-copy`
result means the input shape is compatible with the official sidecar; it is still
not evidence and does not satisfy finding gates until the official sidecar,
matching intent policy, decode review, finding gate, and adjudication all agree.

`approved-quote-capture-guide --show-commands` prints the offline handoff recipe
for the single approved `/api/quote` capture. It combines the current staging
contract, accepted single-file formats, required context, redaction checklist,
current staged-capture state, and the next local commands. Use it before asking
an operator to export or restage evidence: it makes clear that the capture should
stop at quote generation, should contain exactly one `POST /api/quote` request
plus its matching response, and should remove raw auth, cookie, API-key,
wallet-signature, submitted-transaction, and unrelated authenticated material.
The guide is read-only and does not create operator inputs or official evidence
sidecars.

`redact-approved-quote-capture --input ./approved-quote.har --show-commands`
is the local staging helper for an approved capture that parses but still carries
raw auth or cookie headers. It accepts the same single-exchange formats as the
staged-candidate scanner, extracts the unique `POST /api/quote` request and
matching response, removes forbidden request/response headers such as
`Cookie`, `Authorization`, `Set-Cookie`, API-key, token, secret, private-key,
and seed-phrase style headers, then previews a redacted `.http` output path.
With `--write-redacted-capture`, it writes only that supporting redacted capture
under `.greybox/discover-check/operator-inputs/` by default; it still does not
write operator input JSON files or official evidence sidecars. After writing,
rerun `approved-quote-exchange-candidates --show-commands` and import only if
the staged hygiene status is `passed`.

`prepare-approved-quote-operator-inputs --request-input ./approved-quote-request.http --payload-input ./approved-quote-response.http --approval-reference APPROVED-QUOTE-001 --no-write --show-preflight --show-commands`
is the offline helper for Burp/raw-HTTP handoff. It also accepts
`--exchange-input` for one approved raw HTTP exchange, Burp "Copy as cURL"
request followed by the matching raw HTTP response, JSON-wrapped cURL/response
exchange, JSON-wrapped raw HTTP exchange, HAR with one unique `POST /api/quote`,
or Burp XML item export with one unique `POST /api/quote`. It strips raw HTTP headers from an approved quote
request/response pair, keeps only the JSON bodies as candidate supporting
operator inputs, and generates an approved quote intent draft from the derived
wallet, recipient, mints, raw amount, optional minimum destination amount, chain,
direction, and payload type. By default it previews only. With
`--write-operator-inputs`, it writes the three supporting files under
`.greybox/discover-check/operator-inputs`; this still does not create official
evidence sidecars. Generated intent remains `approved_for_offline_validation=false`
unless `--approve-offline-validation` is supplied after operator review, and an
approved import also requires a real `--approval-reference`.
The cURL importer never executes the command and rejects `@file` data references;
it only reconstructs a raw HTTP request from inline arguments before the existing
header-stripping preflight runs. A JSON-wrapped cURL handoff can use fields like
`copy_as_curl`, `response`, and optional `status` when the response is available as a JSON
body instead of a raw HTTP response.
When an approved HAR, Burp XML export, cURL+response, JSON-wrapped exchange, or
raw HTTP exchange is staged directly under `.greybox/discover-check/operator-inputs`,
`evidence-sidecar-drafts` and `bounty-shortest-path` surface the importable
candidate and its exact no-write preview command. The staged-file scanner also
checks approved export files in subdirectories up to two levels deep, such as
`operator-inputs/exports/burp/*.xml` or `operator-inputs/exports/cURL/*.cURL`,
while keeping the same candidate-count and per-file byte caps.
`approved-quote-exchange-candidates --show-commands` runs the same staged-file
scanner directly and is read-only; with `--strict`, it exits non-zero unless at
least one importable staged exchange is present.
Use `--input PATH` to inspect a specific approved exchange file without moving it
under the operator input directory first; repeat `--input` for multiple files.
The candidate scanner also emits an approved-quote exchange staging contract:
accepted suffixes, per-file byte caps, scan limits, preferred single-file formats,
minimum capture contents, and material that must not be staged such as full Burp
history exports, cookies, bearer tokens, private keys, wallet signatures, or
unrelated authenticated traffic. This keeps the `/api/quote` evidence handoff
small and bounded before any official sidecar is written.
The scanner also separates parser importability from staging hygiene. A HAR,
Burp XML, cURL+response, JSON-wrapped exchange, or raw HTTP exchange can be
parser-importable while still showing `hygiene=needs-redaction-review` if the
staged file contains raw `Cookie`, `Authorization`, `Set-Cookie`, API-key, or
similar headers. In that case the one-capture closure stops at
`staged-capture-hygiene-review` and asks for a minimal redacted restage before
operator-input writes or official sidecars are considered.
If an explicit input path is missing, skipped, or otherwise not a usable quote
exchange, the hygiene summary now reports `hygiene=no-importable-staged-capture`
with `hygiene_skipped` rather than implying the capture is clean. A clean hygiene
status means at least one parser-importable staged exchange passed the staging
hygiene review.
After a staged exchange is discovered, the operator handoff's
`one_capture_closure_plan` gives the exact local sequence from staged-capture
hygiene review, optional redacted-capture staging, import preview,
operator-input write, paired preflight, official sidecar preview/write,
readiness, decode, finding-gate, and adjudication. If the top staged capture is
parser-importable but carries sensitive headers, the active closure step points
at `redact-approved-quote-capture` before any operator-input write. It
intentionally keeps writes manual and marks post-evidence commands blocked until
the required sidecars are real, paired, approved, and redacted.

`transaction-corpus-preflight --request-input ./approved-quote-request.json --payload-input ./approved-quote-response.json --intent-input ./approved-quote-intent.json --no-write --show-policy-json --show-checks --show-commands`
is the paired offline intake check for one approved quote request body and the
matching approved quote response or extracted payload. The optional
`--intent-input` file lets the reviewer bind a separate approved intent document
to the request before official sidecar prep. When present, the intent JSON must
match the request's wallet, source mint, destination mint, raw amount, optional
minimum destination amount, optional recipient, chain, direction, and `maxNumQuotes` fields; mismatches stop the
preflight at `intent-needs-review`. It derives the intent policy preview from the
request's configured sender, amount, source mint, and destination mint fields,
verifies that the response/payload has exactly one compatible transaction
candidate, checks response `amountIn`, route mints/chains, recipient, quote
container count, and payload `data.chain` against the approved request when the
response exposes those fields, prints the exact policy and decode follow-up
commands, and still writes no official sidecars. Stdin is supported for only one
side at a time; the other sides must be files so the tool never tries to read
the same stream twice.
A `ready-for-approved-corpus-sidecars` result only means the operator-reviewed
request/response/intent set is ready to be copied into the official payload and
intent-policy sidecars after approval.

`prepare-transaction-corpus-sidecars --request-input ./approved-quote-request.json --payload-input ./approved-quote-response.json --intent-input ./approved-quote-intent.json --approval-reference APPROVED-QUOTE-001 --no-write --show-policy-json --show-checks --show-commands`
previews that final offline assembly step. It reuses the paired corpus preflight,
builds the exact `transaction-payloads.jsonl` JSONL line and
`transaction-intent-policy.json` object that would be written, and prints the
sidecar review, decode, and finding-gate follow-up commands. It writes no
official sidecars unless `--write-official-sidecars` is also supplied, the
preflight is ready, an approval reference is present, and existing sidecars are
not being overwritten. If `--approval-reference` is omitted, a matching
`--intent-input` with `approval_reference` and
`approved_for_offline_validation=true` can seed the approval reference for the
preview/write gate. Use `--replace` only after reviewing the existing official
evidence files. `self-test-transactions` exercises this write path inside a
temporary artifact directory, requires `transaction-sidecar-review` to return
`ready-for-decode`, then runs `decode-transactions --no-write` and confirms no
`transaction-intent.json` artifact is written. It also runs a synthetic
high-impact intent mismatch through the same prepared sidecars, writes only a
temporary `transaction-intent.json`, and confirms the finding gate produces a
manual-review `candidate-transaction-integrity-impact` item without treating it
as reportable evidence.

`build-provenance-readiness` is the offline gate for Docker build-secret
signals. It now parses Dockerfile stages and final-stage `COPY --from` edges so
static `ARG`/`ENV`/`.npmrc` findings can be classified as final-image secret
paths versus builder/cache/log/registry provenance risks. For multi-stage builds
where the final runner does not copy a secret path, the readiness output shows
`source_class=builder-stage-provenance-only` and keeps Medium+ promotion blocked
until redacted build provenance proves actual retention or disclosure. This
command sends no traffic, does not query Docker or registries, and does not
create `operator-evidence.json`.

`transaction-sidecar-review --no-write --show-files --show-commands --show-payload-template-json --show-evidence-contract` prints the
accepted sidecar files, configured candidate paths, and compact JSON/JSONL/TXT
payload-shape examples when a sidecar is present but no base64 transaction
candidate can be extracted. When a payload sidecar already yields decode-ready
candidates but `transaction-intent-policy.json` is missing, it also prints the
matching `prepare-transaction-intent-policy --no-write`, write, and
`decode-transactions` command sequence for each profile direction.
An empty `burp-transaction-candidates.json` placeholder counts only as a present
file; it does not satisfy the candidate-bearing sidecar evidence gate.
Add `--show-payload-template-json` to print placeholder JSON/JSONL/TXT sidecar
templates for the single approved quote response before creating a local
payload sidecar.
Add `--show-evidence-contract` to print the single-corpus quote capture,
resource gate, Burp history import, sidecar review, and no-write decode preview
sequence without sending requests, signing wallets, or submitting transactions.
The evidence-contract view prints a command-safety summary and labels every
command step with the same `[ready]`, `[manual-template]`, or `[review-gated]`
classification used by frontier and gate views, so approved-input templates and
Burp history import cannot look like unattended runnable commands.
`transaction-evidence-readiness --no-write --show-commands` summarizes the
same proof path and carries command-safety totals. Sidecar review, corpus
checklist, and transaction-boundary review stay ready offline;
`decode-transactions` stays review-gated until exactly one approved payload and
matching intent policy are ready, and finding-gate/adjudication stay
review-gated until decoded transaction-boundary evidence exists.

`transaction-corpus-checklist` is the offline bridge between source-flow review
and decoding. It reads the current quote collection, Burp transaction candidate,
transaction intent, profile, and resource snapshot artifacts, then prints the
minimal approved quote-response corpus needed for `decode-transactions`. It does
not send requests, read raw Burp history, sign wallets, or submit transactions.
It also emits `transaction_corpus_approval_packet`, a compact offline packet
that names the recommended single `POST /api/quote` direction, the payload and
intent-policy sidecar paths, required redacted fields, the gated approval
sequence, and the current finding-gate blockers. In `greybox` mode this packet
helps close the dangerous transaction-intent surface; in `blackbox` mode it keeps
the evidence path focused on the shortest valid high-impact bounty candidate.
When the resource gate is degraded or critical, it keeps capture steps marked as
blocked and only prints sidecar formats plus decode commands:

With `--show-commands`, the corpus checklist uses the same command-safety
labels as frontier, gate, and evidence-contract views. Policy preparation and
decode previews that still contain wallet or amount placeholders are printed as
`[manual-template]`; sidecar review remains `[review-gated]` until a reviewable
approved corpus exists; only fully local ready commands are eligible for
autorun metadata.

```bash
python3 scripts/inferforge.py transaction-corpus-checklist --no-write --show-commands --show-steps --skip-current-resource-check
```

```bash
python3 scripts/inferforge.py decode-transactions --input .greybox/transaction-payloads.jsonl
python3 scripts/inferforge.py decode-transactions --no-write --input .greybox/transaction-payloads.jsonl
python3 scripts/inferforge.py decode-transactions --input ./approved-payloads.jsonl --max-input-bytes 1048576
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

To write the matching sidecar without sending target traffic, prepare it from
the active profile first:

```bash
python3 scripts/inferforge.py prepare-transaction-intent-policy \
  --direction buy \
  --wallet EzDmLUHTj53mSLN4BBrsuW8w3Gvc1iDGiYCXrkwm4vrR \
  --amount-in 1000000
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

For `buy` and `sell`, InferForge derives expected source and destination mints
from `quote_intent.directions` in the active target profile, unless an explicit
transaction intent policy supplies `sourceMint` and `destinationMint`.
`allowedPrograms` can also live in `quote_intent` or in a specific direction,
and explicit CLI or policy-file allowlists take precedence. The current checks
verify that the decoded transaction has the expected wallet account, the wallet
is a signer, both expected mints appear in static account keys or can be
inferred from token-account metadata when available, compiled instructions are
present, decoded source-mint transfer amounts match `amountIn` when available,
explicit `sourceTokenAccount` and
`destinationTokenAccount` values match decoded SPL transfer accounts, and all
compiled instruction program IDs are in `allowedPrograms` when that allowlist is
configured. Address table lookups can require manual review unless
`transaction-address-tables.json` or `transaction-address-lookups.json` supplies
public lookup-table metadata.
If no `allowedPrograms` policy is configured, transaction corpus and sidecar
reviews now include a `program_allowlist_review.review_package` for each
direction. The package records the decode check to review, required inputs,
pass/fail criteria, policy fields to update, and the finding-gate rule: an
unreviewed decoded program list is not enough for Medium+ promotion. After
reviewing one approved decoded payload, copy only the approved decoded program
IDs into `transaction-intent-policy.json` or the profile direction before
treating program behavior as passed.
When an approved public token-account metadata sidecar is available,
`transaction-token-accounts.json` or `transaction-token-accounts.jsonl` may also
provide rows with `address`, `mint`, and `owner`. Those rows let
`decode-transactions` verify that explicit source and destination token accounts
belong to the expected wallet/recipient and mint. They also let InferForge bind
unchecked SPL Token `transfer` instructions to an inferred mint, and bind the
decoded source-mint debit to the expected wallet owner. Missing token-account
metadata does not create a finding; a concrete owner or mint mismatch is only a
candidate transaction-integrity signal that still has to pass finding-gate and
adjudication.
Explicit token-account boundary checks still compare decoded `transfer` account
edges even when the opcode omits mint; mint and owner attribution stay in review
until public token-account metadata is available.
`transaction-evidence-readiness --show-checks` also prints post-payload review
packages for address lookup coverage, token-account metadata coverage, and
program allowlist review. These packages name the accepted sidecar paths, required
conditions, pass/fail criteria, preview commands where applicable, and the
finding-gate boundary. They are workflow controls only: unresolved lookup-table
or token-account metadata keeps address-dependent claims in review, and missing
metadata by itself is never a Medium+ finding.
`decode-transactions` and `transaction-sidecar-review --show-commands` also
summarize missing token-account metadata and print JSONL template rows for the
public account, mint, and owner values that must be supplied before relying on
offline owner attribution.
Use `prepare-transaction-token-account-metadata --no-write --show-jsonl` to
render those rows as a pending template package. The package is not
`transaction-token-accounts.jsonl` evidence and does not satisfy finding gates;
write the official sidecar only after the public mint/owner rows are manually
approved. To preflight approved rows, pass `--metadata-input` and
`--approval-reference`; `--write-official-sidecar` writes
`transaction-token-accounts.jsonl` only when the rows are public, unpolluted,
approved, and match the decoded metadata requirements.
By default, decoded top-level SPL token transfer instructions must stay within
the expected source and destination mints/accounts. A policy can set
`allowExtraTokenTransfers: true` only after the route's extra token movement is
reviewed; otherwise unexpected transfer mints or unexpected explicit token
account boundaries are treated as candidate transaction-integrity impact. When
token-account metadata is available, same-mint transfers from a non-wallet
source owner or to a non-recipient destination owner are also treated as
unapproved transfer scope.
Compute budget instructions are decoded as well. Set `maxComputeUnitLimit`,
`maxComputeUnitPriceMicroLamports`, and `maxPriorityFeeLamports` in the intent
policy to cap priority-fee exposure; when both unit limit and unit price are
explicit, InferForge estimates the priority fee in lamports and gates values
above policy as candidate user-funds impact.
When an approved quote includes a minimum or expected destination amount, add
`minDestinationAmount` to the intent policy. InferForge sums decoded
destination-mint transfers and gates a concrete shortfall as candidate
transaction-integrity impact; if the output amount is not visible in the
unsigned transaction payload, the check stays in manual review instead of
claiming a finding.
When token-account metadata is available, the destination amount must also be
credited to the expected recipient/wallet owner. A concrete owner or mint
mismatch on the credited destination output is treated as candidate
transaction-integrity impact; missing metadata remains non-finding context.
For paired corpus preparation, `prepare-transaction-corpus-sidecars` can derive
`minDestinationAmount` from a unique positive-integer `amountOut` in the same
approved quote response/payload that supplies `transaction-payloads.jsonl`.
If the approved quote intent input also declares `expected.min_destination_amount`
or a supported alias such as `minDestinationAmount`, it must match that same
derived value. Ambiguous, non-integer, or mismatched output amounts stay in review
and must be approved manually before they are used as the output-amount policy.
`transaction-intent.json.reportability_review` summarizes whether decoded
checks are merely waiting for corpus/policy, passed for the current corpus, or
contain signer, wallet, mint, or program mismatches that are ready for a
separate finding-gate review. It is still a candidate impact signal, not a
reportable finding by itself.

`collect-quote` is the safe quote-corpus helper. It requests the active
profile's quote path, saves a successful quote response to
`.greybox/transaction-payloads.json`, writes `.greybox/quote-collection.json`,
refreshes `.greybox/transaction-intent.json`, updates the related
evidence/readiness artifacts, and refreshes the managed artifact manifest. It
does not sign transactions or submit them to Solana. On constrained hosts it
blocks behind the resource gate before sending the quote request or running
transaction decoding unless `--allow-resource-warning` is passed explicitly.
Evidence gaps, methodology review, and the verification queue prefer the
no-write sidecar/corpus evidence contract first; run `collect-quote` only after
the specific upstream request, wallet, amount, and resource impact are approved.
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
present. MCP inventory failure diagnostics are stored as redacted type,
length, and hash summaries rather than raw exception text. The CLI prints
concise `Burp tools:` and `Burp MCP tool inventory:` lines for unattended setup
checks. Use `--no-write` to preview these checks without refreshing capability
artifacts.

`readiness` writes `.greybox/environment-readiness.json`, combining target
health, profile-declared redacted environment checks, and quote corpus status
only when a quote cluster is active, then refreshes the managed artifact
manifest. `self-test-transactions` writes
`.greybox/transaction-decoder-selftest.json`; it generates a synthetic local
Solana versioned transaction to prove the candidate extractor, decoder, and
intent-policy checks work. The same self-test also covers prepared sidecar
write, sidecar review, no-write decode preview, and synthetic mismatch
finding-gate handoff, but it is not a substitute for a real quote-provider
corpus.

`burp-sync` is the preferred automatic Burp loop. It can force Proxy Intercept
off, optionally run the deterministic `burp-observe` flow, read matching Burp
Proxy HTTP history directly through Burp MCP, import normalized observations,
refresh traffic clustering, write `.greybox/burp-mcp-sync.json`, and refresh the
managed artifact manifest. By default, raw MCP history is imported in memory and
is not persisted; the sync artifact records raw history byte counts and SHA-256
hashes instead. Use `--raw-output`, `--websocket-raw-output`, or
`--keep-raw-history` only when an explicit offline raw-history file is needed.
The default MCP history window is 50 items. `burp-sync` also performs a local
memory/swap resource preflight before observation or history reads; when that
gate is warning, it writes a `blocked-resource-gate` sync artifact and reads no
MCP history unless `--allow-resource-warning` is passed explicitly with a small
`--count`.
The sync artifact includes `mcp_actions`, a compact audit log of Burp MCP tool
calls with sensitive request bodies, regex values, tokens, and secrets hashed or
redacted; MCP exception messages are summarized by type, length, and SHA-256
instead of stored as raw text. Top-level `burp-sync` failure metadata and
Intercept-disable errors use the same redacted error shape.
`burp-sync` first performs a read-only `tools/list` inventory when available,
prefers the regex history tools, and directly selects the non-regex
HTTP/WebSocket history tools when a Burp MCP version does not list the regex
variant. If inventory is unavailable or a listed regex tool still fails, it uses
the older audited regex-then-fallback path. Fallback imports still apply the
local target/profile filters before writing normalized
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
`covered-with-external-blocker`; the latter is expected while the quote
transaction corpus is blocked by placeholder credentials.
Use `evidence-gaps` to refresh gap state and dependent coverage artifacts from
existing local evidence without sending new probes:

```bash
python3 scripts/inferforge.py evidence-gaps
```

When a resource snapshot artifact is present, `evidence-gaps` annotates gaps
that would require active traffic, Burp observation, browser automation, or
WebSocket probes with an `active_followup_status`. The printed follow-up
commands remain no-write/offline previews; an active follow-up marked
`blocked-resource` or `requires-resource-check` must not be run until
`resource-snapshot --strict` is healthy. Use `--current-resource-check` only
when you explicitly want a fresh local `/proc` preflight.

For generated starter profiles, source-discovered surfaces that are intentionally
not actively probed, such as reviewed-only rewrite proxies, are marked
`not-applicable` for safe-probe and policy-field coverage until a Burp
observation or reviewed probe target is added. Their evidence gaps include
review-only observation candidates that state the concrete approval needed
before automation is allowed.

`burp-observation-coverage --no-write` previews the same coverage without
writing artifacts; without `--no-write`, `burp-observation-coverage` writes
`.greybox/burp-observation-coverage.json`. It is a read-only Burp workflow
index that shows, per cluster, whether Burp
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

`source-peek` writes `.greybox/source-peek-results.json` from bounded local
source snippets. It consumes `source-peek-requests.json` when present, resolves
declared source refs and line refs with a per-file byte cap, keeps unresolved
refs explicit, and records when manual deployment/operator evidence is still
required. `source-peek --no-write` previews the same answer summary without
writing target-profile artifacts, source-peek results, traffic indexes, or
manifests.

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
Add `--current-resource-check` before considering active target traffic; when
local memory or swap pressure makes the resource gate unhealthy, active queue
items such as bounded `audit` reruns are marked `blocked-resource` while
offline index/gate commands remain available.
For WebSocket header-forwarding leads, run
`websocket-candidate-review --no-write --show-evidence-contract` to print the
required sensitive-header filters, auth-context status, reportability gates, and
forbidden validation steps without opening sockets or importing Burp history.
When source review finds an unresolved forwarding lead, the same review now
prints and carries a WebSocket header-forwarding approval packet through
`verification-queue`, `validation-plan`, and `iteration-decision`. That packet
requires sensitive client-header context, upstream receipt/trust/logging or
billing evidence, browser/client header-control review, and concrete impact
before any finding-gate escalation; it still forbids WebSocket frames,
subscriptions, wallet payloads, raw secrets, and resource-pressure tests.
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
control operators are present. Commands that reference protected control-plane
ports are also classified as `unsafe-template`; these ports must not appear in
watch-port, readiness, health-check, resource-check, probe, or reclaim command
templates. The CLI and reproduction steps print command safety totals for
runnable, manual-input, external-blocked, unsafe, and placeholder counts so
unattended runs can tell whether commands are ready to execute.
`verification-queue` returns a non-zero status if unsafe command templates are
generated. Human-review and external-configuration states are encoded in the
JSON artifacts; use `review-blockers --strict` when those states should fail a
CI job.

`review-blockers` writes `.greybox/review-blockers.json` plus
`.greybox/review-blockers.md`, a read-only summary of the human-review,
profile-update, and external blockers currently spread across discovery
coverage, Burp observation coverage, verification queue, source-peek requests,
environment readiness, artifact health, and blocked finding-gate previews.
The summary carries the active `assessment_policy`, so a run clearly shows
whether it is optimizing for `greybox` coverage closure or `blackbox` valid
high-bounty impact before ranking the next blocker.
Blocked previews enter the `finding-gate-blocker` category with the missing
evidence, severity, entrypoint, and packet type, but remain explicitly
non-reportable until a real finding gate passes. Each finding-gate blocker also
stores an `unblock_plan` with the nearest evidence artifacts, the first concrete
evidence item to collect, and no-write command templates for the matching
contract: rewrite-response sidecars for fixed-upstream impact, transaction
sidecars and corpus checklists for quote integrity, and operator-evidence
templates for credential/resource impact. The same group summary carries
`oracle_types` plus validation-oracle acceptance and rejection checks, so
`review-blockers --no-write` can show the exact proof model that must pass before
finding-gate or adjudication can accept a Medium+ claim. The run-level
`oracle_summary` also rolls up oracle type/status counts, operator/deployment
dependencies, sidecar or single-observation dependencies, and the current top
oracle. It also summarizes whether the referenced local evidence artifacts are
present and names the first missing artifact for the top oracle. The top oracle
also exposes the compact evidence contract kind and first required sidecar field,
so unattended loops can distinguish "file missing" from the exact proof shape
needed next. This keeps greybox runs focused on remaining coverage evidence
classes while blackbox runs can choose the shortest valid high-impact bounty path
without reading every blocker first. Rewrite-response unblock plans also carry
the selected read-only request, source reference, fixed upstreams,
path-sensitivity score, sidecar path, and redacted required fields, so reviewers
can understand why the path is high-value without re-running the lower-level
rewrite review first. `audit` and
`verification-queue` refresh it automatically.
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

`oracle-plan` turns the validation-oracle blockers into a shorter offline
execution queue. It ranks each oracle by the active objective, bounty/coverage
pressure, evidence-contract availability, missing artifacts, whether the next
step requires operator/deployment evidence, and whether any active traffic must
stay blocked behind approval and a healthy resource gate:

```bash
python3 scripts/inferforge.py oracle-plan --no-write --top 6 --show-details
python3 scripts/inferforge.py oracle-plan
python3 scripts/inferforge.py oracle-plan \
  --check-dir .greybox/regression-default \
  --check-dir .greybox/regression-discovered \
  --no-write
```

The command writes `.greybox/oracle-plan.json` unless `--no-write` is used. It
does not send HTTP requests, query Burp, sign wallets, submit transactions, run
scanners, or perform resource stress validation.

`manifest` writes `.greybox/artifact-manifest.json`, an integrity snapshot with
SHA256 hashes, sizes, modification timestamps, generated-at timestamps, JSONL row
counts, key status summaries, and missing-required-artifact checks. `audit`
generates this manifest as its final write so the manifest covers the rendered
report and index page. Standalone local refresh commands that rewrite existing
top-level artifacts, such as `profile`, `plan`, `collect`, `burp-observe`,
`burp-sync`, `import-burp-history`, `coverage`, `burp-observation-coverage`,
`discovery-coverage`, `response-deltas`, `source-peek`,
`source-peek-requests`,
`source-risk-review`, `evidence-chain`, `evidence-appendix`,
`verification-queue`, `review-blockers`, `oracle-plan`, `gate`, `adjudicate`,
`artifact-health`, `review-candidates`,
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
or raw exception messages, checks `burp-mcp-sync.json` failure and Intercept
error fields plus `burp-observation-run.json` top-level/nested errors for
redacted error summaries, checks probe, warm-up, and Burp observation artifacts
for raw bodies, unredacted body samples, and raw error strings, flags persisted
default raw Burp MCP history files as security hygiene issues,
carries forward key gate statuses such as black-box coverage, discovery
coverage, verification queue, review blockers, response deltas,
source-peek requests, and Burp observation coverage, and
classifies each run as `healthy`, `ready-with-external-blockers`,
`ready-with-evidence-gaps`, `needs-human-review`, or `failed`. Coverage gaps and
`response-deltas` with `no-probe-results` stay visible as
`ready-with-evidence-gaps` instead of hard failures; structural integrity,
staleness, parse, profile, and security-hygiene problems still fail the health
gate. `iteration-decision` blocks active validation only for hard failed
artifact health; manual-review and evidence-gap states remain visible while
command-safety and resource gates control individual active commands. When it
writes `artifact-health.json` inside a managed artifact directory, it refreshes
that directory's manifest so the health artifact does not make the next
integrity check stale. When stale inputs exist, the CLI prints the first few
affected files with their reason, newer inputs, and suggested refresh command. It
is useful after regression runs:

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
coverage, command-safety, review-blocker, artifact-health, source-risk,
regression-offline-safety, and manifest-refresh, no-write, Burp sync failure,
and transaction-decoder self-tests, refresh static discovery, run offline
`source-risk-review` and a passive `lead-portfolio`, check that the discovered
profile covers every static surface or review gate, run deterministic Burp
observe/sync for the checked-in profile and discovered profile, collect one
source-known Orca pool baseline, run both audits, write artifact health, and
then generate a root-level review-blocker rollup, `regression-suite.json`, and a
refreshed root `artifact-manifest.json`. The final log prints step counts,
artifact-health gate counts including `security_issues`, review-blocker counts,
and the top
grouped review blockers so unattended runs surface both health gates and next
actions directly. `regression-suite.json` stores step output as byte, hash, and
line-count summaries rather than raw command stdout; step and preparation
failure errors use the same redacted type/length/hash shape as Burp MCP error
artifacts. Probe and warm-up artifacts do not store full response `body_text`;
they keep response hashes, lengths, truncation flags, and bounded redacted body
samples for grouping and reproduction context, and transport errors are stored
as type, length, and hash summaries rather than raw exception text. Target probe
lock artifacts use the same blocked-error shape. It clears only generated
`probe-results.jsonl` files in the selected regression artifact directories
before audit so reruns do not accumulate stale probe rows. It does not run Burp
Scanner, fuzz broadly, invoke Server Actions, sign wallets, or submit
transactions.

On constrained VPS hosts, `regression-suite` now blocks at startup while the
resource gate is warning unless `--allow-resource-warning` is passed. This avoids
queuing self-tests, Burp observe/sync, Orca baselines, active audits, and report
rollups when swap pressure is already high.

During tool development, prefer the offline mode first:

```bash
python3 scripts/inferforge.py regression-suite --offline-only --plan-only
python3 scripts/inferforge.py regression-suite --offline-only
```

`--plan-only` writes `regression-suite.json` with `planned` steps but does not
execute subcommands or clear probe artifacts. `--offline-only` forces the suite
to skip Burp observe/sync, active audit probes, Orca baseline collection,
external probes, WebSocket resource probes, and non-local observation traffic.
It still allows static self-tests, source/profile discovery, discovery coverage,
offline source-risk review, passive lead portfolio generation, artifact health,
review-blocker rollups, and local report rendering from existing artifacts. The
generated suite artifact records `offline_only`,
`plan_only`, and the disabled action list so unattended runs can verify the
development-safe boundary before executing anything active.

```bash
python3 scripts/inferforge.py regression-suite --include-external --ws-resource-probes
```

Use `--skip-self-tests`, `--skip-discovery-coverage`, `--skip-review-blockers`,
`--skip-burp-sync`, `--skip-orca-baseline`, `--skip-audit`, or
`--skip-discovered` for narrower local checks. Combine those skip flags with
`--allow-resource-warning` only after explicit review. Use `--strict` when
human-review or external-configuration blockers should fail the command.

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
host. Each raw input is capped at 4 MiB by default so a large saved Burp export
does not create a memory spike on small VPS hosts; raise `--max-input-bytes`
only after reviewing the file and available memory. Successful imports write
normalized observations to:

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
python3 scripts/inferforge.py import-burp-history --input .greybox/burp-mcp-history.txt --max-input-bytes 1048576
```

If you intentionally persist raw MCP history for offline debugging, keep it out
of shared artifacts. `artifact-health` treats the default raw history filenames
as security hygiene issues because they can contain request headers, cookies, and
full response bodies.

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
.greybox/burp-sync-failure-selftest.json
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
.greybox/probe-results-summary.json
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
.greybox/source-risk-review.json
.greybox/source-risk-review-selftest.json
.greybox/bounty-program-profile-selftest.json
.greybox/regression-offline-safety-selftest.json
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
connection references, and the observed high-impact method probe results. The
same artifact also records static remote-transaction material references, such
as base64 transaction extraction or `VersionedTransaction.deserialize`, and
adds a `remote_transaction_signing_review` gate when those references can flow
toward wallet signing calls. This is only a prompt to collect and decode an
approved transaction corpus; it is not reportable without decoded intent
mismatch or equivalent user-funds impact evidence.

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
addresses and does not store the full response body. It also blocks behind the
resource gate before sending the baseline request unless
`--allow-resource-warning` is passed explicitly. When this baseline is
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
- Codex can send approved MCP HTTP requests to `127.0.0.1:3100` when the local
  target app is running; this is the default app target port, not the Burp Proxy
  listener or Burp's built-in browser.
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
