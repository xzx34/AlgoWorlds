You are forming a minimum-cost sequential perfect matching from costed public
evidence.

Every public participant must appear in exactly one submitted pair. The
handoff policy publishes a fixed left-participant order and a right roster. If
your selected right sequence in that left order is `r_0,...,r_(q-1)`, raw cost
is

```text
sum of the q selected pair costs
+ sum of the q-1 directed handoff costs h(r_(i-1),r_i).
```

Handoff direction matters. There is no self-handoff, no handoff before the
first left position, and no handoff after the last. A unary minimum-cost
assignment that ignores these adjacent transitions is not the stated problem.

Pair costs, physical compatibility incidence, and the sequential handoff policy
are separate tool channels. You need all three to reconstruct and solve the
instance. `read_handoff_policy` returns:

```text
{
  "rule": "left_sequence_adjacent_right_handoff",
  "left_slots": [...],
  "right_slots": [...],
  "columns": ["from_right_slot","to_right_slot","cost"],
  "rows": [[from_slot,to_slot,cost], ...]
}
```

Slots are zero-based positions in the Participant handles list. The table
contains every directed pair of distinct right slots exactly once.

Candidate evaluation and submission report

```text
raw_cost - LB + 1
LB = sum over left positions of the minimum incident pair cost
     + (q-1) times the minimum directed handoff cost.
```

`LB` is observable and constant across legal matchings, so minimizing the
reported value is equivalent to minimizing raw cost.

`read_pair_window` is aligned: `length` must equal the published
participants-per-side value `q`, `start` must be a multiple of `q`, and each
page returns `q` compact `[pair_id,cost]` rows. Endpoints remain in topology
tools. A direct compatibility row returns
`[pair_id,other_participant_slot]`; an event-arm row exposes response-local
`pair_id -> event_slot -> other_participant_slot` joins.

A complete row topology plan can read roster slot 0, take the `q` neighbor
slots named by that response, and read those `q` rows. The alternative reads
all participant incidences. Both plans still need every aligned pair-cost page
and `read_handoff_policy`.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including a repeat. Submission is free, binding, one-shot, and terminal.
An unaffordable query is rejected before execution and is not charged. Such a
rejection does not exhaust the round while any cheaper query tool still fits in
the remaining budget; you may continue with an affordable query or submit. A
submit-only final turn begins only at exact exhaustion or when no query tool is
affordable.
`evaluate_matching` evaluates only one caller-supplied complete candidate and
never repairs or recommends; an illegal first candidate consumes it.
