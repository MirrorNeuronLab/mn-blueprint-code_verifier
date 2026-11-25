# Software verifier suite specification

## Reviewing the suite report

Choose **Sample dispatch review** for a fictional comparison with recorded evidence, or select your own source. To add case observations, put the independently recorded ledger in **Runner evidence folder** as `<sha256>.json` and enter its digest in **Case evidence SHA-256**. Each specialist receives its own cases. A removed or late specialist leaves its section incomplete. The coordinator retains late replies under their originating review.

The five views use the shared offline report template. The first view shows the release decision, the comparison checks with receipts, and the approved passages each case covers. **Verified defects** counts distinct repeatable behavior. Configuration mismatches and test controls have separate evidence. **Actions** offers **Print all sections**, **Export HTML** and the **Evidence explorer** for detailed checks and source review.

Optionally supply **Report context SHA-256** to identify the collection method, link implementation lines and bind existing tests, lint, CI, AI review or a proposed test repair to the exact run records. Missing comparisons stay unmeasured. Changing an approved requirement invalidates its passage-based case match.

See the [dispatch example](examples/dispatch_review/README.md) for the ledger contract.

Verification opens with developer findings and the specification-to-test evidence for each approved behavior. A prepared Git comparison can be selected by the coordinator or any specialist. Both snapshots use the same protected criteria. A finding distinguishes impact, confidence, inspected locations and remaining uncertainty. The structured report preserves the revision, case history and evidence references.

For tests generated from analysis documents, attach the generator’s requirement-to-test index or review the links against frozen document passages. Bulk CI results retain the entire case inventory and distinguish verified passage links from suite-level provenance. Inspect the specialist tabs for named cases, prompts for unresolved coverage and supporting measurements.

Hiring Software verifier suite in OtterDesk connects its coordinator and four independently runnable co-workers on one collaboration board. Hiring leaves every co-worker idle. Start the coordinator when you have a source to review. After you approve its rules, each assignment starts a run for the selected specialist. Remove a specialist from Collaboration to leave its checks uncovered. Archiving the coordinator archives the original suite hires. Select a source folder and optionally supply a supervisor-owned verification scope. The coordinator captures the source once, waits for approval of the rule revision, then runs the source review alongside the selected specialist checks. Open the published web report to see the overall verdict and five evidence views.

| Report section | Evidence owner |
| --- | --- |
| Functional intent | Functional verifier compares requirements and observed workflow outcomes. |
| Verified defects | The coordinator groups matching failures with at least two consistent clean runs of a single case and fixture. |
| Integration and regression | Compatibility verifier compares service stages on the baseline and candidate. |
| Security and authorization | Security verifier compares recorded decisions with the approved access policy. |
| Independent test quality | Reliability verifier inspects test oracles, measured coverage and independent mutation controls. |

The dispatch sample supplies observations for all five sections. An unselected specialist has a visible skip reason. Each check records its criterion, attempt history and supporting evidence. For test suites, builds or platforms outside the built-in checks, supply independently pinned execution records through **Runner evidence folder**. The source review can require further investigation even when every selected deterministic check passes.

For a repair, supply a different candidate and the SHA-256 of the preceding nonpassing report in `repair_of`. Put the report bytes in the evidence folder as `<digest>.json`. The protected criteria stay fixed and up to two candidate revisions are linked. A merge or release scope requires integrated, target-specific evidence. The co-worker publishes the decision and leaves promotion to its owner.

## Activity-based run supervision

The workflow declares `execution.supervision: "activity"`. Matching Core and SDK
supervise process liveness and real packet/model progress without phase-wide
elapsed limits. Extraction and verification time allowances default to `null`;
operators may still set an explicit 1–3600 second computation budget. Individual
model requests remain bounded to 90 seconds; packet, retry, rule and turn limits
still apply. Human review retains its bounded approval expiry and advertises a
waiting state rather than stalled computation. Completion remains a durable
runtime receipt.

