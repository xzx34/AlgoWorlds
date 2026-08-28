"""Runtime-only helpers for case_01_subway_transfers."""
from __future__ import annotations
from typing import Any, Mapping

def line_order(payload: Mapping[str, Any]) -> tuple[str, ...]:
    rows = payload.get('lines')
    if not isinstance(rows, list) or not rows:
        raise ValueError('line catalog is missing')
    ordered = sorted(rows, key=lambda row: row.get('order', -1))
    result = tuple((row.get('line_id') for row in ordered))
    if any((not isinstance(line_id, str) or not line_id for line_id in result)) or len(set(result)) != len(result) or [row.get('order') for row in ordered] != list(range(len(ordered))):
        raise ValueError('line catalog is malformed')
    if len(result) != payload.get('line_pool_size'):
        raise ValueError('line catalog has the wrong size')
    return result

def transfer_cost_index(payload: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    lines = line_order(payload)
    expected = {(left, right) for left in lines for right in lines}
    rows = payload.get('transfer_costs')
    if not isinstance(rows, list):
        raise ValueError('transfer-cost source must be a row list')
    result: dict[tuple[str, str], int] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError('transfer-cost row is malformed')
        key = (row.get('from_line_id'), row.get('to_line_id'))
        cost = row.get('cost')
        if key in result or key not in expected:
            raise ValueError('transfer-cost matrix has a duplicate or unknown cell')
        if isinstance(cost, bool) or not isinstance(cost, int) or cost < 0:
            raise ValueError('transfer costs must be nonnegative integers')
        if key[0] == key[1] and cost != 0:
            raise ValueError('remaining on one line must cost zero')
        result[key] = cost
    if set(result) != expected:
        raise ValueError('transfer-cost matrix must be complete')
    return result

def relation_by_leg(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    relation = payload['relation']
    if relation['encoding'] == 'direct':
        result = {row['leg_id']: {'from_station': row['from_station'], 'to_station': row['to_station'], 'line_id': row['line_id']} for row in relation['rows']}
        if len(result) != len(relation['rows']):
            raise ValueError('direct relation contains a duplicate leg')
    elif relation['encoding'] == 'platform_mediated':
        station_by_platform = {row['platform_id']: row['station_id'] for row in relation['station_platforms']}
        line_by_platform = {row['platform_id']: row['line_id'] for row in relation['platform_lines']}
        if len(station_by_platform) != len(relation['station_platforms']):
            raise ValueError('duplicate station-platform row')
        if len(line_by_platform) != len(relation['platform_lines']):
            raise ValueError('duplicate platform-line row')
        result = {}
        for row in relation['leg_platforms']:
            if row['leg_id'] in result:
                raise ValueError('mediated relation contains a duplicate leg')
            from_platform = row['from_platform']
            to_platform = row['to_platform']
            if line_by_platform.get(from_platform) != line_by_platform.get(to_platform):
                raise ValueError("a leg's endpoint platforms disagree on line membership")
            if from_platform not in station_by_platform or to_platform not in station_by_platform:
                raise ValueError('a leg references an unknown platform')
            result[row['leg_id']] = {'from_station': station_by_platform[from_platform], 'to_station': station_by_platform[to_platform], 'line_id': line_by_platform[from_platform]}
    else:
        raise ValueError('unknown route relation encoding')
    expected = {row['leg_id'] for row in payload['legs']}
    if set(result) != expected or any((row['line_id'] not in line_order(payload) for row in result.values())):
        raise ValueError('relation rows do not match the leg and line catalogs')
    return result

def legs_by_stage(payload: Mapping[str, Any]) -> tuple[tuple[dict[str, Any], ...], ...]:
    depth = payload['depth']
    width = payload['width']
    if type(depth) is not int or depth < 2 or type(width) is not int or (width < 3):
        raise ValueError('route scale is malformed')
    stations = sorted(payload['stations'], key=lambda row: row['order'])
    if len(stations) != depth + 1 or [row['order'] for row in stations] != list(range(depth + 1)):
        raise ValueError('station chain is malformed')
    grouped = []
    for stage in range(depth):
        rows = tuple(sorted((row for row in payload['legs'] if row['stage'] == stage), key=lambda row: row['choice']))
        if len(rows) != width or [row['choice'] for row in rows] != list(range(width)):
            raise ValueError('every route stage must expose the configured choice width')
        if any((row['from_station'] != stations[stage]['station_id'] or row['to_station'] != stations[stage + 1]['station_id'] or isinstance(row['travel_time'], bool) or (not isinstance(row['travel_time'], int)) or (row['travel_time'] <= 0) for row in rows)):
            raise ValueError('leg topology or travel time is malformed')
        grouped.append(rows)
    if sum((len(rows) for rows in grouped)) != len(payload['legs']):
        raise ValueError('leg catalog contains an out-of-range stage')
    relation_by_leg(payload)
    return tuple(grouped)
