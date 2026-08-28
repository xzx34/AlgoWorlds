You are selecting a minimum-cost package under precedence, compatibility,
handoff, and override rules.

Choose exactly one play at each ordered stage. The first play must be authorized
from the source, and every later play must be authorized after the preceding
choice. For an authorized step from `u` to `v`, the charged amount is:

`base_cost(v) + cost_adjustment(override_code(v)) + handoff_cost(u,v)`.

These three components are available through separate costed sources and all
must be joined before global optimization.

Each play also contributes a `clearance_residue`. A complete package is legal
only when the sum of these residues equals `required_residue` modulo the
`modulus` returned by `read_override_policy`. This is a global constraint: an
authorized package with the wrong residue is illegal.

Responses are compact positional tables with fixed column order:

- catalog stage rows: `[play_id, base_cost, override_code, clearance_residue]`;
- direct authorization rows: `[predecessor_id, successor_id, handoff_cost]`;
- staged authorization entries: `[predecessor_id, approval_slot]`;
- staged authorization exits: `[approval_slot, successor_id, handoff_cost]`;
- policy rows: `[override_code, cost_adjustment]`.

Catalog responses include the exact `columns` declaration. The policy response
includes `checksum: {modulus, required_residue}` and its own `columns`
declaration. Treat booleans, missing fields, extra columns, or out-of-range
residues as malformed data rather than guessing.

Tables are grouped under `stages`, each with a `stage_id`. A staged
`approval_slot` is response-local: join entries and exits from that same tool
response. It is not a play id and must not be submitted.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including an exact repetition. `evaluate_package` checks and prices exactly one
caller-supplied package; the first call consumes this one-shot opportunity even
if the package is malformed or illegal, and later calls only return
`already evaluated`. It never recommends or repairs a choice.

Submission is free, binding, one-shot, and terminal.
