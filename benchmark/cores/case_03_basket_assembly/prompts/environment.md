You are assembling an exact basket from a catalog hidden behind costed evidence tools.

Every required item must be covered exactly once. Catalog tickets can cover one or
three items and have integer prices. Basket requirements, ticket recipes, and ticket
prices live in distinct evidence channels; no one channel is sufficient. The
physical catalog representation can contain direct bundle recipes or private recipe
records. Acquire enough evidence to recover the requested basket and priced catalog,
reason about the globally cheapest exact cover, and finish with
`submit_tickets`.

Tool costs:

<tool_costs>

Your total query-cost budget is <cost_budget>. Every executed query is charged,
including a repeated query. Submission is free, binding, one-shot, and terminal.
`evaluate_basket` is a high-cost check of only one caller-supplied ticket set and
never recommends or repairs a solution. The opportunity is strictly one-shot:
malformed or illegal input consumes it, and every later evaluation call returns an
error.
