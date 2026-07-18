from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourcePattern:
    kind: str
    pattern: str
    label: str


@dataclass(frozen=True)
class FlowRule:
    id: str
    title: str
    description: str
    cwe: str
    owasp: str
    severity: str
    sink_patterns: tuple[str, ...]
    source_kinds: tuple[str, ...]
    control_patterns: tuple[str, ...]
    remediation: str
    verification_questions: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class StaticRule:
    id: str
    title: str
    description: str
    cwe: str
    owasp: str
    severity: str
    patterns: tuple[str, ...]
    remediation: str
    verification_questions: tuple[str, ...]
    tags: tuple[str, ...]
    confidence: str = "high"


SOURCE_PATTERNS: tuple[SourcePattern, ...] = (
    SourcePattern(
        "request-input",
        r"\b(?:req|request|ctx)\s*\.\s*(?:query|body|params|headers|cookies|files)\b",
        "HTTP request data",
    ),
    SourcePattern(
        "request-input",
        r"\b(?:req|request)\s*\.\s*(?:json|formData|text)\s*\(",
        "HTTP request body",
    ),
    SourcePattern(
        "request-input",
        r"\b(?:searchParams|url\.searchParams)\s*\.\s*get\s*\(",
        "URL query parameter",
    ),
    SourcePattern(
        "request-input",
        r"\brequest\s*\.\s*(?:args|form|json|values|headers|cookies|files)\b",
        "Python request data",
    ),
    SourcePattern(
        "request-input",
        r"\brequest\s*\.\s*get_json\s*\(",
        "Python JSON request body",
    ),
    SourcePattern(
        "request-input",
        r"\b(?:request|servletRequest)\s*\.\s*get(?:Parameter|Header|Cookies?)\s*\(",
        "Servlet request data",
    ),
    SourcePattern(
        "request-input",
        r"\$_(?:GET|POST|REQUEST|COOKIE|FILES|SERVER)\b",
        "PHP request data",
    ),
    SourcePattern(
        "request-input",
        r"\bparams\s*(?:\[|\.require\s*\(|\.permit\s*\()",
        "Rails request parameters",
    ),
    SourcePattern(
        "request-input",
        r"\b(?:c|ctx|r)\s*\.\s*(?:Query|Param|FormValue|PostForm|GetHeader)\s*\(",
        "Go request data",
    ),
    SourcePattern(
        "message-input",
        r"\b(?:event|message|msg)\s*\.\s*data\b",
        "browser or message-bus data",
    ),
    SourcePattern(
        "external-response",
        r"\b(?:response|res|result|upstream)\s*\.\s*(?:json|text|data)\b",
        "external service response",
    ),
    SourcePattern(
        "external-response",
        r"\bawait\s+(?:fetch|axios\.|requests\.|httpx\.)",
        "external service response",
    ),
)


