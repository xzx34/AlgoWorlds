"""Runtime-only helpers for case_14_override."""
from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any, Iterable, Mapping
CASE_ID = 'case_14_override'
QUERY_COSTS = {'read_catalog_stage': 2, 'read_authorization_stage': 2, 'read_catalog_window': 7, 'read_authorization_window': 7, 'read_override_policy': 3, 'evaluate_package': 5}

def _plain_int(value: Any, label: str, *, minimum: int=0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{label} must be an integer at least {minimum}')
    return value

def _exact_row(row: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(row, Mapping) or set(row) != keys:
        raise ValueError(f'{label} must contain exactly {sorted(keys)}')
    return row

def contraction_view(documents: Mapping[str, Any]) -> list[dict[str, Any]]:
    authorization = documents.get('authorization')
    if not isinstance(authorization, Mapping):
        raise ValueError('authorization must be an object')
    if authorization.get('encoding') == 'direct':
        if set(authorization) != {'encoding', 'rows'}:
            raise ValueError('direct authorization has unexpected fields')
        rows = authorization.get('rows')
        if not isinstance(rows, list):
            raise ValueError('direct authorization rows must be a list')
        result = []
        for (index, raw) in enumerate(rows):
            row = _exact_row(raw, {'stage_id', 'predecessor_id', 'successor_id', 'handoff_cost'}, f'authorization.rows[{index}]')
            if not all((isinstance(row[key], str) and row[key] for key in ('stage_id', 'predecessor_id', 'successor_id'))):
                raise ValueError('authorization identifiers must be non-empty strings')
            result.append({'stage_id': row['stage_id'], 'predecessor_id': row['predecessor_id'], 'successor_id': row['successor_id'], 'handoff_cost': _plain_int(row['handoff_cost'], f'authorization.rows[{index}].handoff_cost')})
    elif authorization.get('encoding') == 'staged':
        if set(authorization) != {'encoding', 'authorization_entries', 'authorization_exits'}:
            raise ValueError('staged authorization has unexpected fields')
        raw_entries = authorization.get('authorization_entries')
        raw_exits = authorization.get('authorization_exits')
        if not isinstance(raw_entries, list) or not isinstance(raw_exits, list):
            raise ValueError('staged authorization halves must be lists')
        entries: dict[str, tuple[str, str]] = {}
        exits: dict[str, tuple[str, str, int]] = {}
        for (index, raw) in enumerate(raw_entries):
            row = _exact_row(raw, {'stage_id', 'predecessor_id', 'approval_id'}, f'authorization.authorization_entries[{index}]')
            if not all((isinstance(row[key], str) and row[key] for key in row)):
                raise ValueError('authorization entry identifiers must be non-empty strings')
            approval = row['approval_id']
            if approval in entries:
                raise ValueError('duplicate authorization entry')
            entries[approval] = (row['stage_id'], row['predecessor_id'])
        for (index, raw) in enumerate(raw_exits):
            row = _exact_row(raw, {'stage_id', 'approval_id', 'successor_id', 'handoff_cost'}, f'authorization.authorization_exits[{index}]')
            if not all((isinstance(row[key], str) and row[key] for key in ('stage_id', 'approval_id', 'successor_id'))):
                raise ValueError('authorization exit identifiers must be non-empty strings')
            approval = row['approval_id']
            if approval in exits:
                raise ValueError('duplicate authorization exit')
            exits[approval] = (row['stage_id'], row['successor_id'], _plain_int(row['handoff_cost'], f'authorization.authorization_exits[{index}].handoff_cost'))
        if set(entries) != set(exits):
            raise ValueError('staged authorization halves do not match')
        result = []
        for approval in entries:
            (entry_stage, predecessor) = entries[approval]
            (exit_stage, successor, handoff) = exits[approval]
            if entry_stage != exit_stage:
                raise ValueError('approval halves disagree on stage')
            result.append({'stage_id': entry_stage, 'predecessor_id': predecessor, 'successor_id': successor, 'handoff_cost': handoff})
    else:
        raise ValueError('unknown authorization encoding')
    return sorted(result, key=lambda row: (row['stage_id'], row['predecessor_id'], row['successor_id']))

def recover_model(documents: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(documents, Mapping):
        raise ValueError('source documents must be an object')
    stage_order = documents.get('stage_order')
    source = documents.get('source_id')
    width = documents.get('declared_width')
    degree = documents.get('declared_transition_degree')
    if not isinstance(stage_order, list) or len(stage_order) < 2 or len(set(stage_order)) != len(stage_order) or (not all((isinstance(stage, str) for stage in stage_order))) or (not isinstance(source, str)) or isinstance(width, bool) or (not isinstance(width, int)) or (width < 2) or isinstance(degree, bool) or (not isinstance(degree, int)) or (not 1 <= degree < width):
        raise ValueError('malformed scale, stage order, or source')
    checksum = documents.get('checksum')
    if not isinstance(checksum, Mapping) or set(checksum) != {'modulus', 'required_residue'}:
        raise ValueError('checksum must contain exactly modulus and required_residue')
    modulus = _plain_int(checksum['modulus'], 'checksum.modulus', minimum=2)
    required_residue = _plain_int(checksum['required_residue'], 'checksum.required_residue')
    if required_residue >= modulus:
        raise ValueError('required checksum residue lies outside the modulus')
    stage_set = set(stage_order)
    policy: dict[str, int] = {}
    raw_policy = documents.get('override_policy')
    if not isinstance(raw_policy, list):
        raise ValueError('override_policy must be a list')
    for (index, raw) in enumerate(raw_policy):
        row = _exact_row(raw, {'override_code', 'cost_adjustment'}, f'override_policy[{index}]')
        (code, adjustment) = (row['override_code'], row['cost_adjustment'])
        if not isinstance(code, str) or not code or code in policy or isinstance(adjustment, bool) or (not isinstance(adjustment, int)) or (adjustment < 0):
            raise ValueError('malformed override policy')
        policy[code] = adjustment
    plays: dict[str, dict[str, Any]] = {}
    per_stage = Counter()
    used_codes: set[str] = set()
    raw_catalog = documents.get('catalog')
    if not isinstance(raw_catalog, list):
        raise ValueError('catalog must be a list')
    for (index, raw) in enumerate(raw_catalog):
        row = _exact_row(raw, {'stage_id', 'play_id', 'base_cost', 'override_code', 'clearance_residue'}, f'catalog[{index}]')
        (stage, play, base, code, residue) = (row['stage_id'], row['play_id'], row['base_cost'], row['override_code'], row['clearance_residue'])
        if stage not in stage_set or not isinstance(play, str) or (not play) or (play in plays) or isinstance(base, bool) or (not isinstance(base, int)) or (base < 0) or (code not in policy) or (code in used_codes) or isinstance(residue, bool) or (not isinstance(residue, int)) or (not 0 <= residue < modulus):
            raise ValueError('malformed catalog row, clearance residue, or non-unique override code')
        used_codes.add(code)
        plays[play] = {'stage_id': stage, 'base_cost': base, 'override_code': code, 'effective_cost': base + policy[code], 'clearance_residue': residue}
        per_stage[stage] += 1
    if set(policy) != used_codes or any((per_stage[stage] != width for stage in stage_order)):
        raise ValueError('catalog/policy mismatch or wrong stage width')
    stage_index = {stage: index for (index, stage) in enumerate(stage_order)}
    allowed_edges: set[tuple[str, str]] = set()
    handoff_costs: dict[tuple[str, str], int] = {}
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    boundary_counts = Counter()
    for row in contraction_view(documents):
        (stage, predecessor, successor, handoff) = (row.get('stage_id'), row.get('predecessor_id'), row.get('successor_id'), row.get('handoff_cost'))
        if stage not in stage_set or successor not in plays or isinstance(handoff, bool) or (not isinstance(handoff, int)) or (handoff < 0):
            raise ValueError('authorization refers to an unknown stage or successor')
        index = stage_index[stage]
        if plays[successor]['stage_id'] != stage:
            raise ValueError('authorization successor belongs to the wrong stage')
        valid_predecessor = predecessor == source if index == 0 else predecessor in plays and plays[predecessor]['stage_id'] == stage_order[index - 1]
        edge = (predecessor, successor)
        if not valid_predecessor or edge in allowed_edges:
            raise ValueError('malformed or duplicate authorization relation')
        allowed_edges.add(edge)
        handoff_costs[edge] = handoff
        incoming[successor].append(predecessor)
        outgoing[predecessor].append(successor)
        boundary_counts[index] += 1
    if boundary_counts[0] != width or any((boundary_counts[index] != width * degree for index in range(1, len(stage_order)))):
        raise ValueError('authorization does not match the declared regular scale')
    groups = tuple((tuple(sorted((play for (play, row) in plays.items() if row['stage_id'] == stage))) for stage in stage_order))
    if len(outgoing[source]) != width or any((len(outgoing[play]) != degree for group in groups[:-1] for play in group)):
        raise ValueError('authorization does not have the declared predecessor out-degree')
    if any((not incoming[play] for group in groups for play in group)):
        raise ValueError('every play must be reachable from the preceding layer')
    return {'stage_order': list(stage_order), 'source_id': source, 'width': width, 'degree': degree, 'plays': plays, 'groups': groups, 'allowed_edges': allowed_edges, 'handoff_costs': handoff_costs, 'incoming': {key: sorted(value) for (key, value) in incoming.items()}, 'outgoing': {key: sorted(value) for (key, value) in outgoing.items()}, 'policy': policy, 'checksum_modulus': modulus, 'required_residue': required_residue}

def package_breakdown(documents: Mapping[str, Any], selected: Iterable[str]) -> dict[str, Any]:
    if isinstance(selected, (str, bytes)):
        raise ValueError('selected package must be an iterable of play ids')
    chosen = list(selected)
    model = recover_model(documents)
    if len(chosen) != len(model['groups']) or len(set(chosen)) != len(chosen):
        raise ValueError('package must choose exactly one distinct play per stage')
    chosen_set = set(chosen)
    ordered: list[str] = []
    for group in model['groups']:
        items = [play for play in group if play in chosen_set]
        if len(items) != 1:
            raise ValueError('package must choose exactly one play per stage')
        ordered.append(items[0])
    predecessor = model['source_id']
    authorization_cost = 0
    for play in ordered:
        if (predecessor, play) not in model['allowed_edges']:
            raise ValueError('package violates an authorization relation')
        authorization_cost += model['handoff_costs'][predecessor, play]
        predecessor = play
    clearance_residue = sum((model['plays'][play]['clearance_residue'] for play in ordered)) % model['checksum_modulus']
    if clearance_residue != model['required_residue']:
        raise ValueError('package violates the clearance checksum')
    base = sum((model['plays'][play]['base_cost'] for play in ordered))
    adjustment = sum((model['policy'][model['plays'][play]['override_code']] for play in ordered))
    return {'ordered_plays': ordered, 'base_cost': base, 'override_adjustment': adjustment, 'authorization_cost': authorization_cost, 'clearance_residue': clearance_residue, 'total_cost': base + adjustment + authorization_cost}
