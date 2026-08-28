"""Runtime-only helpers for case_21_fixed_charge_migration."""
from __future__ import annotations
from collections import Counter
from typing import Any, Iterable, Mapping
CASE_ID = 'case_21_fixed_charge_migration'
PAGE_SIZE = 16
PACKAGE_COUNT_RANGE = (2, 4)
QUERY_COSTS = {'read_catalog_group': 2, 'read_classification_group': 2, 'read_catalog_window': 5, 'read_classification_window': 5, 'read_catalog_page': 25, 'read_classification_page': 25, 'read_support_policy': 2, 'evaluate_portfolio': 5}

def page_count(groups: int) -> int:
    if type(groups) is not int or groups <= 0:
        raise ValueError('groups must be a positive integer')
    return (groups + PAGE_SIZE - 1) // PAGE_SIZE

def _classification_index(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    classification = documents.get('classification')
    if not isinstance(classification, Mapping):
        raise ValueError('classification must be an object')
    encoding = classification.get('encoding')
    result: dict[str, dict[str, Any]] = {}
    if encoding == 'direct':
        rows = classification.get('rows')
        if not isinstance(rows, list):
            raise ValueError('direct classification rows must be a list')
        if any((not isinstance(row, Mapping) for row in rows)):
            raise ValueError('direct classification rows must be objects')
        expanded = rows
    elif encoding == 'mediated':
        package_rows = classification.get('package_cohorts')
        term_rows = classification.get('cohort_terms')
        if not isinstance(package_rows, list) or not isinstance(term_rows, list):
            raise ValueError('mediated classification relations must be lists')
        if any((not isinstance(row, Mapping) for row in (*package_rows, *term_rows))):
            raise ValueError('mediated classification relations must be objects')
        package_to_cohort: dict[str, str] = {}
        cohort_terms: dict[str, Mapping[str, Any]] = {}
        for row in package_rows:
            (package, cohort) = (row.get('package_id'), row.get('cohort_id'))
            if not isinstance(package, str) or not isinstance(cohort, str) or package in package_to_cohort:
                raise ValueError('malformed package-cohort relation')
            package_to_cohort[package] = cohort
        for row in term_rows:
            cohort = row.get('cohort_id')
            if not isinstance(cohort, str) or cohort in cohort_terms:
                raise ValueError('malformed cohort term')
            cohort_terms[cohort] = row
        if len(set(package_to_cohort.values())) != len(package_to_cohort):
            raise ValueError('mediated cohorts must be private')
        expanded = []
        for (package, cohort) in package_to_cohort.items():
            if cohort not in cohort_terms:
                raise ValueError('package references an unknown cohort')
            term = cohort_terms[cohort]
            expanded.append({'package_id': package, 'mode': term.get('mode'), 'support_domains': term.get('support_domains')})
        if set(package_to_cohort.values()) != set(cohort_terms):
            raise ValueError('unreferenced cohort term')
    else:
        raise ValueError('unknown classification encoding')
    for row in expanded:
        package = row.get('package_id')
        required = row.get('support_domains')
        if not isinstance(package, str) or package in result:
            raise ValueError('duplicate or malformed package classification')
        if not isinstance(required, list) or any((not isinstance(item, str) for item in required)):
            raise ValueError('support_domains must be a string list')
        if len(required) != len(set(required)) or len(required) > 2:
            raise ValueError('support_domains must contain zero, one, or two distinct domains')
        result[package] = {'mode': row.get('mode'), 'support_domains': tuple(sorted(required))}
    return result

def recover_packages(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    if documents.get('package_count_range') != list(PACKAGE_COUNT_RANGE):
        raise ValueError('package_count_range must be [2, 4]')
    objective_offset = documents.get('objective_offset')
    if isinstance(objective_offset, bool) or not isinstance(objective_offset, int) or objective_offset < 0:
        raise ValueError('objective_offset must be a nonnegative integer')
    group_order = documents.get('group_order')
    if not isinstance(group_order, list) or not group_order or len(group_order) != len(set(group_order)):
        raise ValueError('group_order must be a nonempty unique string list')
    if any((not isinstance(group, str) for group in group_order)):
        raise ValueError('group identifiers must be strings')
    policy_rows = documents.get('support_policy')
    if not isinstance(policy_rows, list) or any((not isinstance(row, Mapping) for row in policy_rows)):
        raise ValueError('support_policy must be an object list')
    policy: dict[str, int] = {}
    for row in policy_rows:
        (domain, charge) = (row.get('domain_id'), row.get('fixed_charge'))
        if not isinstance(domain, str) or domain in policy or isinstance(charge, bool) or (not isinstance(charge, int)) or (charge <= 0):
            raise ValueError('malformed support policy')
        policy[domain] = charge
    if not policy:
        raise ValueError('support policy must be nonempty')
    classification = _classification_index(documents)
    catalog_rows = documents.get('catalog')
    if not isinstance(catalog_rows, list) or any((not isinstance(row, Mapping) for row in catalog_rows)):
        raise ValueError('catalog must be an object list')
    packages: dict[str, dict[str, Any]] = {}
    for row in catalog_rows:
        (package, group, base) = (row.get('package_id'), row.get('group_id'), row.get('base_cost'))
        if not isinstance(package, str) or package in packages or group not in group_order or isinstance(base, bool) or (not isinstance(base, int)) or (base < 0) or (package not in classification):
            raise ValueError('malformed catalog row')
        term = classification[package]
        (mode, required) = (term['mode'], tuple(term['support_domains']))
        if mode == 'modern' and required:
            raise ValueError('modern packages cannot require support domains')
        if mode == 'legacy' and (not required):
            raise ValueError('legacy packages must require at least one support domain')
        if mode not in ('modern', 'legacy') or any((domain not in policy for domain in required)):
            raise ValueError('invalid package mode or support-domain reference')
        packages[package] = {'package_id': package, 'group_id': group, 'base_cost': base, 'mode': mode, 'support_domains': required}
    if set(packages) != set(classification):
        raise ValueError('catalog and classification package sets differ')
    counts = Counter((row['group_id'] for row in packages.values()))
    if set(counts) != set(group_order) or any((not PACKAGE_COUNT_RANGE[0] <= count <= PACKAGE_COUNT_RANGE[1] for count in counts.values())):
        raise ValueError('each group must contain two through four packages')
    if any((sum((row['mode'] == 'modern' for row in packages.values() if row['group_id'] == group)) != 1 for group in group_order)):
        raise ValueError('each group must contain exactly one modern package')
    return packages

def packages_by_group(documents: Mapping[str, Any]) -> tuple[tuple[str, ...], ...]:
    packages = recover_packages(documents)
    return tuple((tuple(sorted((package for (package, row) in packages.items() if row['group_id'] == group))) for group in documents['group_order']))

def portfolio_breakdown(documents: Mapping[str, Any], selected: Iterable[str]) -> dict[str, Any]:
    packages = recover_packages(documents)
    groups = packages_by_group(documents)
    chosen = tuple(selected)
    if len(chosen) != len(groups) or len(set(chosen)) != len(chosen):
        raise ValueError('portfolio must select one distinct package per group')
    selected_set = set(chosen)
    if any((package not in packages for package in chosen)) or any((sum((package in selected_set for package in group)) != 1 for group in groups)):
        raise ValueError('portfolio violates group feasibility')
    raw_base_cost = sum((packages[package]['base_cost'] for package in chosen))
    activated = sorted({domain for package in chosen for domain in packages[package]['support_domains']})
    policy = {row['domain_id']: row['fixed_charge'] for row in documents['support_policy']}
    support_cost = sum((policy[domain] for domain in activated))
    objective_offset = documents.get('objective_offset', 0)
    if isinstance(objective_offset, bool) or not isinstance(objective_offset, int) or objective_offset < 0:
        raise ValueError('objective_offset must be a nonnegative integer')
    total = raw_base_cost + support_cost - objective_offset + 1
    return {'raw_base_cost': raw_base_cost, 'support_cost': support_cost, 'objective_offset': objective_offset, 'total_cost': total, 'activated_domains': activated}
