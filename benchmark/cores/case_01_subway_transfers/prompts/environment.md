You are planning a minimum-cost route through an ordered subway corridor.

Choose exactly one leg at every route stage, from the surveyed source through
every ordered station to the destination. Each leg has a positive travel time,
a public ticket residue, and belongs to one opaque line. If consecutive
selected legs use lines `a` and `b`, add the directed transfer cost `C[a,b]`;
`C[a,a]` is zero. The raw route cost is the sum of all selected travel times
and all consecutive directed transfer costs. Transfer costs are pair-specific
and directional: this is not a lexicographic “fewest transfers, then fastest”
objective.

A route is legal only when the sum of its selected ticket residues, reduced
modulo `survey_route.checksum_modulus`, equals
`survey_route.required_ticket_residue`. The checksum is a hard constraint,
not a cost or a tie-breaker.

The reported `encoded_cost` subtracts

`sum(minimum visible travel_time at each stage) - 1`

from the raw route cost. This is an observable route-independent constant, so
it changes neither the minimizing route nor any cost gap.

Information is deliberately separated. `survey_route` returns the ordered
station chain, opaque line directory, and checksum rule. `read_departures`
returns one stage's legs, travel times, and ticket residues.
`read_station_window` returns the same topology/travel/residue facts for a
two- or three-stage window starting at a surveyed station.
`read_stage_memberships` returns the direct rows or the two mediated join tables
leaving one surveyed station. `read_transfer_costs` returns one complete
outgoing directed-cost vector aligned with `survey_route.line_ids`. You need
topology, membership, and transfer economics to settle a route exactly; the
survey is the bootstrap source for every opaque station and line handle.

`evaluate_route` settles only the complete route you supply. It exposes no
source rows, does not repair or recommend a route, and gives no optimality gap.
It is independently strict one-shot, including after a malformed candidate.
Use `submit_route` for the final ordered list of leg identifiers.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including an exact repetition. Use exactly one tool call per turn. Submission
is free, binding, one-shot, and terminal. Only facts explicitly returned by
the tools are available; do not assume unreturned payload fields, memberships,
transfer rows, a stored solution, or a recommended route.
