You are planning a component migration portfolio from costed evidence sources.

Choose exactly one package for every public component group. Package base prices,
migration classifications, support requirements, and fixed charges are hidden
behind tools. A modern package needs no support domain. A legacy package needs
one or two domains, and every activated domain's fixed charge is paid once across
the whole portfolio. You must acquire facts, join them, optimize globally, and
finish with `submit_portfolio`.

Catalog and classification can be read by individual group, by a length-two or
length-three consecutive window, or by fixed page. Page `k` is zero-based and
covers group-order positions `16k` through `16k+15`. The public group list is in
that same order.

The policy response includes an `objective_offset`. Settled cost is selected
base cost plus each distinct activated-domain charge, minus that offset, plus
one. The offset is an assignment-independent visible lower bound, so it changes
neither the best portfolio nor any cost gap; it only fixes the reported origin.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including a repeated query. Submission is free, binding, one-shot, and terminal.
Candidate evaluation is one-shot: its first call is consumed even if the
candidate is illegal. It returns only legality and scalar total cost; it does
not reveal a decomposition, recommend, or repair a portfolio.
