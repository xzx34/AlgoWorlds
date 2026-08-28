"""Runtime-only helpers for case_18_match_pairing."""
from __future__ import annotations
from typing import Any, Mapping
from algoworlds.runtime_types import QueryCall
from benchmark.cores.case_18_match_pairing import runtime_data

def _docs(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return payload['source_documents']

def _pair_cost_observation(documents: Mapping[str, Any], pair_id: str) -> dict[str, Any]:
    row = next((row for row in documents['pair_source']['pairs'] if row['pair_id'] == pair_id))
    return {'pair_id': pair_id, 'cost': row['cost']}

def _handoff_observation(documents: Mapping[str, Any]) -> dict[str, Any]:
    people = list(documents['participant_order'])
    slots = {person: index for (index, person) in enumerate(people)}
    (left, right, costs) = runtime_data.normalized_handoffs(documents)
    return {'rule': 'left_sequence_adjacent_right_handoff', 'left_slots': [slots[item] for item in left], 'right_slots': [slots[item] for item in right], 'columns': ['from_right_slot', 'to_right_slot', 'cost'], 'rows': [[slots[source], slots[target], costs[source, target]] for source in right for target in right if source != target]}

def _observe(payload: Mapping[str, Any], call: QueryCall) -> Any:
    documents = _docs(payload)
    pairs = runtime_data.normalized_pairs(documents)
    if call.tool == 'read_participant':
        person = call.args['participant']
        return {'slot': documents['participant_order'].index(person), 'pair_ids': sorted((pair_id for (pair_id, row) in pairs.items() if person in row['participants']))}
    if call.tool == 'read_pair':
        return _pair_cost_observation(documents, call.args['pair'])
    if call.tool == 'read_compatibility_row':
        person = call.args['participant']
        slots = {item: index for (index, item) in enumerate(documents['participant_order'])}
        pair_ids = sorted((pair_id for (pair_id, row) in pairs.items() if person in row['participants']))
        others = {pair_id: next((item for item in pairs[pair_id]['participants'] if item != person)) for pair_id in pair_ids}
        if documents['pair_source']['encoding'] == 'direct':
            return {'encoding': 'direct', 'slot': slots[person], 'rows': [[pair_id, slots[others[pair_id]]] for pair_id in pair_ids]}
        return {'encoding': 'event', 'slot': slots[person], 'pair_events': [[pair_id, event] for (event, pair_id) in enumerate(pair_ids)], 'event_participants': [[event, slots[others[pair_id]]] for (event, pair_id) in enumerate(pair_ids)]}
    if call.tool == 'read_pair_window':
        (start, length) = (call.args['start'], call.args['length'])
        return {'pairs': [[row['pair_id'], row['cost']] for row in (_pair_cost_observation(documents, pair_id) for pair_id in documents['pair_order'][start:start + length])]}
    if call.tool == 'read_handoff_policy':
        if call.args:
            raise ValueError('read_handoff_policy takes no arguments')
        return _handoff_observation(documents)
    if call.tool == 'evaluate_matching':
        try:
            value = runtime_data.matching_cost(documents, call.args['pairs'])
        except (KeyError, TypeError, ValueError):
            return {'complete': False, 'legal': False}
        return {'complete': True, 'legal': True, 'total_cost': value}
    raise ValueError(f'unknown query {call.tool!r}')
