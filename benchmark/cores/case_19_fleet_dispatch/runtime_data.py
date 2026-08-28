"""Runtime-only helpers for case_19_fleet_dispatch."""
from __future__ import annotations
from typing import Any, Mapping
CASE_ID = 'case_19_fleet_dispatch'
QUERY_COSTS = {'read_fleet_policy': 2, 'read_job': 2, 'read_vehicle_contract': 4, 'read_route_row': 5, 'read_dispatch_window': 11, 'evaluate_assignment': 5}
SUBMIT_TOOL = 'submit_assignment'

def normalized_routes(documents: Mapping[str, Any]) -> dict[tuple[str, str], int]:
    catalog = documents['eligibility_catalog']
    result: dict[tuple[str, str], int] = {}
    if catalog['encoding'] == 'direct':
        for row in catalog['assignment_rows']:
            result[row['vehicle_id'], row['job_id']] = row['route_cost']
    elif catalog['encoding'] == 'mediated':
        shift_to_vehicle = {row['shift_id']: row['vehicle_id'] for row in catalog['vehicle_shift_rows']}
        if len(shift_to_vehicle) != len(catalog['vehicle_shift_rows']):
            raise ValueError('duplicate shift id')
        for row in catalog['shift_job_rows']:
            if row['shift_id'] not in shift_to_vehicle:
                raise ValueError('job incidence references an unknown shift')
            result[shift_to_vehicle[row['shift_id']], row['job_id']] = row['route_cost']
        if set(shift_to_vehicle) != {row['shift_id'] for row in catalog['shift_job_rows']}:
            raise ValueError('orphan vehicle shift')
    else:
        raise ValueError('unknown eligibility encoding')
    expected = {(vehicle, job) for vehicle in documents['vehicle_order'] for job in documents['job_order']}
    if set(result) != expected or any((isinstance(cost, bool) or not isinstance(cost, int) or cost <= 0 for cost in result.values())):
        raise ValueError('route matrix must contain one positive cost per vehicle-job pair')
    return result

def contract_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result = {row['vehicle_id']: dict(row) for row in documents['contract_rows']}
    if set(result) != set(documents['vehicle_order']):
        raise ValueError('contracts must cover the vehicle roster exactly')
    for row in result.values():
        if any((isinstance(row[key], bool) or not isinstance(row[key], int) or row[key] <= 0 for key in ('capacity', 'fixed_contract_cost'))):
            raise ValueError('contract capacity and fixed cost must be positive integers')
    return result

def job_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    result = {row['job_id']: dict(row) for row in documents['job_rows']}
    if set(result) != set(documents['job_order']):
        raise ValueError('jobs must cover the job roster exactly')
    if any((isinstance(row['load'], bool) or not isinstance(row['load'], int) or row['load'] <= 0 for row in result.values())):
        raise ValueError('job loads must be positive integers')
    return result

def _route_row_observation(documents: Mapping[str, Any], vehicle: str) -> dict[str, Any]:
    catalog = documents['eligibility_catalog']
    if catalog['encoding'] == 'direct':
        return {'encoding': 'direct', 'rows': [dict(row) for row in catalog['assignment_rows'] if row['vehicle_id'] == vehicle]}
    vehicle_shift = next((row for row in catalog['vehicle_shift_rows'] if row['vehicle_id'] == vehicle))
    return {'encoding': 'mediated', 'vehicle_shift': dict(vehicle_shift), 'rows': [dict(row) for row in catalog['shift_job_rows'] if row['shift_id'] == vehicle_shift['shift_id']]}

def _job_route_observations(documents: Mapping[str, Any], jobs: set[str]) -> dict[str, Any]:
    catalog = documents['eligibility_catalog']
    if catalog['encoding'] == 'direct':
        return {'encoding': 'direct', 'assignment_rows': [dict(row) for row in catalog['assignment_rows'] if row['job_id'] in jobs]}
    shifts = list(catalog['vehicle_shift_rows'])
    return {'encoding': 'mediated', 'vehicle_shift_rows': [dict(row) for row in shifts], 'shift_job_rows': [dict(row) for row in catalog['shift_job_rows'] if row['job_id'] in jobs]}

def assignment_raw_value(payload: Mapping[str, Any], assignment: Any) -> int:
    """Unnormalized route-plus-fixed objective after complete legality checks."""
    if not isinstance(assignment, dict):
        raise ValueError('assignment must map every job id to one vehicle id')
    documents = payload['source_documents']
    if set(assignment) != set(documents['job_order']) or any((not isinstance(job, str) or not isinstance(vehicle, str) for (job, vehicle) in assignment.items())):
        raise ValueError('assignment must cover the job roster exactly')
    contracts = contract_index(documents)
    jobs = job_index(documents)
    routes = normalized_routes(documents)
    loads = {vehicle: 0 for vehicle in documents['vehicle_order']}
    for (job, vehicle) in assignment.items():
        if (vehicle, job) not in routes:
            raise ValueError('assignment uses an ineligible vehicle-job pair')
        loads[vehicle] += jobs[job]['load']
    if any((loads[vehicle] > contracts[vehicle]['capacity'] for vehicle in loads)):
        raise ValueError('assignment exceeds a vehicle capacity')
    used = {vehicle for (vehicle, load) in loads.items() if load > 0}
    return sum((routes[vehicle, job] for (job, vehicle) in assignment.items())) + sum((contracts[vehicle]['fixed_contract_cost'] for vehicle in used))

def objective_normalization(payload: Mapping[str, Any]) -> int:
    """Observable lower-bound constant subtracted from every legal assignment.

    Route column minima are unavoidable because every job is assigned once.
    Capacities imply a lower bound on the number of active vehicles, whose
    cheapest fixed prices are also unavoidable.  Subtracting this same constant
    from *every* legal decision preserves all gaps, ordering, and optima while
    removing an irrelevant additive scale from the shared score curve.
    """
    documents = payload['source_documents']
    vehicles = list(documents['vehicle_order'])
    jobs = list(documents['job_order'])
    contracts = contract_index(documents)
    demands = job_index(documents)
    routes = normalized_routes(documents)
    total_load = sum((demands[job]['load'] for job in jobs))
    cumulative_capacity = 0
    required_vehicles = 0
    for capacity in sorted((contracts[vehicle]['capacity'] for vehicle in vehicles), reverse=True):
        cumulative_capacity += capacity
        required_vehicles += 1
        if cumulative_capacity >= total_load:
            break
    if cumulative_capacity < total_load:
        raise ValueError('fleet capacities cannot carry the total job load')
    route_floor = sum((min((routes[vehicle, job] for vehicle in vehicles)) for job in jobs))
    fixed_floor = sum(sorted((contracts[vehicle]['fixed_contract_cost'] for vehicle in vehicles))[:required_vehicles])
    return route_floor + fixed_floor - 1

def assignment_value(payload: Mapping[str, Any], assignment: Any) -> int:
    """Lower-bound-normalized objective; always positive for a legal mapping."""
    value = assignment_raw_value(payload, assignment) - objective_normalization(payload)
    if value <= 0:
        raise AssertionError('normalized legal fleet objective must be positive')
    return value