Version 3.1.0 changes only this blueprint and its offline code-search/static-analysis
skills. Use the updated skills and prepare a fresh Job/run with the existing runtime.
Existing reports and accepted-run checkpoints retain their original policy; a new
policy cannot resume an old investigation or reuse its approval.

## Mission and outputs

The coordinator uses the runtime’s shared default model. Its CPU and RAM
requirements describe the minimum size of the execution computer. Specialists
need CPU and RAM to inspect their assigned evidence. The coordinator permits
one outstanding assignment, verifies the published report, then advances to
the next connected role. An expired reply deadline stops further dispatch.

Given a local repository checkout or plain software folder, read complete captured
`SPEC.md`/`spec.md`, Markdown, reStructuredText and text documentation; extract
atomic intended behaviors, constraints and prohibitions; apply supervisor-authored
Markdown from Job knowledge; obtain supervisor approval of the exact list in
OtterDesk Chat; verify each approved rule independently against
captured implementation; publish an editable Markdown list and evidence table.

Version 3.4.0 also accepts a prepared Git comparison as the selected local
folder. The host-side helper reads two local commits and exports bounded source
trees, their digests and full commit SHAs. Capture checks both staged digests.
The folder supplies the identity of the local Git comparison. The workflow
reads staged source and leaves program and test execution to the repository owner.
The optional specification path list narrows extraction to exact captured
proposed-commit documents; investigation can use all captured code.

The existing approval binds the exact proposed rules, comparative capture and
any CI receipt. Verification applies those same rules to each frozen revision,
with changed code prioritized for retrieval. A new regression requires a base
Pass, a proposed Fail and a cited changed implementation or configuration
span. If the base is Unknown or the relationship to a change is unresolved,
that distinction remains explicit. Base evidence and checkpoints are kept
alongside proposed evidence. Plain-folder reviews retain their single snapshot.

The preparation helper may attach mapped JUnit observations. Its supplied CI
commit must exactly equal the proposed commit SHA. The receipt retains the
JUnit filename and digest and captures only mapped test names and outcomes.
A skipped, missing or mixed outcome remains explicit. A replaced rule statement
requires the mapping to be reviewed again. CI evidence never changes the
static verdict, model evidence or approval state.

**Start from sample data** selects the bundled dispatch comparison and its recorded
evidence. **Use your own data** asks for one source code folder. Selecting it starts
the coordinator with the current requirements and any custom rules. Rules mode,
specification paths, runner evidence and the output folder are optional in
Configure. The coordinator plans specialist checks after approval of the exact
rule list on either path.

Core schedules capture, extraction and rule review in order. After approval, source review and specialist coordination can run in parallel. Publication waits for both branches. The Rust coordinator returns bounded child-plan proposals to Core. Each admitted child receives only its mapped work packet, its invocation identity and its declared WIT grants.

The SDK stages local folders according to the blueprint exclusions and verifies each declared skill digest before composition. The executor verifies each staged input against its inventory and creates a private WASI invocation directory.

## Rule contract

Extraction, source-repair and investigation calls send their response schemas
through the SDK's structured-output API. Structural validation cannot replace
exact source admission or supervisor approval. Explicit fake-model execution may
return an empty extraction or Unknown judgments; it establishes no conformance
result and retains the same human review gate.

Verification returns an object containing `decision`; its nested union selects
search, read or finish. Every branch uses explicit action/status types. A root
union must not be sent to strict model routes. Trusted code unwraps the decision
before applying the unchanged source-evidence and confidence checks.

The supervisor's digest-addressed Markdown review document is committed as a
host-readable shared artifact before its Core interaction is published. Replay
verifies identical bytes; private checkpoints keep private permissions.
Editable `rules.md` uses the same host-readable permissions on each replacement.
Final reports use the SDK publication adapter to verify delivery and register
receipt-backed runtime downloads, including the editable rules document.