FLOW_RULES: tuple[FlowRule, ...] = (
    FlowRule(
        id="IFW001",
        title="Untrusted data reaches an operating-system command sink",
        description="A request or message-derived value appears to reach command execution.",
        cwe="CWE-78",
        owasp="A03:2021 Injection",
        severity="critical",
        sink_patterns=(
            r"\b(?:child_process\.)?(?:exec|execSync)\s*\(",
            r"\b(?:os\.)?(?:system|popen)\s*\(",
            r"\bsubprocess\.(?:run|Popen|call|check_call|check_output)\s*\(",
            r"\bRuntime\.getRuntime\(\)\.exec\s*\(",
            r"\bProcessBuilder\s*\(",
        ),
        source_kinds=("request-input", "message-input", "external-response"),
        control_patterns=(r"\ballowlist\b", r"\bwhitelist\b", r"\bshellescape\b", r"\bescapeshellarg\b"),
        remediation="Replace shell composition with an argument-vector API and a strict operation allowlist.",
        verification_questions=(
            "Can an attacker-controlled metacharacter alter the executed program or arguments?",
            "Does execution occur in a worker, container, or privileged runtime with additional impact?",
        ),
        tags=("injection", "command-execution"),
    ),
    FlowRule(
        id="IFW002",
        title="Untrusted data reaches a database query sink",
        description="A request-derived value appears to enter a raw SQL or query expression.",
        cwe="CWE-89",
        owasp="A03:2021 Injection",
        severity="high",
        sink_patterns=(
            r"\b(?:query|execute|executemany|raw|whereRaw|orderByRaw|havingRaw)\s*\(",
            r"\$(?:queryRawUnsafe|executeRawUnsafe)\s*\(",
            r"\bcreateNativeQuery\s*\(",
            r"\bStatement\.execute(?:Query|Update)?\s*\(",
        ),
        source_kinds=("request-input", "message-input"),
        control_patterns=(
            r"\bparameteriz",
            r"\bpreparedstatement\b",
            r"\bprepare\s*\(",
            r"\bplaceholder",
            r"\ballowed_(?:columns|fields|sort)",
        ),
        remediation="Use a parameterized query and map non-value fragments such as sort fields through an allowlist.",
        verification_questions=(
            "Is the tainted value bound as data, or concatenated into query syntax?",
            "For identifiers and sort clauses, is there a closed server-side mapping?",
        ),
        tags=("injection", "database"),
    ),
    FlowRule(
        id="IFW003",
        title="Untrusted data controls a server-side outbound request",
        description="A request-derived URL, host, or path appears to reach an HTTP client.",
        cwe="CWE-918",
        owasp="A10:2021 Server-Side Request Forgery",
        severity="high",
        sink_patterns=(
            r"\bfetch\s*\(",
            r"\baxios\.(?:get|post|put|patch|delete|request)\s*\(",
            r"\brequests\.(?:get|post|put|patch|delete|request)\s*\(",
            r"\bhttpx\.(?:get|post|put|patch|delete|request)\s*\(",
            r"\burllib\.request\.urlopen\s*\(",
            r"\bhttp\.(?:Get|Post)\s*\(",
            r"\bRestTemplate\b.*\.(?:getForObject|exchange)\s*\(",
            r"\bWebClient\b.*\.uri\s*\(",
        ),
        source_kinds=("request-input", "message-input"),
        control_patterns=(
            r"\ballowlist\b",
            r"\bwhitelist\b",
            r"\bhostname\b",
            r"\bprivate[_-]?(?:ip|network)\b",
            r"\bisloopback\b",
            r"\bisprivate\b",
            r"\bdns\b.*\brebind",
        ),
        remediation=(
            "Resolve outbound destinations from server-owned identifiers, and enforce scheme, host, port, "
            "redirect, DNS, and private-address policy at the final connection."
        ),
        verification_questions=(
            "Can redirects or DNS rebinding escape the validated destination?",
            "Can the request reach loopback, link-local, cloud metadata, or an internal control plane?",
        ),
        tags=("ssrf", "outbound-request"),
    ),
    FlowRule(
        id="IFW004",
        title="Untrusted data reaches a filesystem path sink",
        description="A request-derived filename or path appears to reach a filesystem operation.",
        cwe="CWE-22",
        owasp="A01:2021 Broken Access Control",
        severity="high",
        sink_patterns=(
            r"\b(?:readFile|readFileSync|createReadStream|sendFile|download)\s*\(",
            r"\b(?:writeFile|writeFileSync|createWriteStream|unlink|rm)\s*\(",
            r"\b(?:open|send_file|send_from_directory)\s*\(",
            r"\bFiles\.(?:read|write|delete|newInputStream|newOutputStream)\s*\(",
            r"\bos\.(?:Open|ReadFile|WriteFile|Remove)\s*\(",
        ),
        source_kinds=("request-input", "message-input"),
        control_patterns=(
            r"\brealpath\b",
            r"\bresolve\s*\(",
            r"\brelative\s*\(",
            r"\bbasename\b",
            r"\bsecure_filename\b",
            r"\bstartsWith\s*\(",
            r"\bis_relative_to\b",
        ),
        remediation="Resolve against a fixed root, reject absolute/traversal paths, and verify the canonical result stays below that root.",
        verification_questions=(
            "Do encoded separators, alternate separators, symlinks, or archive entries escape the intended root?",
            "Does the same path control apply to both read and write operations?",
        ),
        tags=("path-traversal", "filesystem"),
    ),
    FlowRule(
        id="IFW005",
        title="Untrusted data reaches an HTML rendering sink",
        description="Request or message data appears to be rendered as HTML without a proven encoding boundary.",
        cwe="CWE-79",
        owasp="A03:2021 Injection",
        severity="high",
        sink_patterns=(
            r"\bdangerouslySetInnerHTML\b",
            r"\b(?:innerHTML|outerHTML)\s*=",
            r"\bdocument\.write\s*\(",
            r"\bMarkup\s*\(",
            r"\bmark_safe\s*\(",
            r"\bhtml_safe\b",
            r"\bres\.(?:send|end)\s*\(",
        ),
        source_kinds=("request-input", "message-input", "external-response"),
        control_patterns=(r"\bDOMPurify\b", r"\bsanitize", r"\bescape(?:Html)?\b", r"\bbleach\b"),
        remediation="Keep untrusted values in auto-escaped template/text contexts or sanitize with a context-appropriate policy.",
        verification_questions=(
            "Which browser parsing context receives the value: HTML, attribute, URL, script, or CSS?",
            "Can stored or upstream-controlled data reach the same sink for another user?",
        ),
        tags=("xss", "rendering"),
    ),
    FlowRule(
        id="IFW006",
        title="Untrusted data controls a redirect destination",
        description="A request-derived value appears to reach a redirect response.",
        cwe="CWE-601",
        owasp="A01:2021 Broken Access Control",
        severity="medium",
        sink_patterns=(r"\b(?:res\.|response\.)?redirect\s*\(", r"\bRedirectResponse\s*\("),
        source_kinds=("request-input", "message-input"),
        control_patterns=(r"\ballowlist\b", r"\bsame[_-]?origin\b", r"\bstartsWith\s*\(\s*['\"]/"),
        remediation="Accept only server-owned route identifiers or validated same-origin relative paths.",
        verification_questions=(
            "Are protocol-relative, encoded, backslash, or user-info URL forms accepted?",
            "Does the redirect participate in OAuth, SSO, password reset, or another credential-bearing flow?",
        ),
        tags=("open-redirect", "navigation"),
    ),
    FlowRule(
        id="IFW007",
        title="Untrusted data reaches a server-side template compiler",
        description="A request-derived template string appears to be compiled or rendered dynamically.",
        cwe="CWE-1336",
        owasp="A03:2021 Injection",
        severity="critical",
        sink_patterns=(
            r"\brender_template_string\s*\(",
            r"\b(?:ejs|pug|handlebars|mustache)\.(?:render|compile)\s*\(",
            r"\bTemplate\s*\(",
            r"\bcreateTemplate\s*\(",
        ),
        source_kinds=("request-input", "message-input", "external-response"),
        control_patterns=(r"\bsandbox", r"\bStrictUndefined\b"),
        remediation="Render only fixed server-owned templates; pass untrusted content solely as template data.",
        verification_questions=(
            "Can template expressions access objects, files, environment values, or process execution?",
            "Is the template persisted or rendered for a higher-privileged user?",
        ),
        tags=("template-injection", "code-execution"),
    ),
    FlowRule(
        id="IFW008",
        title="Untrusted data reaches dynamic code evaluation",
        description="A request or message-derived value appears to reach a dynamic language evaluator.",
        cwe="CWE-95",
        owasp="A03:2021 Injection",
        severity="critical",
        sink_patterns=(
            r"(?<![\w.])eval\s*\(",
            r"\bnew\s+Function\s*\(",
            r"\bexec\s*\(",
            r"\bcompile\s*\(",
            r"\bScriptEngine\b.*\.eval\s*\(",
        ),
        source_kinds=("request-input", "message-input", "external-response"),
        control_patterns=(r"\bast\.literal_eval\b", r"\bsandbox\b", r"\ballowlist\b"),
        remediation="Remove dynamic evaluation and map a closed set of operations to explicit implementations.",
        verification_questions=(
            "What globals, modules, or capabilities are available to evaluated code?",
            "Can encoding or object-graph tricks bypass a claimed sandbox?",
        ),
        tags=("code-injection", "code-execution"),
    ),
    FlowRule(
        id="IFW009",
        title="Untrusted data reaches an unsafe deserializer",
        description="An attacker-controlled serialized value appears to be deserialized by a general object loader.",
        cwe="CWE-502",
        owasp="A08:2021 Software and Data Integrity Failures",
        severity="critical",
        sink_patterns=(
            r"\bpickle\.loads?\s*\(",
            r"\byaml\.(?:load|unsafe_load)\s*\(",
            r"\bObjectInputStream\s*\(",
            r"\bBinaryFormatter\b.*\.Deserialize\s*\(",
            r"\bMarshal\.load\s*\(",
            r"\bunserialize\s*\(",
        ),
        source_kinds=("request-input", "message-input", "external-response"),
        control_patterns=(r"\bSafeLoader\b", r"\bsafe_load\b", r"\ballowed[_-]?(?:types|classes)\b"),
        remediation="Use a data-only format and schema; never deserialize attacker-controlled object graphs.",
        verification_questions=(
            "Which classes or hooks can execute during deserialization?",
            "Is integrity/authenticity verified before parsing, and can keys be reused across trust domains?",
        ),
        tags=("deserialization", "code-execution"),
    ),
    FlowRule(
        id="IFW010",
        title="Untrusted data reaches a directory or search filter",
        description="A request-derived value appears to enter an LDAP/search filter expression.",
        cwe="CWE-90",
        owasp="A03:2021 Injection",
        severity="high",
        sink_patterns=(r"\b(?:ldap\.)?(?:search|search_s|search_ext)\s*\(", r"\bLdapTemplate\.search\s*\("),
        source_kinds=("request-input", "message-input"),
        control_patterns=(r"\bescape_filter_chars\b", r"\bencodeForLDAP\b", r"\bfilter\.encode"),
        remediation="Use the directory client's parameterized filter builder or its LDAP-specific escaping routine.",
        verification_questions=(
            "Can filter metacharacters alter predicate scope or returned attributes?",
            "Does the bound directory identity expose privileged records?",
        ),
        tags=("injection", "ldap"),
    ),
    FlowRule(
        id="IFW011",
        title="Untrusted data reaches an HTTP response header",
        description="A request-derived value appears to control a response header or cookie attribute.",
        cwe="CWE-113",
        owasp="A03:2021 Injection",
        severity="medium",
        sink_patterns=(
            r"\b(?:res|response)\.(?:set|setHeader|header|append)\s*\(",
            r"\bheaders\.set\s*\(",
        ),
        source_kinds=("request-input", "message-input"),
        control_patterns=(r"\breject.*(?:newline|crlf)", r"\bencodeURIComponent\b"),
        remediation="Map header values from server-owned data and reject carriage-return/newline characters.",
        verification_questions=(
            "Does the framework reject CR/LF before emitting the response?",
            "Can the value alter cache, CORS, CSP, Location, or Set-Cookie behavior?",
        ),
        tags=("header-injection", "response"),
    ),
    FlowRule(
        id="IFW012",
        title="Untrusted data reaches a signing or transaction-submission sink",
        description="Request or upstream-controlled transaction data appears to be signed or submitted without proven intent checks.",
        cwe="CWE-345",
        owasp="A08:2021 Software and Data Integrity Failures",
        severity="high",
        sink_patterns=(
            r"\b(?:signTransaction|sendTransaction|signAndSendTransaction|signTypedData)\s*\(",
            r"\bwallet\.(?:sign|send|submit)\w*\s*\(",
            r"\bsigner\.(?:sign|send)\w*\s*\(",
        ),
        source_kinds=("request-input", "external-response", "message-input"),
        control_patterns=(
            r"\bexpected_(?:recipient|amount|chain|token)\b",
            r"\bverify[_-]?(?:intent|transaction|calldata)\b",
            r"\ballowlist\b",
            r"\bsimulat",
        ),
        remediation=(
            "Reconstruct or decode the transaction locally and bind chain, recipient, asset, amount, calldata, "
            "spender, and expiry to the user's displayed intent before signing."
        ),
        verification_questions=(
            "Which economically meaningful fields are derived from an upstream or browser message?",
            "Can a compromised upstream or same-origin component alter those fields while preserving the displayed intent?",
        ),
        tags=("transaction-integrity", "web3", "client-trust"),
    ),
    FlowRule(
        id="IFW013",
        title="Untrusted object reaches a bulk model update",
        description="A complete request object appears to be assigned into a persistence model.",
        cwe="CWE-915",
        owasp="A01:2021 Broken Access Control",
        severity="high",
        sink_patterns=(
            r"\.(?:create|update|updateOne|findOneAndUpdate|assign_attributes|fill)\s*\(",
            r"\bModelMapper\b",
        ),
        source_kinds=("request-input",),
        control_patterns=(
            r"\bpick\s*\(",
            r"\bpermit\s*\(",
            r"\ballowed[_-]?fields\b",
            r"\bdto\b",
            r"\bschema\b",
        ),
        remediation="Copy a closed list of writable fields into a dedicated input object before persistence.",
        verification_questions=(
            "Can protected fields such as role, owner, tenant, status, balance, or approval be supplied?",
            "Do nested objects or alternate content types bypass the visible allowlist?",
        ),
        tags=("mass-assignment", "authorization"),
    ),
)


