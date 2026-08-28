"""Runtime-only helpers for case_01_subway_transfers."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from algoworlds.runtime_types import Evaluation
from benchmark.cores.case_01_subway_transfers import runtime_data

@dataclass(frozen=True)
class _Problem:
    depth: int
    width: int
    stages: tuple[tuple[Mapping[str, Any], ...], ...]
    rows: Mapping[str, Mapping[str, Any]]
    line_by_leg: Mapping[str, str]
    transfer_cost: Mapping[tuple[str, str], int]
    objective_offset: int
    checksum_modulus: int
    required_ticket_residue: int

def _plain_int(value: Any, label: str, *, minimum: int | None=None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f'{label} must be an integer (bool is forbidden)')
    if minimum is not None and value < minimum:
        raise ValueError(f'{label} must be at least {minimum}')
    return value

def _line_catalog(payload: Mapping[str, Any], used_lines: set[str]) -> tuple[str, ...]:
    """Return the declared line universe, deriving it only for old payloads."""
    declared = payload.get('lines')
    if declared is None:
        return tuple(sorted(used_lines))
    if not isinstance(declared, list) or not declared:
        raise ValueError('lines must be a non-empty list')
    line_ids: list[str] = []
    orders: list[int] = []
    for (index, row) in enumerate(declared):
        if isinstance(row, str):
            line_id = row
        elif isinstance(row, Mapping):
            line_id = row.get('line_id')
            if 'order' in row:
                orders.append(_plain_int(row['order'], f'lines[{index}].order', minimum=0))
        else:
            raise ValueError(f'lines[{index}] must be a line row')
        if not isinstance(line_id, str) or not line_id:
            raise ValueError(f'lines[{index}].line_id must be a non-empty string')
        line_ids.append(line_id)
    if len(set(line_ids)) != len(line_ids):
        raise ValueError('line catalog contains duplicate line identifiers')
    if orders and (len(orders) != len(line_ids) or set(orders) != set(range(len(line_ids)))):
        raise ValueError('line catalog orders must be exactly 0..p-1 when present')
    if not used_lines <= set(line_ids):
        raise ValueError('a leg references a line outside the line catalog')
    if 'line_pool_size' in payload and _plain_int(payload['line_pool_size'], 'line_pool_size', minimum=1) != len(line_ids):
        raise ValueError('line_pool_size disagrees with the line catalog')
    return tuple(line_ids)

def _matrix_rows(payload: Mapping[str, Any]) -> Any:
    """Read the canonical row table without silently masking malformed input."""
    if 'transfer_costs' in payload:
        return payload['transfer_costs']
    if 'transfer_cost_matrix' in payload:
        return payload['transfer_cost_matrix']
    return None

def _parse_transfer_costs(payload: Mapping[str, Any], line_ids: tuple[str, ...]) -> dict[tuple[str, str], int]:
    raw = _matrix_rows(payload)
    line_set = set(line_ids)
    if raw is None:
        if 'big_m' not in payload:
            raise ValueError('payload is missing the directed transfer-cost matrix')
        penalty = _plain_int(payload['big_m'], 'big_m', minimum=0)
        return {(left, right): 0 if left == right else penalty for left in line_ids for right in line_ids}
    if isinstance(raw, Mapping) and set(raw) == {'rows'}:
        raw = raw['rows']
    result: dict[tuple[str, str], int] = {}
    if isinstance(raw, list):
        for (index, row) in enumerate(raw):
            if not isinstance(row, Mapping):
                raise ValueError(f'transfer_costs[{index}] must be an object')
            if set(row) != {'from_line_id', 'to_line_id', 'cost'}:
                raise ValueError('each transfer-cost row must contain exactly from_line_id, to_line_id, and cost')
            left = row['from_line_id']
            right = row['to_line_id']
            if not isinstance(left, str) or not isinstance(right, str):
                raise ValueError('transfer-cost line identifiers must be strings')
            if left not in line_set or right not in line_set:
                raise ValueError('transfer-cost row references an undeclared line')
            pair = (left, right)
            if pair in result:
                raise ValueError('directed transfer-cost matrix contains a duplicate pair')
            result[pair] = _plain_int(row['cost'], f'transfer_costs[{index}].cost', minimum=0)
    elif isinstance(raw, Mapping):
        if set(raw) != line_set:
            raise ValueError('directed transfer-cost matrix has incorrect row keys')
        for left in line_ids:
            row = raw[left]
            if not isinstance(row, Mapping) or set(row) != line_set:
                raise ValueError('directed transfer-cost matrix has incorrect column keys')
            for right in line_ids:
                result[left, right] = _plain_int(row[right], f'transfer_costs[{left!r}][{right!r}]', minimum=0)
    else:
        raise ValueError('transfer_costs must be a complete row list')
    expected = {(left, right) for left in line_ids for right in line_ids}
    missing = expected - set(result)
    extra = set(result) - expected
    if missing or extra:
        raise ValueError(f'directed transfer-cost matrix must cover every ordered line pair (missing={len(missing)}, extra={len(extra)})')
    for line_id in line_ids:
        if result[line_id, line_id] != 0:
            raise ValueError('same-line transfer costs must be zero')
    return result

def _build_problem(payload: Mapping[str, Any]) -> _Problem:
    depth = _plain_int(payload.get('depth'), 'depth', minimum=1)
    width = _plain_int(payload.get('width'), 'width', minimum=1)
    legs = payload.get('legs')
    if not isinstance(legs, list):
        raise ValueError('legs must be a list')
    rows_by_id: dict[str, Mapping[str, Any]] = {}
    grouped: list[list[Mapping[str, Any]]] = [[] for _ in range(depth)]
    for (index, row) in enumerate(legs):
        if not isinstance(row, Mapping):
            raise ValueError(f'legs[{index}] must be an object')
        leg_id = row.get('leg_id')
        if not isinstance(leg_id, str) or not leg_id:
            raise ValueError(f'legs[{index}].leg_id must be a non-empty string')
        if leg_id in rows_by_id:
            raise ValueError('leg catalog contains duplicate leg identifiers')
        stage = _plain_int(row.get('stage'), f'legs[{index}].stage', minimum=0)
        choice = _plain_int(row.get('choice'), f'legs[{index}].choice', minimum=0)
        if stage >= depth:
            raise ValueError('leg stage lies outside the route depth')
        _plain_int(row.get('travel_time'), f'legs[{index}].travel_time', minimum=1)
        residue = _plain_int(row.get('ticket_residue'), f'legs[{index}].ticket_residue', minimum=0)
        if not isinstance(row.get('from_station'), str) or not isinstance(row.get('to_station'), str):
            raise ValueError('leg endpoints must be station identifiers')
        rows_by_id[leg_id] = row
        grouped[stage].append(row)
    stages: list[tuple[Mapping[str, Any], ...]] = []
    previous_destination: str | None = None
    for (stage_index, rows) in enumerate(grouped):
        rows.sort(key=lambda row: (row['choice'], row['leg_id']))
        if len(rows) != width or [row['choice'] for row in rows] != list(range(width)):
            raise ValueError('every stage must contain choices 0..width-1 exactly once')
        origins = {row['from_station'] for row in rows}
        destinations = {row['to_station'] for row in rows}
        if len(origins) != 1 or len(destinations) != 1:
            raise ValueError('all legs in a stage must share its ordered endpoints')
        origin = next(iter(origins))
        destination = next(iter(destinations))
        if stage_index and origin != previous_destination:
            raise ValueError('consecutive route stages are not connected')
        previous_destination = destination
        stages.append(tuple(rows))
    relation = runtime_data.relation_by_leg(payload)
    if set(relation) != set(rows_by_id):
        raise ValueError('route relation does not match the leg catalog')
    line_by_leg: dict[str, str] = {}
    for (leg_id, row) in rows_by_id.items():
        relation_row = relation[leg_id]
        line_id = relation_row.get('line_id')
        if not isinstance(line_id, str) or not line_id:
            raise ValueError('every leg must have one non-empty line identifier')
        if relation_row.get('from_station') != row['from_station'] or relation_row.get('to_station') != row['to_station']:
            raise ValueError('route relation endpoints disagree with the leg catalog')
        line_by_leg[leg_id] = line_id
    line_ids = _line_catalog(payload, set(line_by_leg.values()))
    transfer_cost = _parse_transfer_costs(payload, line_ids)
    objective_offset = _plain_int(payload.get('objective_offset', 0), 'objective_offset')
    checksum_modulus = _plain_int(payload.get('checksum_modulus'), 'checksum_modulus', minimum=2)
    required_ticket_residue = _plain_int(payload.get('required_ticket_residue'), 'required_ticket_residue', minimum=0)
    if required_ticket_residue >= checksum_modulus:
        raise ValueError('required_ticket_residue must be below checksum_modulus')
    if any((row['ticket_residue'] >= checksum_modulus for row in rows_by_id.values())):
        raise ValueError('leg ticket residue must be below checksum_modulus')
    return _Problem(depth=depth, width=width, stages=tuple(stages), rows=rows_by_id, line_by_leg=line_by_leg, transfer_cost=transfer_cost, objective_offset=objective_offset, checksum_modulus=checksum_modulus, required_ticket_residue=required_ticket_residue)

def _route_breakdown(problem: _Problem, decision: Sequence[Any]) -> dict[str, int]:
    if len(decision) != problem.depth:
        raise ValueError('route must select exactly one leg per stage')
    selected: list[Mapping[str, Any]] = []
    for (stage, leg_id) in enumerate(decision):
        if not isinstance(leg_id, str):
            raise ValueError('route leg identifiers must be strings')
        row = problem.rows.get(leg_id)
        if row is None or row['stage'] != stage:
            raise ValueError('route selects an unknown leg or a leg from the wrong stage')
        selected.append(row)
    for (left, right) in zip(selected, selected[1:]):
        if left['to_station'] != right['from_station']:
            raise ValueError('route contains disconnected consecutive legs')
    lines = [problem.line_by_leg[row['leg_id']] for row in selected]
    transfer_cost = sum((problem.transfer_cost[left, right] for (left, right) in zip(lines, lines[1:])))
    travel_time = sum((int(row['travel_time']) for row in selected))
    ticket_residue = sum((int(row['ticket_residue']) for row in selected)) % problem.checksum_modulus
    if ticket_residue != problem.required_ticket_residue:
        raise ValueError('route violates the published ticket checksum')
    raw_cost = travel_time + transfer_cost
    return {'transfers': sum((left != right for (left, right) in zip(lines, lines[1:]))), 'travel_time': travel_time, 'transfer_cost': transfer_cost, 'ticket_residue': ticket_residue, 'raw_cost': raw_cost, 'encoded_cost': raw_cost - problem.objective_offset}

def evaluate_route(payload: Mapping[str, Any], decision: Any) -> Evaluation:
    problem = _build_problem(payload)
    if not isinstance(decision, list):
        return Evaluation(False, None)
    try:
        breakdown = _route_breakdown(problem, decision)
    except ValueError:
        return Evaluation(False, None)
    return Evaluation(True, breakdown['encoded_cost'])

def route_breakdown(payload: Mapping[str, Any], decision: list[str]) -> dict[str, int]:
    """Return the raw components and the offset-normalized scalar objective."""
    if not isinstance(decision, list):
        raise ValueError('route must be a leg list')
    return _route_breakdown(_build_problem(payload), decision)