`knowledge/rules/*.md` contains `## RULE-ID` or `## RULE-ID — Short title` sections
and Markdown statement bodies. Titles are at most 120 UTF-16 units; statements
are at most 4,000 UTF-8 bytes. Exported rules retain their titles and stable IDs.
Each ID is unique across files. Empty files are allowed. A malformed rule file
fails visibly. Augment combines extracted rules and custom rules, with custom
IDs overriding generated IDs. Replace uses only custom rules. An empty effective
list after successful extraction requires human review and publishes no
conformance result. An empty list with unresolved extraction gaps is a failed
extraction: it cannot publish an approval request, consume an older approval,
start verification, or complete as a conformance report. This applies to cached
artifacts and retries as well. A staged `extraction-status.json` records zero
candidates, unresolved and unattempted sections, and available typed diagnostic
codes. Error diagnostics retain only bounded types, codes, stages, retryability
and provider response counts; provider messages, credentials, prompts and sources
are excluded.
Candidates beyond the investigation limit remain visible and receive Unknown
rows after human review of that budget.
Generated IDs hash the document path, normalized statement, and distinct
subject, scope, modality, conditions and kind. Exact duplicates retain all
origins. A legacy ID can override a single unambiguous matching rule.
Models select immutable source-line IDs; trusted code copies the exact captured
text and physical span. Invalid selections receive focused corrections that
preserve every original statement. Invented handles cannot establish references.
Canonical candidate artifacts and cache entries must pass exact quote/span
validation against the current captured source before admission.

Responses receive at most `review.max_extraction_attempts` attempts per packet
(default and maximum 3). Malformed JSON, incomplete output and persistent
selection errors partition the source into smaller complete-line packets within
the same packet budget and deadline. Successful children survive sibling
failures; partial model responses are never admitted as complete extractions.
Unresolved sections record identity, line range and safe reason in
`extraction_gaps`, then other documents continue. Transport failures receive
bounded retries and backoff. Three consecutive unavailable document packets
open the phase circuit; remaining sections become explicit gaps. Deadline
exhaustion also becomes gaps. Every gap is bound into human review and the
published report. Missing requirements never receive invented judgments.
Draft responses are confidential audit artifacts, not rule or approval authorities.
The complete effective list is `rules.md`; source provenance is in `rules.json`.
Job-scoped candidate caches bind snapshot, document hash/span and extraction
policy and require fresh evidence validation. They never retain approval
authority. Invalid entries are recomputed; optional cache writes cannot block
results. The cache holds at most 2,048 entries of at most 1 MB each.

## Required human review

Version 1.1.0 adds a mandatory review gate. Unattended runs now stop before rule
verification until the supervisor explicitly approves the list in Chat. There
is no model response or local approval file that can bypass this gate.
Version 3.3.0 declares `default_answer.option_id=approve` on each review request.
An enabled, persisted OtterDesk automatic-response preference may submit that
default after its configured delay (15 seconds by default). The app uses the
same Core response, revision, digest and ownership checks as a manual decision.
Manual review remains available and stops that request's automatic response.

The review step calls the run-scoped WIT approval interface to create blocking approval records in Core. OtterDesk's existing conversation interaction stream displays
them and submits Approve/Reject directly to Core. It does not publish legacy
file-ledger requests. The step waits for authoritative decisions; the verification
specialist independently reads them again before creating its model client.

One Core request binds the canonical ruleset digest (including source snapshot
and provenance), review revision, and SHA-256 of an immutable Markdown collection
artifact. The existing conversation stream displays a searchable list of short
titles, complete Markdown details/source references, and a per-rule Markdown
editor. Title pages contain at most 50 entries; search and Approve all cover the
entire list. No rule text is silently omitted. Review artifacts are at most 16 MiB.

Saving an edit sends the existing rule ID, title and Markdown through Core's
bounded `revise` response. The specialist validates it, retains original source
provenance, saves the revised rules and audit, and publishes a new content-bound
review. This never grants approval. A save interrupted between rules persistence
and coordination-plan persistence is reconstructed from its exact Core edit
receipt. Invalid edits preserve the rules and request review again.

Approve all authorizes the entire saved version. The latest Core request must
match that version before verification and report publication. Unsaved drafts,
stale decisions, a prior run, changed local rules, forged approval files or an
audit event alone cannot grant permission. Rejection stops the run. Edits apply
to the current run; exported titled Markdown can be copied into Job Knowledge
for reuse. Unresolved extraction coverage and investigation limits are included
in the hashed review content and remain visible in a scope notice. Accepting
partial scope does not imply missing requirements were found or verified.

