# Relay evidence environment

You must build one connected directed path from `<source>` to `<destination>`.
The network contains `<decision_layers>` relay layers with `<layer_width>`
relay nodes per layer. These `d` relay layers induce exactly `d+1` ordered arc
stages: source to relay layer 0, each consecutive relay-layer transition, and
the final relay layer to destination. Their ordered stage handles are
`<stage_handles>`, and the component handle is `<component_handle>`.

A legal logical path selects exactly one manifest row from every ordered stage.
The selected row in the first stage must leave `<source>`, each selected row's
head must equal the next stage's selected-row tail, and the last selected row
must enter `<destination>`. The submitted physical edge list is obtained by
concatenating each selected row's `physical_edge_ids` in stage order, preserving
the order inside every row. Merely choosing one cheap row per stage without
these connectivity equalities is illegal.

In addition to minimizing price, your complete path must have checksum residue `<required_residue>` modulo `<residue_modulus>`. Residues start at zero and each
logical arc adds its manifest `residue_delta` modulo that modulus.

Manifest tools return `compact_manifest_v2`. Each response explicitly repeats
the residue modulus, which must agree with `<residue_modulus>`. Each item in
`stages` contains a
stage handle, a `nodes` directory, and `rows`. Every row is

```text
[physical_edge_ids, tail_node_slot, head_node_slot, quantity_residue_code]
```

where the node slots index that stage's `nodes`. `physical_edge_ids` contains
either one id or two serial-piece ids already in traversal order. Preserve that
order when constructing the final submitted path.

Decode the final scalar using

```text
tariff_quantity, residue_delta = divmod(quantity_residue_code, residue_modulus).
```

The quotient is strictly positive and the remainder is in
`0..residue_modulus-1`.

Exception tools return `compact_exceptions_v1`. For the same stage,
`class_slots[i]` describes manifest `rows[i]`. The tariff-card tool returns
`compact_tariff_v1`, where `rate_by_class_slot[j]` is the rate for class slot
`j`. Thus a logical manifest row costs

```text
tariff_quantity * rate_by_class_slot[class_slots[i]].
```

You must combine all three sources, track residue as part of the planning
state, and compare only complete connected paths having the required residue.

Your total query budget is `<cost_budget>` units. Query costs are
`<tool_costs>`. Discovery queries are charged, including an exact repetition. A
query that would exceed the remaining budget does not execute. Candidate
evaluation uses the same budget and is strictly one-shot: the first legal,
illegal, or malformed candidate consumes it. A repeat is still subject to the
public query price and budget, and can never return another scalar result.
Final submission is free, binding, and terminal.

Stage tools read one source at one stage. Window tools return the identical
per-stage views for two or three consecutive stages. The tariff-card tool
returns rates but no edge identities. `evaluate_path` only checks and prices
the exact candidate you provide; it does not submit, complete, recommend, or
modify it.
