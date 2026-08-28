"""Runtime-only helpers for case_03_basket_assembly."""
from __future__ import annotations
from collections import Counter
from typing import Any, Iterable, Mapping
CASE_ID = 'case_03_basket_assembly'
BASE_QUERY_COSTS = {'read_requirements': 2, 'read_bundle': 1, 'read_item_index': 5, 'read_catalog_window': 8, 'evaluate_basket': 16}
QUERY_TOOLS = tuple(BASE_QUERY_COSTS)
SUBMIT_TOOL = 'submit_tickets'

def normalized_bundles(documents: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    catalog = documents['catalog']
    result: dict[str, dict[str, Any]] = {}
    if catalog['encoding'] == 'direct':
        for row in catalog['bundles']:
            result[row['bundle_id']] = {'price': row['price'], 'quantities': dict(row['quantities'])}
    elif catalog['encoding'] == 'mediated':
        recipe_items: dict[str, dict[str, int]] = {}
        for row in catalog['recipe_rows']:
            recipe = row['recipe_id']
            item = row['item_id']
            target = recipe_items.setdefault(recipe, {})
            if item in target:
                raise ValueError('duplicate recipe item row')
            target[item] = row['quantity']
        for row in catalog['bundles']:
            if row['recipe_id'] not in recipe_items:
                raise ValueError('bundle references unknown recipe')
            result[row['bundle_id']] = {'price': row['price'], 'quantities': recipe_items[row['recipe_id']]}
        if {row['recipe_id'] for row in catalog['bundles']} != set(recipe_items):
            raise ValueError('orphan recipe')
    else:
        raise ValueError('unknown catalog encoding')
    if len(result) != len(catalog['bundles']):
        raise ValueError('duplicate bundle id')
    catalog_order = documents.get('catalog_order')
    if not isinstance(catalog_order, list) or len(set(catalog_order)) != len(catalog_order) or set(catalog_order) != set(result):
        raise ValueError('catalog order must list every bundle exactly once')
    requirement_rows = documents['requirements']
    requirements = {row['item_id']: row['quantity'] for row in requirement_rows}
    if len(requirements) != len(requirement_rows) or any((not isinstance(item, str) or type(quantity) is not int or quantity != 1 for (item, quantity) in requirements.items())):
        raise ValueError('requirements must cover each public item exactly once')
    for row in result.values():
        if not row['quantities'] or any((item not in requirements or type(quantity) is not int or quantity != 1 for (item, quantity) in row['quantities'].items())):
            raise ValueError('bundle has malformed quantities')
        if type(row['price']) is not int or row['price'] <= 0:
            raise ValueError('bundle price must be positive')
    return result

def requirement_items(documents: Mapping[str, Any]) -> list[str]:
    """Return the public required handles in a deterministic evidence-only order."""
    rows = documents.get('requirements')
    if not isinstance(rows, list):
        raise ValueError('requirements must be a row list')
    items = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('item_id'), str) or type(row.get('quantity')) is not int or (row.get('quantity') != 1):
            raise ValueError('malformed requirement row')
        items.append(row['item_id'])
    if len(set(items)) != len(items):
        raise ValueError('duplicate required item')
    return sorted(items)

def basket_value(documents: Mapping[str, Any], tickets: Iterable[str]) -> int:
    bundles = normalized_bundles(documents)
    selected = tuple(tickets)
    if len(set(selected)) != len(selected) or any((ticket not in bundles for ticket in selected)):
        raise ValueError('tickets must be distinct known bundle ids')
    delivered = Counter()
    for ticket in selected:
        delivered.update(bundles[ticket]['quantities'])
    required = Counter({row['item_id']: row['quantity'] for row in documents['requirements']})
    if delivered != required:
        raise ValueError('tickets do not exactly cover the basket')
    return sum((bundles[ticket]['price'] for ticket in selected))
