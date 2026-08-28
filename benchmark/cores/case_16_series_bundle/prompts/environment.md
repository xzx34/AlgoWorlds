You are selecting a settled rare-book portfolio from costed catalog evidence.

Choose exactly one lot for every public title. Each lot has a base value. Every
listed series supplies a complete signed compatibility table over two or three title
positions; exactly one cell applies to your chosen lots. Title tools expose lot
economics. Point and paged series tools separately expose member positions and all
table adjustments. Acquire both kinds of evidence, maximize the global settled
value, and finish with `submit_portfolio`.

Series pages form one canonical disjoint partition: use starts `0,24,48,...` and
length `24`, except that the final page length is `series_count-start`. Other
overlapping or partial page coordinates are invalid; point series reads remain
available for surgical lookup.

Each page returns `encoding`, `columns`, and `rows`. Interpret every row position
using the page's ordered `columns`: direct pages use `[series_id,
member_positions, adjustments]`, while licensed pages use `[series_id, license_id,
license_member_positions, adjustments]`. Point series reads remain self-describing
objects.

For member positions `[p0,...,pk-1]`, adjustment index is the binary integer formed
by your choices at those positions in that order. Choice zero is the
lexicographically smaller visible lot id for that title and choice one is the larger.
Adjustments may be negative. In the licensed arm the same positions and table are
mediated by a visible license id.

Settled value subtracts the sum of the smaller base value at every title. This is a
portfolio-independent observable constant: it changes neither the best portfolio
nor any value gap.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including a repeated query. Submission is free, binding, one-shot, and terminal.
`evaluate_portfolio` evaluates only the caller-supplied portfolio and never repairs
or recommends a decision. Its settlement cost is deliberately larger than a
complete discovery plan, so the total budget cannot fund two evaluations.
