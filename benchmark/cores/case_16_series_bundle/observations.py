"""Runtime-only helpers for case_16_series_bundle."""
from __future__ import annotations
from typing import Any, Mapping
from algoworlds.runtime_types import QueryCall
from benchmark.cores.case_16_series_bundle import runtime_data

def _docs(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    return payload['source_documents']
_SERIES_OBSERVATION_CACHE: dict[int, tuple[Mapping[str, Any], dict[str, dict[str, Any]]]] = {}

def _series_observation_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Build compact model-visible factor rows once per immutable document bundle."""
    key = id(documents)
    cached = _SERIES_OBSERVATION_CACHE.get(key)
    if cached is not None and cached[0] is documents:
        return cached[1]
    data = runtime_data.normalized(documents)
    source = documents['series_source']
    source_rows = {row['series_id']: row for row in source['series']}
    result: dict[str, dict[str, Any]] = {}
    for factor in data['factors']:
        series_id = factor['series_id']
        positions = list(factor['positions'])
        if source['encoding'] == 'direct':
            result[series_id] = {'encoding': 'direct', 'series_id': series_id, 'member_positions': positions, 'adjustments': list(factor['adjustments'])}
        else:
            result[series_id] = {'encoding': 'licensed', 'series_id': series_id, 'adjustments': list(factor['adjustments']), 'license_id': source_rows[series_id]['license_id'], 'license_member_positions': positions}
    if len(_SERIES_OBSERVATION_CACHE) >= 16:
        _SERIES_OBSERVATION_CACHE.pop(next(iter(_SERIES_OBSERVATION_CACHE)))
    _SERIES_OBSERVATION_CACHE[key] = (documents, result)
    return result

def _series_observation(documents: Mapping[str, Any], series_id: str) -> dict[str, Any]:
    try:
        return dict(_series_observation_index(documents)[series_id])
    except KeyError as exc:
        raise ValueError('unknown series') from exc

def _series_page_observation(documents: Mapping[str, Any], start: int, length: int) -> dict[str, Any]:
    """Return the canonical page with its repeated field names factored out."""
    source = documents['series_source']
    index = _series_observation_index(documents)
    series_ids = documents['series_order'][start:start + length]
    if source['encoding'] == 'direct':
        return {'encoding': 'direct', 'columns': ['series_id', 'member_positions', 'adjustments'], 'rows': [[series_id, index[series_id]['member_positions'], index[series_id]['adjustments']] for series_id in series_ids]}
    return {'encoding': 'licensed', 'columns': ['series_id', 'license_id', 'license_member_positions', 'adjustments'], 'rows': [[series_id, index[series_id]['license_id'], index[series_id]['license_member_positions'], index[series_id]['adjustments']] for series_id in series_ids]}

def _title_observation(documents: Mapping[str, Any], title_id: str) -> dict[str, Any]:
    return dict(next((row for row in documents['titles'] if row['title_id'] == title_id)))

def _observe(payload: Mapping[str, Any], call: QueryCall) -> Any:
    documents = _docs(payload)
    if call.tool == 'read_title':
        return _title_observation(documents, call.args['title'])
    if call.tool == 'read_series':
        return _series_observation(documents, call.args['series'])
    if call.tool == 'read_series_page':
        (start, length) = (call.args['start'], call.args['length'])
        if (start, length) not in set(runtime_data.series_page_partition(len(documents['series_order']))):
            raise ValueError('invalid or noncanonical series page')
        return _series_page_observation(documents, start, length)
    if call.tool == 'read_title_index':
        title = call.args['title']
        data = runtime_data.normalized(documents)
        lots = [row['lot_id'] for row in data['titles'][title]['lots']]
        position = documents['title_order'].index(title)
        return {'title_id': title, 'lot_ids': sorted(lots), 'series_ids': sorted((series_id for (series_id, factor) in zip(documents['series_order'], data['factors']) if position in factor['positions']))}
    if call.tool == 'read_catalog_window':
        (start, length) = (call.args['start'], call.args['length'])
        return {'titles': [_title_observation(documents, documents['title_order'][index]) for index in range(start, start + length)]}
    if call.tool == 'evaluate_portfolio':
        try:
            value = runtime_data.portfolio_value(documents, call.args['lots'])
        except (KeyError, TypeError, ValueError):
            return {'complete': False, 'legal': False}
        return {'complete': True, 'legal': True, 'settled_value': value}
    raise ValueError(f'unknown query {call.tool!r}')