Pending reviews share one persisted expiry, at most one hour. Rejection,
expiration, missing decisions or authority failures never authorize verification.
The review step returns only after the saved list is approved. Core cancellation
ends the worker. Duplicate delivery reuses the same request IDs and actual Core
decisions. `rules-review*.json` are audit artifacts, not decision authorities.

## Evidence and judgment

Each rule receives its own bounded model/tool investigation using literal code
search and exact source reads. Only citations read in that investigation can be
admitted; quotes, lines and full captured file hashes must match. File roles are
assigned by trusted code. Names, comments, desired behavior and test definitions
are not execution evidence. Syntax parser gaps and unresolved bindings stay
explicit. Missing matches never prove absence. No repository source or tests run.
Models select evidence IDs from source reads; trusted code copies their text.
Invalid actions, replies and citations receive safe feedback within the turn
budget, allowing query, range and evidence selection changes. Working context
compacts to 24 KB while the full audit history is retained. Large file inventories
are previewed within 24 KB/512 entries; search and read retain the full captured
scope. Three consecutive provider failures end that rule as Unknown. Each
subsequent approved rule still receives its own independent investigation within
the configured rule and verification time limits, even after consecutive failed
rules. Earlier failures cannot substitute an unattempted row for a later rule.
Saved outage placeholders without an investigation are unfinished work and must
be investigated on resume; completed investigations remain idempotent.

Every effective rule has exactly one result: pass, fail or unknown. Pass/fail
requires admitted implementation evidence and model confidence >=0.60. The
static confidence cap is 0.85; Unknown is capped at 0.49, and tool/model/validation
failure or exhausted budgets yields 0.0 with an explicit reason. Original model
confidence is retained when admissible. Scores are uncalibrated assessments,
not measured probabilities. Results always identify `basis=static_review` and
`tests_executed=false`. Requirement conflict, universal claims and runtime-only
properties require human interpretation and usually Unknown.

The Markdown report contains rule, pass or not, evidence with file/line reference
and SHA-256, and confidence 0–1. It includes reasoning, origins, omissions and
limitations. Structured results and captured source accompany the report so a
source checkout changing later cannot silently change historical evidence.

## Safety, storage and evaluation

All source, documentation, custom knowledge and model output are untrusted.
The tool allowlist has only rank/search/symbols/trace/read/finish, with no command, network, edits
or delegation authority. Input and run outputs must be separate. The runtime
stages the selected folder; blueprint capture never derives host destinations.
Artifacts are written atomically before agent output, use deterministic names,
and are reused on duplicate delivery. Per-rule checkpoints bind to the effective
rule and snapshot identity. Knowledge is Job-scoped; new runs capture edits.

Capture has bounded entry, file, byte, format and symlink policies. Excluded
subtrees and files remain explicit. Captured files are UTF-8 and at most 500 KB;
capture is at most 2,000 files/10 MB, custom rules 100 files/500 KB. Default
`review.documentation_scope=current_requirements` excludes documents in case-insensitive
`benchmark-results`, `benchmark_results`, `test-results`, `test_results` and
`playwright-report` directory segments from rule extraction, while retaining
captured text for evidence. `all_captured_docs` explicitly includes these.
`extraction-plan.json` records the selected and excluded document identities,
source snapshot and packet budget before model creation. rules.json and the
final report retain the exact selection and every excluded document.
Extraction uses packets of up to 50 complete lines / a 4 KB target, allowing a
single complete line up to 12 KB. It admits at most `review.max_extraction_packets`
packets (default 512, bounded 1–2048), including adaptive children. The investigation
allowance defaults to 2000 rules and is bounded 1–2000; every candidate remains
visible and requires approval. Excess candidates receive Unknown rows.
Extraction failures and explicitly configured deadlines become reviewable gaps; verification deadlines
mark remaining rows Unknown. Extraction has no default elapsed deadline and requests an
8,192-token output allowance; verification retains 3,500 tokens per request.
Model requests have 90-second deadlines. Bounded retries and adaptation never
substitute deterministic model success. Core cancellation
terminates the executing worker.
Model input packets have a 100 KB ceiling and working tool observations a 24 KB
ceiling. Invalid setup, capture/storage integrity failures and unavailable human
approval remain blocking. Platform staging precedes capture; users select a
clean source scope.

