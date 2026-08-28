# Capacitated fleet-dispatch environment

Assign every listed positive-load job to exactly one eligible vehicle. Vehicle handles are
`<vehicle_handles>` and job handles are `<job_handles>`. A legal dispatch must
respect every vehicle's load capacity. Its raw cost is the sum of primitive
vehicle-job route costs plus the fixed contract cost of each vehicle that
carries at least one job.

The reported objective removes one public unavoidable lower-bound constant.
Let `k` be the smallest number of largest capacities whose sum can carry all
job load. The constant is the sum, over jobs, of the cheapest route price for
that job, plus the `k` cheapest fixed prices, minus one. Reported cost is raw
cost minus that same constant for every legal assignment. It is always positive
and has exactly the same ordering and optimum as raw cost. Minimize reported
cost.

The query budget is `<cost_budget>` units and query costs are `<tool_costs>`.
Every query is charged, including repetitions. A query that would exceed the
remaining budget does not execute. Final submission is free, binding, one-shot,
and terminal.

Job loads can differ. Job calls reveal load and eligibility but no route prices.
Fleet policy is the only source of capacities. Contract calls reveal only one
vehicle's fixed activation price; they never list a capacity or a set of jobs.
Route-row calls reveal one physical direct or shift-mediated route row.
Windows reveal primitive records for two or three consecutive jobs. Candidate
evaluation checks exactly the complete mapping supplied by the caller, returns
its normalized price, and never constructs or modifies a dispatch. It may
execute only once; an illegal candidate consumes that opportunity.
