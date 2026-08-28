"""Runtime-only helpers for case_17_machine_layout."""
from __future__ import annotations
from typing import Any, Mapping
from algoworlds.runtime_types import Evaluation
from benchmark.cores.case_17_machine_layout import runtime_data

def evaluate_layout(payload: Mapping[str, Any], decision: Any) -> Evaluation:
    if not isinstance(decision, dict):
        return Evaluation(False, None)
    machines = [row['machine_id'] for row in payload['machines']]
    slots = [row['slot_id'] for row in payload['slots']]
    if set(decision) != set(machines):
        return Evaluation(False, None)
    assigned = [decision[machine] for machine in machines]
    if any((not isinstance(slot, str) for slot in assigned)) or set(assigned) != set(slots):
        return Evaluation(False, None)
    flows = runtime_data.flow_lookup(payload)
    distances = runtime_data.distance_lookup(payload)
    settlement = runtime_data.settlement_lookup(payload)
    raw_interaction = 0
    for (left_index, left) in enumerate(machines):
        for right in machines[left_index + 1:]:
            flow = flows.get(tuple(sorted((left, right))), 0)
            distance = distances[tuple(sorted((decision[left], decision[right])))]
            raw_interaction += flow * distance
    adjustment = sum((settlement[machine, decision[machine]] for machine in machines))
    offset = payload.get('flow_normalization_offset')
    if isinstance(offset, bool) or not isinstance(offset, int):
        raise ValueError('flow_normalization_offset must be an integer')
    total = raw_interaction + adjustment - offset
    return Evaluation(True, total)
