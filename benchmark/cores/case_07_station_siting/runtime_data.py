"""Runtime-only helpers for case_07_station_siting."""
from __future__ import annotations
from typing import Any, Mapping
CASE_ID = 'case_07_station_siting'
QUERY_COSTS = {'read_zone': 2, 'read_demand': 3, 'read_zone_window': 7, 'evaluate_layout': 5}
SUBMIT_TOOL = 'submit_sites'

def _demand_observation(documents: Mapping[str, Any], demand_id: str) -> dict[str, Any]:
    catalog = documents['coverage_catalog']
    demand = next((row for row in catalog['demands'] if row['demand_id'] == demand_id))
    if catalog['encoding'] == 'direct':
        return {'encoding': 'direct', 'demand': dict(demand)}
    connector_id = demand['connector_id']
    connector_rows = [dict(row) for row in catalog['connector_site_rows'] if row['connector_id'] == connector_id]
    return {'encoding': 'mediated', 'demand': dict(demand), 'connector_site_rows': connector_rows}

def normalized_demands(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = documents['coverage_catalog']
    result: dict[str, dict[str, Any]] = {}
    if catalog['encoding'] == 'direct':
        for row in catalog['demands']:
            result[row['demand_id']] = {'reward': row['reward'], 'required_sites': list(row['required_sites'])}
    elif catalog['encoding'] == 'mediated':
        sites_by_connector: dict[str, list[str]] = {}
        for row in catalog['connector_site_rows']:
            sites_by_connector.setdefault(row['connector_id'], []).append(row['site_id'])
        for row in catalog['demands']:
            connector = row['connector_id']
            if connector not in sites_by_connector:
                raise ValueError('demand references an unknown connector')
            result[row['demand_id']] = {'reward': row['reward'], 'required_sites': sorted(sites_by_connector[connector])}
        if {row['connector_id'] for row in catalog['demands']} != set(sites_by_connector):
            raise ValueError('orphan connector incidence')
    else:
        raise ValueError('unknown coverage encoding')
    if set(result) != set(documents['demand_order']):
        raise ValueError('demand order and catalog differ')
    for row in result.values():
        if isinstance(row['reward'], bool) or not isinstance(row['reward'], int) or row['reward'] <= 0 or (len(row['required_sites']) != 2) or (len(set(row['required_sites'])) != 2):
            raise ValueError('every conjunctive demand needs two sites and positive reward')
    return result

def site_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = documents['site_rows']
    result = {row['site_id']: dict(row) for row in rows}
    if len(result) != len(rows):
        raise ValueError('duplicate site id')
    zones = list(documents['zone_order'])
    if len(zones) < 4 or len(set(zones)) != len(zones):
        raise ValueError('zone order must contain at least four distinct zones')
    by_zone: dict[str, list[dict[str, Any]]] = {zone: [] for zone in zones}
    for row in result.values():
        if row.get('zone_id') not in by_zone or isinstance(row.get('option'), bool) or row.get('option') not in (0, 1) or isinstance(row.get('operating_cost'), bool) or (not isinstance(row.get('operating_cost'), int)) or (row['operating_cost'] <= 0):
            raise ValueError('malformed site row')
        by_zone[row['zone_id']].append(row)
    if any((sorted((row['option'] for row in group)) != [0, 1] for group in by_zone.values())):
        raise ValueError('each zone must expose exactly two site options')
    return result

def _semantic_arrays(payload: Mapping[str, Any]) -> tuple[list[list[str]], list[list[int]], list[tuple[int, int, int, int, int]]]:
    """Normalize both arms to sites, unary costs, and banded pair factors.

    Each edge is ``(left_index, right_index, left_option, right_option,
    reward)`` and the returned order is coordinate order, independent of the
    shuffled physical rows.
    """
    documents = payload['source_documents']
    zones = list(documents['zone_order'])
    sites = site_index(documents)
    by_zone_option = {(row['zone_id'], row['option']): row for row in sites.values()}
    site_ids = [[by_zone_option[zone, option]['site_id'] for option in (0, 1)] for zone in zones]
    costs = [[by_zone_option[zone, option]['operating_cost'] for option in (0, 1)] for zone in zones]
    reverse = {site_ids[index][option]: (index, option) for index in range(len(zones)) for option in (0, 1)}
    demands = normalized_demands(documents)
    bandwidth = payload['public'].get('interaction_bandwidth')
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int) or (not 1 <= bandwidth < len(zones)):
        raise ValueError('invalid interaction bandwidth')
    edges: list[tuple[int, int, int, int, int]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for demand_id in documents['demand_order']:
        row = demands[demand_id]
        try:
            endpoints = sorted((reverse[site] for site in row['required_sites']))
        except KeyError as exc:
            raise ValueError('demand references an unknown site') from exc
        ((left_index, left_option), (right_index, right_option)) = endpoints
        if left_index == right_index or right_index - left_index > bandwidth:
            raise ValueError('demand endpoints violate the banded corridor')
        pair = (left_index, right_index)
        if pair in seen_pairs:
            raise ValueError('duplicate zone-pair demand')
        seen_pairs.add(pair)
        edges.append((left_index, right_index, left_option, right_option, row['reward']))
    expected_pairs = {(left, right) for left in range(len(zones)) for right in range(left + 1, min(len(zones), left + bandwidth + 1))}
    if seen_pairs != expected_pairs:
        raise ValueError('coverage catalog is not the complete requested band')
    capacity = payload['public']['max_extended_sites']
    if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 0 or (capacity > len(zones)):
        raise ValueError('invalid extended-site capacity')
    return (site_ids, costs, sorted(edges))

def _bits_value(costs: list[list[int]], edges: list[tuple[int, int, int, int, int]], bits: tuple[int, ...]) -> int:
    value = -sum((costs[index][bit] for (index, bit) in enumerate(bits)))
    for (left_index, right_index, left, right, reward) in edges:
        if bits[left_index] == left and bits[right_index] == right:
            value += reward
    return value

def chosen_bits(payload: Mapping[str, Any], selected_sites: Any) -> tuple[int, ...]:
    if not isinstance(selected_sites, list) or any((not isinstance(item, str) for item in selected_sites)):
        raise ValueError('sites must be a list of site ids')
    if len(set(selected_sites)) != len(selected_sites):
        raise ValueError('site ids must be distinct')
    (site_ids, _costs, _edges) = _semantic_arrays(payload)
    selected = set(selected_sites)
    if len(selected) != len(site_ids):
        raise ValueError('layout must choose exactly one site in every zone')
    bits = []
    for pair in site_ids:
        matches = [option for (option, site) in enumerate(pair) if site in selected]
        if len(matches) != 1:
            raise ValueError('layout must choose exactly one site in every zone')
        bits.append(matches[0])
    if sum(bits) > payload['public']['max_extended_sites']:
        raise ValueError('layout exceeds the global extended-site capacity')
    return tuple(bits)

def raw_layout_value(payload: Mapping[str, Any], selected_sites: Any) -> int:
    """Return covered reward minus the serialized operating costs."""
    bits = chosen_bits(payload, selected_sites)
    (_site_ids, costs, edges) = _semantic_arrays(payload)
    return _bits_value(costs, edges, bits)

def economics_baseline_raw_value(payload: Mapping[str, Any]) -> int:
    """Return the instance-frozen economics baseline used as zero.

    Release payloads freeze this value before their scientific
    counterfactuals are built.  That keeps an unchanged candidate evaluation
    unchanged when a mutation alters only facts outside that query.  Generic
    caller-provided payloads without the field retain the derived behavior.
    """
    frozen = payload.get('objective_baseline_raw_value')
    if frozen is not None:
        if isinstance(frozen, bool) or not isinstance(frozen, int):
            raise ValueError('objective baseline must be an integer')
        return frozen
    (_site_ids, costs, edges) = _semantic_arrays(payload)
    return _bits_value(costs, edges, cheapest_bits(payload))

def layout_value(payload: Mapping[str, Any], selected_sites: Any) -> int:
    """Return improvement over the public economics-only feasible layout.

    The subtracted value is fixed for the instance, observable from site
    economics alone, and therefore preserves every ordering and objective gap.
    """
    return raw_layout_value(payload, selected_sites) - economics_baseline_raw_value(payload)

def cheapest_bits(payload: Mapping[str, Any]) -> tuple[int, ...]:
    """Economics-only attack: ignore every conjunctive reward."""
    (_site_ids, costs, _edges) = _semantic_arrays(payload)
    capacity = payload['public']['max_extended_sites']
    bits = [0 if row[0] <= row[1] else 1 for row in costs]
    if sum(bits) > capacity:
        for index in sorted((i for (i, bit) in enumerate(bits) if bit), key=lambda i: (costs[i][0] - costs[i][1], i))[:sum(bits) - capacity]:
            bits[index] = 0
    return tuple(bits)
