"""Runtime-only helpers for case_17_machine_layout."""
from __future__ import annotations
from typing import Any, Mapping
CASE_ID = 'case_17_machine_layout'
QUERY_COSTS = {'survey_floor': 2, 'read_flow_row': 3, 'read_distance_row': 5, 'read_settlement_row': 4, 'read_flow_block': 12, 'read_distance_block': 12, 'read_settlement_block': 15, 'evaluate_layout': 7}
SUBMIT_TOOL = 'submit_layout'

def flow_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    result: dict[tuple[str, str], int] = {}
    for row in payload['flows']:
        key = tuple(sorted((row['machine_a'], row['machine_b'])))
        if key in result:
            raise ValueError('duplicate machine pair')
        result[key] = row['throughput']
    return result

def distance_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    result: dict[tuple[str, str], int] = {}
    for row in payload['distances']:
        key = tuple(sorted((row['slot_a'], row['slot_b'])))
        if key in result:
            raise ValueError('duplicate slot pair')
        result[key] = row['distance']
    return result

def settlement_lookup(payload: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    relation = payload['settlement']
    if relation['encoding'] == 'direct':
        rows = relation['machine_slots']
        result = {(row['machine_id'], row['slot_id']): row['adjustment'] for row in rows}
    elif relation['encoding'] == 'cell_anchor_mediated':
        anchor_slot = {row['anchor_id']: row['slot_id'] for row in relation['anchors']}
        cell_slot = {row['cell_id']: anchor_slot[row['anchor_id']] for row in relation['cells']}
        result = {(row['machine_id'], cell_slot[row['cell_id']]): row['adjustment'] for row in relation['machine_cells']}
    else:
        raise ValueError('unknown settlement encoding')
    expected = len(payload['machines']) * len(payload['slots'])
    if len(result) != expected:
        raise ValueError('settlement must define every machine-slot pair exactly once')
    return result
