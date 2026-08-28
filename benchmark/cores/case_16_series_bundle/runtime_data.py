"""Runtime-only helpers for case_16_series_bundle."""
from __future__ import annotations
from typing import Any, Iterable, Mapping
CASE_ID = 'case_16_series_bundle'
QUERY_COSTS = {'read_title': 3, 'read_series': 3, 'read_series_page': 12, 'read_title_index': 4, 'read_catalog_window': 8, 'evaluate_portfolio': 1000}
SUBMIT_TOOL = 'submit_portfolio'
_SERIES_PAGE_SIZE = 24

def series_page_partition(size: int) -> tuple[tuple[int, int], ...]:
    if size < 1:
        raise ValueError('series size must be positive')
    return tuple(((start, min(_SERIES_PAGE_SIZE, size - start)) for start in range(0, size, _SERIES_PAGE_SIZE)))

def normalized(documents: Mapping[str, Any]) -> dict[str, Any]:
    title_order = list(documents['title_order'])
    title_rows = {row['title_id']: row for row in documents['titles']}
    if len(title_order) < 2 or len(set(title_order)) != len(title_order) or set(title_rows) != set(title_order):
        raise ValueError('title source does not match title order')
    lots: dict[str, dict[str, Any]] = {}
    lot_title: dict[str, str] = {}
    title_position = {title_id: index for (index, title_id) in enumerate(title_order)}
    for title_id in title_order:
        rows = title_rows[title_id]['lots']
        if len(rows) != 2:
            raise ValueError('every title must expose two lots')
        for row in rows:
            (lot_id, value) = (row['lot_id'], row['base_value'])
            if not isinstance(lot_id, str) or lot_id in lots or isinstance(value, bool) or (not isinstance(value, int)) or (value <= 0):
                raise ValueError('malformed lot row')
            lots[lot_id] = {'base_value': value, 'title_id': title_id}
            lot_title[lot_id] = title_id
    source = documents['series_source']
    series: dict[str, dict[str, Any]] = {}
    if source['encoding'] == 'direct':
        for row in source['series']:
            series[row['series_id']] = {'adjustments': list(row['adjustments']), 'lot_pairs': [list(pair) for pair in row['lot_pairs']]}
    elif source['encoding'] == 'licensed':
        by_license: dict[str, list[list[str]]] = {}
        for row in source['license_rows']:
            by_license.setdefault(row['license_id'], []).append([row['zero_lot_id'], row['one_lot_id']])
        for row in source['series']:
            if row['license_id'] not in by_license:
                raise ValueError('series references an unknown license')
            series[row['series_id']] = {'adjustments': list(row['adjustments']), 'lot_pairs': by_license[row['license_id']]}
        if {row['license_id'] for row in source['series']} != set(by_license):
            raise ValueError('orphan license')
    else:
        raise ValueError('unknown series encoding')
    if set(series) != set(documents['series_order']):
        raise ValueError('series source does not match series order')
    choices: list[tuple[str, str]] = []
    choice0_values: list[int] = []
    choice1_values: list[int] = []
    for title_id in title_order:
        ordered = sorted(title_rows[title_id]['lots'], key=lambda row: row['lot_id'])
        pair = (ordered[0]['lot_id'], ordered[1]['lot_id'])
        choices.append(pair)
        choice0_values.append(ordered[0]['base_value'])
        choice1_values.append(ordered[1]['base_value'])
    factors = []
    actual_max_span = 1
    for series_id in documents['series_order']:
        row = series[series_id]
        lot_pairs = list(row['lot_pairs'])
        adjustments = list(row['adjustments'])
        if len(lot_pairs) not in (2, 3) or len(adjustments) != 1 << len(lot_pairs) or any((isinstance(value, bool) or not isinstance(value, int) for value in adjustments)) or (len(set(adjustments)) < 2) or any((not isinstance(pair, list) or len(pair) != 2 or pair[0] == pair[1] or any((lot not in lots for lot in pair)) for pair in lot_pairs)):
            raise ValueError('malformed series row')
        by_position = {title_position[lot_title[pair[0]]]: pair for pair in lot_pairs}
        positions = sorted(by_position)
        if len(by_position) != len(lot_pairs) or any((lot_title[pair[0]] != lot_title[pair[1]] for pair in lot_pairs)) or any((set(by_position[position]) != set(choices[position]) for position in positions)):
            raise ValueError('series potential must use both choices of distinct titles')
        span = positions[-1] - positions[0] + 1
        actual_max_span = max(actual_max_span, span)
        factors.append({'series_id': series_id, 'adjustments': tuple(adjustments), 'positions': tuple(positions)})
    declared_span = documents['declared_max_series_span']
    if isinstance(declared_span, bool) or not isinstance(declared_span, int) or declared_span < 2 or (actual_max_span != declared_span):
        raise ValueError('declared max series span does not match the factors')
    return {'titles': title_rows, 'lots': lots, 'lot_title': lot_title, 'series': series, 'choices': choices, 'plain_values': choice0_values, 'collectible_values': choice1_values, 'factors': factors, 'max_span': actual_max_span}

def _value_from_bits(data: Mapping[str, Any], bits: tuple[int, ...]) -> int:
    value = sum(((data['plain_values'][index] if bit == 0 else data['collectible_values'][index]) - min(data['plain_values'][index], data['collectible_values'][index]) for (index, bit) in enumerate(bits)))
    for factor in data['factors']:
        code = 0
        for position in factor['positions']:
            code = code << 1 | bits[position]
        value += factor['adjustments'][code]
    return value

def portfolio_value(documents: Mapping[str, Any], lots: Iterable[str]) -> int:
    data = normalized(documents)
    selected = tuple(lots)
    if len(selected) != len(documents['title_order']) or len(set(selected)) != len(selected):
        raise ValueError('portfolio must choose exactly one distinct lot per title')
    if any((lot not in data['lots'] for lot in selected)):
        raise ValueError('unknown lot')
    titles = [data['lot_title'][lot] for lot in selected]
    if len(set(titles)) != len(documents['title_order']):
        raise ValueError('portfolio must choose one lot per title')
    chosen = set(selected)
    bits = tuple((1 if pair[1] in chosen else 0 for pair in data['choices']))
    return _value_from_bits(data, bits)
