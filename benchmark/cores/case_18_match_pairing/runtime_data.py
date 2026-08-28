"""Runtime-only helpers for case_18_match_pairing."""
from __future__ import annotations
from typing import Any, Iterable, Mapping
CASE_ID = 'case_18_match_pairing'
QUERY_COSTS = {'read_participant': 2, 'read_pair': 3, 'read_compatibility_row': 8, 'read_pair_window': 8, 'read_handoff_policy': 2, 'evaluate_matching': 5}
SUBMIT_TOOL = 'submit_matching'

def _bipartition(participants: list[str], pairs: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    adjacency = {person: set() for person in participants}
    for row in pairs.values():
        (left, right) = row['participants']
        adjacency[left].add(right)
        adjacency[right].add(left)
    color = {participants[0]: 0}
    stack = [participants[0]]
    while stack:
        person = stack.pop()
        for neighbor in adjacency[person]:
            if neighbor not in color:
                color[neighbor] = 1 - color[person]
                stack.append(neighbor)
            elif color[neighbor] == color[person]:
                raise ValueError('compatibility graph is not bipartite')
    if set(color) != set(participants):
        raise ValueError('compatibility graph must be connected')
    first = [person for person in participants if color[person] == 0]
    second = [person for person in participants if color[person] == 1]
    if len(first) != len(second):
        raise ValueError('compatibility bipartition must be balanced')
    q = len(first)
    if any((len(adjacency[person]) != q for person in participants)):
        raise ValueError('compatibility graph must be complete bipartite')
    return (first, second)

def normalized_pairs(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    source = documents['pair_source']
    result: dict[str, dict[str, Any]] = {}
    if source['encoding'] == 'direct':
        for row in source['pairs']:
            result[row['pair_id']] = {'participants': sorted((row['left'], row['right'])), 'cost': row['cost']}
    elif source['encoding'] == 'event':
        attendance: dict[str, list[str]] = {}
        for row in source['attendance']:
            attendance.setdefault(row['event_id'], []).append(row['participant_id'])
        for row in source['pairs']:
            if row['event_id'] not in attendance:
                raise ValueError('pair references unknown event')
            result[row['pair_id']] = {'participants': sorted(attendance[row['event_id']]), 'cost': row['cost']}
        if {row['event_id'] for row in source['pairs']} != set(attendance):
            raise ValueError('orphan event')
    else:
        raise ValueError('unknown pair encoding')
    participants = list(documents['participant_order'])
    if len(participants) < 4 or len(participants) % 2 or len(set(participants)) != len(participants):
        raise ValueError('participants must be a distinct even roster')
    if len(result) != len(documents['pair_order']) or set(result) != set(documents['pair_order']):
        raise ValueError('pair source does not match pair order')
    seen_endpoints = set()
    for row in result.values():
        endpoints = row['participants']
        if len(endpoints) != 2 or len(set(endpoints)) != 2 or any((person not in participants for person in endpoints)) or isinstance(row['cost'], bool) or (not isinstance(row['cost'], int)) or (row['cost'] <= 0):
            raise ValueError('malformed pair row')
        endpoint_key = tuple(endpoints)
        if endpoint_key in seen_endpoints:
            raise ValueError('duplicate endpoint pair')
        seen_endpoints.add(endpoint_key)
    (first, second) = _bipartition(participants, result)
    if len(result) != len(first) * len(second):
        raise ValueError('pair source must contain one record per cross-partition pair')
    return result

def normalized_handoffs(documents: Mapping[str, Any]) -> tuple[tuple[str, ...], tuple[str, ...], dict[tuple[str, str], int]]:
    """Strictly decode the public sequence rule and complete directed costs."""
    policy = documents.get('handoff_policy')
    if not isinstance(policy, Mapping) or set(policy) != {'rule', 'left_order', 'right_order', 'rows'}:
        raise ValueError('handoff policy must use the exact public schema')
    if policy.get('rule') != 'left_sequence_adjacent_right_handoff':
        raise ValueError('unknown handoff rule')
    (left_raw, right_raw, rows) = (policy.get('left_order'), policy.get('right_order'), policy.get('rows'))
    if not isinstance(left_raw, list) or not isinstance(right_raw, list) or (not isinstance(rows, list)) or (not left_raw) or (len(left_raw) != len(right_raw)) or any((not isinstance(item, str) or not item for item in (*left_raw, *right_raw))):
        raise ValueError('malformed handoff orders')
    (left, right) = (tuple(left_raw), tuple(right_raw))
    if len(set(left)) != len(left) or len(set(right)) != len(right) or set(left) & set(right) or (set(left) | set(right) != set(documents.get('participant_order', ()))):
        raise ValueError('handoff orders must partition the public roster')
    costs: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {'from_right', 'to_right', 'cost'}:
            raise ValueError('handoff rows must use the exact schema')
        (source, target, cost) = (row.get('from_right'), row.get('to_right'), row.get('cost'))
        if not isinstance(source, str) or not isinstance(target, str) or source not in set(right) or (target not in set(right)) or (source == target) or isinstance(cost, bool) or (not isinstance(cost, int)) or (cost <= 0) or ((source, target) in costs):
            raise ValueError('malformed, duplicate, or self-loop handoff row')
        costs[source, target] = cost
    expected = {(source, target) for source in right for target in right if source != target}
    if set(costs) != expected:
        raise ValueError('handoff policy must contain every directed off-diagonal edge')
    return (left, right, costs)

def _sequential_problem(documents: Mapping[str, Any]):
    pairs = normalized_pairs(documents)
    (left, right, handoff_costs) = normalized_handoffs(documents)
    left_position = {person: index for (index, person) in enumerate(left)}
    right_position = {person: index for (index, person) in enumerate(right)}
    matrix: list[list[tuple[str, int] | None]] = [[None] * len(right) for _ in left]
    for (pair_id, row) in pairs.items():
        (first, second) = row['participants']
        if first in left_position and second in right_position:
            (row_index, column_index) = (left_position[first], right_position[second])
        elif second in left_position and first in right_position:
            (row_index, column_index) = (left_position[second], right_position[first])
        else:
            raise ValueError('pair does not cross the declared left/right orders')
        if matrix[row_index][column_index] is not None:
            raise ValueError('duplicate sequential assignment cell')
        matrix[row_index][column_index] = (pair_id, int(row['cost']))
    if any((cell is None for row in matrix for cell in row)):
        raise ValueError('sequential assignment matrix is incomplete')
    handoff = [[0 if source == target else handoff_costs[source, target] for target in right] for source in right]
    return (list(left), list(right), matrix, handoff)

def sequential_relaxation_lower_bound(documents: Mapping[str, Any]) -> int:
    """Public lower bound that drops injectivity and path consistency."""
    (_left, _right, matrix, handoff) = _sequential_problem(documents)
    unary_floor = sum((min((cell[1] for cell in row)) for row in matrix))
    handoff_floor = min((handoff[source][target] for source in range(len(handoff)) for target in range(len(handoff)) if source != target))
    return unary_floor + (len(matrix) - 1) * handoff_floor

def objective_normalization(documents: Mapping[str, Any]) -> int:
    """Constant origin shift; the final ``+1`` keeps every legal value positive."""
    return sequential_relaxation_lower_bound(documents) - 1

def matching_raw_cost(documents: Mapping[str, Any], pair_ids: Iterable[str]) -> int:
    (_left, _right, matrix, handoff) = _sequential_problem(documents)
    selected = tuple(pair_ids)
    q = len(matrix)
    if len(selected) != q or len(set(selected)) != len(selected):
        raise ValueError('matching must contain the required number of distinct pairs')
    positions = {matrix[row][column][0]: (row, column) for row in range(q) for column in range(q)}
    if any((pair_id not in positions for pair_id in selected)):
        raise ValueError('unknown pair')
    assignment = [-1] * q
    for pair_id in selected:
        (row, column) = positions[pair_id]
        if assignment[row] != -1:
            raise ValueError('matching chooses more than one pair for a left participant')
        assignment[row] = column
    if sorted(assignment) != list(range(q)):
        raise ValueError('matching must cover every participant exactly once')
    unary = sum((matrix[row][column][1] for (row, column) in enumerate(assignment)))
    transitions = sum((handoff[assignment[row - 1]][assignment[row]] for row in range(1, q)))
    return unary + transitions

def matching_cost(documents: Mapping[str, Any], pair_ids: Iterable[str]) -> int:
    """Lower-bound-normalized cost with unchanged gaps, order, and argmin."""
    value = matching_raw_cost(documents, pair_ids) - objective_normalization(documents)
    if value <= 0:
        raise AssertionError('normalized matching cost must remain positive')
    return value
