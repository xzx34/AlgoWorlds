# Machine layout planning

Place every surveyed machine in exactly one surveyed floor slot, using every
slot exactly once. The raw cost of an assignment is

1. the sum, over every unordered machine pair, of pairwise throughput times the
   distance between their assigned slots; plus
2. the primitive settlement adjustment for every selected machine-slot
   placement.

The reported objective subtracts one fixed `C_flow`: the minimum flow-only
interaction attainable on this same floor. This is only a common origin shift:
every legal assignment has exactly the same constant subtracted, so raw-cost
ordering, pairwise gaps, and the minimizing layout are unchanged. You do not
need to compute `C_flow` to choose the argmin.

Throughput is symmetric and the slot metric is a unit-spaced line. The
throughput, distance, and settlement channels are independently hidden.
Each channel has both single-row reads and two/three-row block reads. A block
uses zero-based consecutive positions in the machine or slot roster returned by
the survey, and still returns only its own channel. Two complete, consistent
distance rows determine the promised unit-line metric even when neither row is
an endpoint. Compare the displayed costs,
acquire and join enough information under budget, reconstruct the slot geometry,
solve the coupled global assignment problem, and submit one complete
machine-to-slot mapping.

Information calls have these costs:

<tool_costs>

The total query budget is <cost_budget>. Submission is free, binding, and may be
called only once. Use exactly one tool call per turn. Candidate evaluation
may also execute only once and returns only the cost of the layout you provide;
an illegal candidate consumes that opportunity. No tool recommends a layout or
reports an optimality gap.
