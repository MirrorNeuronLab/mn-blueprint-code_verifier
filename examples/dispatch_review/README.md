# Dispatch review

Select **Sample dispatch review** in suite setup to use the two fictional revisions under `comparison/` and their pinned records in `evidence/`. The example exercises an ordinary dispatch retry, compares declarative access decisions, and checks whether the original label tests catch two controlled changes. Revision identifiers in this fixture are synthetic. The hosted repository and existing CI status are unspecified.

For your own records, produce UTF-8 JSON using `mn.comparison-evidence.v1`. Pin the SHA-256 of the exact bytes separately in **Case evidence SHA-256**. The full working record in the evidence folder illustrates these fields:

- `subject` and optional `baseline_subject` are the verification plan's captured subject identities.
- Each distinct case provides an `id`, `category`, `claim`, `expected`, fixture SHA-256, scoped source path and line, and `runs`. Use `workflow`, `boundary`, `policy` or `test_control` to select the responsible specialist.
- A run supplies a unique ID within its case, a `candidate` or `baseline` revision, an explicit `clean` reset marker, and an observed value. Boundary runs may include ordered named stages and their expected and observed values.
- Policy cases specify the actor, action and resource and use `allow` or `deny`. Test controls specify the test and controlled change, the result of the original test and whether the control was killed or survived.
- An optional `issue` correlates repeatable symptoms. Within one issue and fixture, share a run ID across views only when they reuse the same physical observation. Include a severity and an acceptance check in `remedy` when known.
- Optional coverage supplies the tool, measured source paths and covered / total executable lines. Missing measurements display as unmeasured.

`record_example.py` recreates the receipts from the bundled fixtures in an environment with the verification skill installed. It is a development tool, separate from the suite workflow.

## What this sample measured

The seven declared passages cover four workflows and three policy cases. Normal dispatch and retry flow through a JSON producer, an in-memory retry transport and a queue consumer. Two fresh candidate retry runs each leave two queue entries. The baseline leaves one. The functional and integration views cite the same run IDs.

The original three candidate tests pass under pytest. Ruff checks E4, E7, E9 and F on the candidate Python files. Neither check reports the duplicate. The role comparison reads the fixture’s JSON policy table. A reviewer can archive a draft according to that configuration. Runtime authorization, hosted CI and independent AI review are unmeasured. Of two controlled changes, accepting a blank label survives the existing tests. A proposed assertion passes on the original and detects that change.

The optional **Report context SHA-256** selects an `otterdesk.assurance-basis.v1` record with matching candidate, baseline and case-ledger identities. `gates` and `repair_checks` reference scoped execution checks backed by separate pinned receipts. `locations` names captured implementation lines. The recorder requires Python, pytest, Ruff and the verification skill. Running it prints the new input pins, including the versions of the tools in the execution receipts. The publication test uses scripted passage selection and approval to exercise the coordinator and four specialist mailboxes. It publishes the real report without an external model.