Acceptance: deterministic tests cover complete extraction, custom add/override/
replace, pass/fail/unknown reports, forged and unread references, docs-only
evidence, invalid confidence, missing source, bounded failures, duplicate delivery,
Job knowledge, source immutability, manifest compile and architectural boundaries.
Human-review tests cover pending/rejected/expired states, full preview coverage,
scope and content binding, replay, forged local receipts, Core transport and
the guarantee that no verification model calls occur before approval.
Live model accuracy and full installed/runtime execution are separate opt-in gates.

Non-goals: automatic fixes, repository and test execution, dependency
installation, remote cloning, formal verification, exhaustive language analysis,
complete requirements discovery or guarantees of conformance/safety.

## Report presentation

`mirrorneuron-web-report-skill` owns common report chrome and component assets.
The blueprint owns its domain-specific views, source scope and evidence semantics.
The web page is local/offline with a minimal header, Actions dropdown, progressive
tabs and a non-modal evidence Sheet. Presentation adds no model calls, source
execution, external sharing, runtime changes or approval authority.
The overview prioritizes new regressions, other failures, conflicting CI
observations and evidence gaps. Each finding shows the approved expectation,
source effect, suggested check when available and exact citations. The source
viewer highlights the cited range and lets the developer inspect the full file.
Rendering or handle-publication failures cannot prevent the authoritative
Markdown and structured report from completing. A safe presentation status
records the failure type without provider or source contents.
Publication stages the declared report, rules, captured source and audit artifacts
in the SDK-provided `MN_JOB_OUTPUT_DIR` before returning. Optional static HTML and its
handle are staged separately after rendering. The runtime owns host delivery and
batch run folders; the blueprint never derives or writes a host Downloads path.
The UI extension declares `static_html`, allowing OtterDesk to open the delivered
`web/index.html` after validating its adjacent handle.
The publication result returns the SDK `published_files` manifest for report
JSON/Markdown and the optional page/handle. Native workers export these verified
bytes for the conversation workspace; optional presentation remains optional.

## Step execution and publication

The executable bindings are in `execution.json` and the step graph is in `workflow.json`. Each Rust component reads its step input, calls its declared run services and returns a structured result. Capture commits the source snapshot. Downstream phases consume content-pinned references, and the review step binds the human response to a rules digest and revision.

The publication step commits the report JSON, Markdown and HTML and asks Core to publish their immutable receipts. Core owns run completion and host delivery.

## Scoped static verification (3.1.0)

`review.documentation_scope=current_requirements` is the default. Historical
changelogs and evaluation reports are recorded separately. Section headings,
fence state and preceding context survive packet boundaries. Tutorial instructions
and bare code/configuration examples cannot become product obligations; governing
prose can establish a requirement scoped to the specific example/tool. Extracted
rules retain subject, scope, modality, conditions and kind. Only exact scoped
duplicates merge, retaining all origins; potential conflicts stay visible.
The existing human review includes exclusions, excluded candidates and scope flags.
A supervisor rewrite clears stale extracted qualifiers and requires fresh approval.

`review.spec_paths` can select captured documents using repository-relative paths
or patterns, one per line. `docs/*.md` selects Markdown files directly in `docs/`.
For a Git comparison, the paths resolve against the proposed snapshot. An unmatched
selection fails before sending document text to the model. A blank setting uses
the configured document scope.

Retrieval uses offline BM25 keyword/path ranking with identifier splitting and
existing Tree-sitter definitions, imports and caller/callee candidates. One index
is reused for the capture. `source_hashes` verifies every analyzed file, including
unsupported/parser-gap files. The model receives a compact role-based project map,
ranked implementation candidates and bounded exact source reads rather than an
alphabetical list dominated by benchmark output. Source, configuration, tests,
examples, generated artifacts and documentation have distinct authority.

