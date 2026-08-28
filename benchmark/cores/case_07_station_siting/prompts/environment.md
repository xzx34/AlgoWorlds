# Banded conjunctive-coverage station-siting environment

Select exactly `<facility_limit>` tooling stations, one from each listed zone.
At most `<max_extended_sites>` selected stations may have option value 1. A
demand contributes its reward only when both sites in its physical incidence
relation are selected; partial coverage contributes nothing. Relations join
zones at most `<interaction_bandwidth>` corridor positions apart. There are
`<demand_count>` distinct relations. The objective is total covered reward
minus selected-site operating cost, then shifted by the fixed value of the
feasible economics-only layout (choose by operating cost and enforce the
option-1 capacity). This public baseline is zero; the shift preserves every
layout ordering and objective gap.

Zone handles are `<zone_handles>`. Demand handles are `<demand_handles>`.
The total query budget is `<cost_budget>` units and query costs are
`<tool_costs>`. Every query is charged, including repetitions. A query that
would exceed the remaining budget does not execute. Final submission is free,
binding, one-shot, and terminal.

Local tools reveal one zone's site economics or one demand relation. A window
reveals only site economics for two or three consecutive zone positions; it
does not reveal demand incidence. Candidate evaluation checks only the complete
layout supplied by the caller, never changes it, and may be called only once;
an illegal or malformed candidate consumes that opportunity. The mediated
physical arm may expose private connector identifiers; a connector represents
one conjunctive demand relation and is not itself selectable.
