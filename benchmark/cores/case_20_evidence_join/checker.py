"""Runtime-only helpers for case_20_evidence_join."""
from __future__ import annotations
from typing import Any
from .runtime_data import Instance

def checksum_parameters(instance: Instance) -> tuple[int, int]:
    public = instance.get('public')
    if not isinstance(public, dict):
        raise ValueError('instance must expose public checksum parameters')
    modulus = public.get('residue_modulus')
    required = public.get('required_residue')
    if isinstance(modulus, bool) or not isinstance(modulus, int) or modulus < 2:
        raise ValueError('residue modulus must be an integer at least two')
    if isinstance(required, bool) or not isinstance(required, int) or required not in range(modulus):
        raise ValueError('required residue must be an integer modulo the modulus')
    return (modulus, required)

def join_sources(instance: Instance) -> list[dict[str, Any]]:
    (modulus, _) = checksum_parameters(instance)
    docs = instance['source_documents']
    exceptions: dict[str, str] = {}
    for row in docs['E']:
        if not isinstance(row, dict) or set(row) != {'semantic_key', 'tariff_class'} or any((not isinstance(row[field], str) or not row[field] for field in ('semantic_key', 'tariff_class'))):
            raise ValueError('exception rows must use the exact string schema')
        key = row['semantic_key']
        if key in exceptions:
            raise ValueError(f'duplicate exception key: {key}')
        exceptions[key] = row['tariff_class']
    tariffs: dict[tuple[str, str], int] = {}
    for row in docs['T']:
        if not isinstance(row, dict) or set(row) != {'component_id', 'tariff_class', 'rate'} or any((not isinstance(row[field], str) or not row[field] for field in ('component_id', 'tariff_class'))):
            raise ValueError('tariff rows must use the exact schema')
        key = (row['component_id'], row['tariff_class'])
        if key in tariffs:
            raise ValueError(f'duplicate tariff key: {key}')
        rate = row['rate']
        if not isinstance(rate, int) or isinstance(rate, bool) or rate <= 0:
            raise ValueError('tariff rates must be positive integers')
        tariffs[key] = rate
    seen_edges: set[str] = set()
    used_exception_keys: set[str] = set()
    used_tariff_keys: set[tuple[str, str]] = set()
    edges: list[dict[str, Any]] = []
    for row in docs['M']:
        if not isinstance(row, dict) or set(row) != {'edge_id', 'tail', 'head', 'component_id', 'semantic_key', 'stage', 'tariff_quantity', 'residue_delta'}:
            raise ValueError('manifest rows must use the exact schema')
        if any((not isinstance(row[field], str) or not row[field] for field in ('edge_id', 'tail', 'head', 'component_id', 'semantic_key', 'stage'))):
            raise ValueError('manifest identifiers must be nonempty strings')
        edge_id = row['edge_id']
        if edge_id in seen_edges:
            raise ValueError(f'duplicate physical edge id: {edge_id}')
        seen_edges.add(edge_id)
        quantity = row['tariff_quantity']
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError('tariff quantities must be positive integers')
        residue_delta = row.get('residue_delta')
        if isinstance(residue_delta, bool) or not isinstance(residue_delta, int) or residue_delta not in range(modulus):
            raise ValueError('residue deltas must be integers modulo the public modulus')
        semantic_key = row['semantic_key']
        if semantic_key not in exceptions:
            raise ValueError(f'missing exception row: {semantic_key}')
        used_exception_keys.add(semantic_key)
        tariff_key = (row['component_id'], exceptions[semantic_key])
        if tariff_key not in tariffs:
            raise ValueError(f'missing tariff row: {tariff_key}')
        used_tariff_keys.add(tariff_key)
        edges.append({'edge_id': edge_id, 'tail': row['tail'], 'head': row['head'], 'stage': row['stage'], 'cost': quantity * tariffs[tariff_key], 'residue_delta': residue_delta})
    if used_exception_keys != set(exceptions):
        raise ValueError('orphan exception rows are prohibited')
    if used_tariff_keys != set(tariffs):
        raise ValueError('orphan tariff rows are prohibited')
    return edges
