"""Runtime-only helpers for case_03_basket_assembly."""
from __future__ import annotations
from typing import Any, Mapping
from benchmark.cores.case_03_basket_assembly import runtime_data

def _bundle_structure_observation(documents: Mapping[str, Any], bundle: str) -> dict[str, Any]:
    catalog = documents['catalog']
    row = next((row for row in catalog['bundles'] if row['bundle_id'] == bundle))
    if catalog['encoding'] == 'direct':
        return {'encoding': 'direct', 'bundle_id': row['bundle_id'], 'quantities': dict(row['quantities'])}
    recipe_rows = [item for item in catalog['recipe_rows'] if item['recipe_id'] == row['recipe_id']]
    return {'encoding': 'mediated', 'bundle': {'bundle_id': row['bundle_id'], 'recipe_id': row['recipe_id']}, 'recipe_rows': recipe_rows}

def _bundle_price_observation(documents: Mapping[str, Any], bundle: str) -> dict[str, Any]:
    return {'bundle_id': bundle, 'price': runtime_data.normalized_bundles(documents)[bundle]['price']}