The default eight model calls reserve two calls for a structured judgment and an
independent critique. `review.max_turns_per_rule` accepts 3–12 total calls. Early
judgments may use fewer calls. The critic sees the approved rule and selected
source, not the draft verdict. Conclusive judgments need matched scope, checked
conditions, direct enforcement/contradiction evidence and agreement. A configuration
value alone cannot prove behavioral enforcement. Generated output cannot prove
product behavior. Syntax navigation is not compiler binding or runtime proof.
Repeated queries receive specific recovery guidance. Full audit history survives
working-context compaction; selected source spans and stable read handles remain
available. Reports retain useful evidence and next steps when a verdict is unknown.

`diagnostics` records model calls, seeded/source reads, searches, empty searches,
repeated queries and unknown reasons. Reasons distinguish budget exhaustion,
provider/response failures, parser/capture gaps, ambiguity, insufficient evidence,
runtime-only properties and reviewer disagreement. Extraction exclusions remain
separate from assessed-rule counts. No unknown-rate target encourages guessing.
The public report retains pass/fail/unknown, exact source references and static
confidence caps. Source execution, network tools, arbitrary commands, automatic
fixes, model-route changes and approval bypass remain unavailable.

Extraction and verification checkpoints bind prompt/implementation policy, source
identity and approved rules. Old-policy runs require a fresh run and human review;
historical delivered reports are never overwritten. Runtime, SDK and desktop
contracts for the original source-review phases continue to apply.

For an authorized delivered run, `python software_verifier_suite/benchmarks/compare_capture.py
/path/to/run --output-dir /tmp/code-verifier-comparison` audits all prior conclusive
results and 26 unknowns stratified by origin. It writes confidential comparison
JSON/Markdown outside that run, comparing source roles and ranked source reads.
It makes no model calls and does not label new pass/fail judgments or claim measured
LLM accuracy. Run the focused blueprint/quality tests and affected skill suites
before an opt-in live run; the revised rules still require the normal approval.

The offline navigation/hash APIs are published in both skills at `>=1.4.1.dev0,<2`.
Publish static-analysis first, then code-search, before raising these blueprint
minimums. Version 3.1.0 uses these published skill versions with the existing
runtime and unchanged SDK dependency declarations.

Capture has no separate source-folder port: it resolves the required folder from
the SDK-owned staged `inputs.payload.input_folder` configuration. A default empty
workflow run-input port must not shadow that staged selection. Empty configuration
still fails visibly; no host-path or alternate-source fallback is introduced.


## Stage-aware conversation

OtterDesk reads `payloads/prompts/conversation.json` as optional app-owned guidance. It combines this role and stage policy with the pending question, confirmed non-secret setup answers, recent dialogue, selected report and fresh Job state. Short follow-ups retain their topic; a correction does not silently change saved configuration.

Use Memory or explicitly ask to remember, edit or forget an explanation preference. This affects Chat wording only; working rules and evidence keep their existing domain controls. The optional `inputs.payload.supervisor_instructions` array is app-managed, never a required setup answer or a new workflow permission.

Use the selected run report and exact source/rule references. Documentation and absence of search hits cannot prove implementation correctness. Only Core approval of the exact rule revision authorizes verification. A conversational yes or saved preference cannot approve, edit or remove rules. Use Review rules and Job knowledge for requirements. Never execute repository code or claim conformance from missing evidence. Existing submitted runs retain their configuration, evidence and approvals. An idle prepared Job may refresh through the existing conditional API without rehiring, resetting memory or mutating an active run.


## WASI 0.3 execution

Core schedules every step, owns retries and cancellation, and validates child plans. Each admitted step runs as a Rust WASI 0.3 command under Wasmtime. The SDK composes the six pinned WIT skills at submission. The phase can use the run-scoped artifact, model, approval, and mailbox imports granted in `execution.json`.