STATIC_RULES: tuple[StaticRule, ...] = (
    StaticRule(
        id="IFC001",
        title="TLS certificate verification is disabled",
        description="The code disables certificate or hostname verification for an outbound connection.",
        cwe="CWE-295",
        owasp="A07:2021 Identification and Authentication Failures",
        severity="high",
        patterns=(
            r"\bverify\s*=\s*False\b",
            r"\brejectUnauthorized\s*:\s*false\b",
            r"\bInsecureSkipVerify\s*:\s*true\b",
            r"\bsetHostnameVerifier\s*\(\s*(?:ALLOW_ALL|NoopHostnameVerifier)",
        ),
        remediation="Use platform certificate and hostname verification; install the intended private CA explicitly when needed.",
        verification_questions=("Is the code reachable in production or only in an isolated test fixture?",),
        tags=("tls", "configuration"),
    ),
    StaticRule(
        id="IFC002",
        title="Token signature verification is disabled",
        description="JWT or signed-token decoding is configured to skip signature verification.",
        cwe="CWE-347",
        owasp="A07:2021 Identification and Authentication Failures",
        severity="critical",
        patterns=(
            r"\bverify_signature['\"]?\s*[:=]\s*(?:False|false)",
            r"\bverify\s*:\s*false\b.{0,120}\bjwt\b",
            r"\bjwt\.decode\s*\([^)]*options\s*=\s*\{[^}]*verify_signature[^}]*False",
        ),
        remediation="Verify the signature, issuer, audience, algorithm, lifetime, and token type before using any claim.",
        verification_questions=(
            "Does an unsigned or attacker-signed token reach an authenticated principal?",
        ),
        tags=("jwt", "authentication"),
    ),
    StaticRule(
        id="IFC003",
        title="Credentialed CORS appears to allow every origin",
        description="Wildcard origin policy is combined with credentialed cross-origin requests.",
        cwe="CWE-942",
        owasp="A05:2021 Security Misconfiguration",
        severity="high",
        patterns=(
            r"(?s)(?:origin|allow_origins?)\s*[:=]\s*(?:['\"]\*['\"]|\[['\"]\*['\"]\]).{0,500}"
            r"(?:credentials|supports_credentials|allow_credentials)\s*[:=]\s*(?:true|True)",
            r"(?s)(?:credentials|supports_credentials|allow_credentials)\s*[:=]\s*(?:true|True).{0,500}"
            r"(?:origin|allow_origins?)\s*[:=]\s*(?:['\"]\*['\"]|\[['\"]\*['\"]\])",
        ),
        remediation="Allow only exact trusted origins and keep credential support disabled for public cross-origin resources.",
        verification_questions=(
            "Does the framework reflect arbitrary Origin values despite rejecting a literal wildcard?",
        ),
        tags=("cors", "configuration"),
    ),
    StaticRule(
        id="IFC004",
        title="Application debug mode appears enabled",
        description="A production-capable application path enables debug behavior.",
        cwe="CWE-489",
        owasp="A05:2021 Security Misconfiguration",
        severity="medium",
        patterns=(
            r"\bapp\.run\s*\([^)]*debug\s*=\s*True",
            r"\bDEBUG\s*=\s*True\b",
            r"\buseDeveloperExceptionPage\s*\(",
        ),
        remediation="Select debug behavior only from an explicitly local development profile and fail closed in production.",
        verification_questions=(
            "Can remote users reach an interactive debugger, stack trace, source excerpt, or secret-bearing error page?",
        ),
        tags=("debug", "information-disclosure"),
    ),
    StaticRule(
        id="IFC005",
        title="YAML is loaded with an unsafe object constructor",
        description="The YAML loader may instantiate arbitrary language objects.",
        cwe="CWE-502",
        owasp="A08:2021 Software and Data Integrity Failures",
        severity="high",
        patterns=(
            r"\byaml\.unsafe_load\s*\(",
            r"\byaml\.load\s*\([^)]*Loader\s*=\s*yaml\.(?:Loader|UnsafeLoader)",
        ),
        remediation="Use a safe/data-only loader and validate the resulting structure against a schema.",
        verification_questions=("Can an attacker influence the YAML bytes or select the parsed document?",),
        tags=("deserialization", "yaml"),
    ),
    StaticRule(
        id="IFC006",
        title="A likely secret is hard-coded in source",
        description="A high-entropy credential-like assignment appears in a source file.",
        cwe="CWE-798",
        owasp="A07:2021 Identification and Authentication Failures",
        severity="high",
        patterns=(
            r"(?i)\b(?:api[_-]?key|client[_-]?secret|private[_-]?key|access[_-]?token|password)\b"
            r"\s*[:=]\s*['\"][A-Za-z0-9_./+=:-]{16,}['\"]",
            r"\bAKIA[0-9A-Z]{16}\b",
            r"\bghp_[A-Za-z0-9]{30,}\b",
            r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        ),
        remediation="Remove the value from source and history, rotate it, and load a scoped credential from a secret manager.",
        verification_questions=("Is the value live, privileged, or present in released history/artifacts?",),
        tags=("secret", "credential"),
    ),
    StaticRule(
        id="IFC007",
        title="A session cookie is configured without a security attribute",
        description="Cookie construction explicitly disables Secure, HttpOnly, or SameSite protection.",
        cwe="CWE-614",
        owasp="A05:2021 Security Misconfiguration",
        severity="medium",
        patterns=(
            r"(?i)\b(?:httpOnly|httponly)\s*[:=]\s*false\b",
            r"(?i)\bsecure\s*[:=]\s*false\b.{0,160}\b(?:session|auth|token|cookie)\b",
            r"(?i)\bsameSite\s*[:=]\s*['\"]none['\"].{0,160}\bsecure\s*[:=]\s*false\b",
        ),
        remediation="Set Secure and HttpOnly for authentication cookies and choose the narrowest viable SameSite policy.",
        verification_questions=(
            "Is the affected cookie authentication-bearing and emitted in a production profile?",
        ),
        tags=("cookie", "session"),
    ),
    StaticRule(
        id="IFC008",
        title="A weak password or signature hash is selected",
        description="MD5 or SHA-1 appears in a security-sensitive hashing call.",
        cwe="CWE-327",
        owasp="A02:2021 Cryptographic Failures",
        severity="medium",
        patterns=(
            r"\b(?:hashlib\.)?(?:md5|sha1)\s*\(",
            r"\bMessageDigest\.getInstance\s*\(\s*['\"](?:MD5|SHA-?1)['\"]",
            r"\bcrypto\.createHash\s*\(\s*['\"](?:md5|sha1)['\"]",
        ),
        remediation="Use a modern construction appropriate to the purpose: Argon2id/scrypt for passwords, SHA-256+ for digests, or HMAC/signatures for authenticity.",
        verification_questions=(
            "Is this used for passwords, signatures, token integrity, or only a non-security cache key?",
        ),
        tags=("cryptography", "weak-hash"),
        confidence="medium",
    ),
)


def rule_catalog() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "flow_rules": [asdict(rule) for rule in FLOW_RULES],
        "static_rules": [asdict(rule) for rule in STATIC_RULES],
        "source_patterns": [asdict(pattern) for pattern in SOURCE_PATTERNS],
        "semantics": {
            "candidate_not_finding": True,
            "static_absence_not_proof": True,
            "confirmation_requires_independent_verification": True,
        },
    }
