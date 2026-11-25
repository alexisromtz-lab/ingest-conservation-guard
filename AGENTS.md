# AGENTS.md — ingest-conservation-guard

Rules for anyone (human or agent) changing this repository. Two of them are
non-negotiable because the package exists for them.

## 1. A bucket is counted, never derived

Every bucket (`imagen`, `rechazos`, `sin_clave`, `colisiones`) is produced by its own
pass over the input. Do not compute a bucket as `dominio - suma(otros)`: that closes
in the integers even when the counts are incompatible, which is the failure the
package is supposed to catch (`68 + 0 + (-1) = 67`).

`cubetas >= 0` is checked separately and is not optional.

## 2. A receipt that cannot fail is not a receipt

If a change makes `RC 4` unreachable, the change is wrong. The three exit codes must
each have a test that reaches them: `0` conserved, `1` merged, `4` broken. A guard
that only ever returns success is indistinguishable from no guard.

## Invariants

- **Zero dependencies.** `pip install` must stay instantaneous and offline-safe. The
  package is a gate; a gate that drags a dependency tree into a CI job gets removed
  from the CI job.
- **Deterministic output.** `as_dict()` sorts keys; collisions are ordered by key.
  Never introduce iteration over a set into the receipt.
- **Witnesses are identifiers, not positions** when the caller supplies
  `testigo_fn`; the default (position `#i`) exists so the library never needs
  `list.index`, which names the *first equal* record instead of the overwritten one.
- **`NO_MEDIDO` is not zero.** Anything not measured (a source query that dropped
  rows before the audit, a payload not compared) is published as unmeasured.

## Checks

```console
python -m pytest -q -p no:cacheprovider
PYTHONPATH=src python -m ingest_conservation_guard               # demo: RC 4, broken on purpose
PYTHONPATH=src python -m ingest_conservation_guard sku           # RC 1
PYTHONPATH=src python -m ingest_conservation_guard sku-completa  # RC 0
```

The demo case `ruptura` is broken on purpose so the failure path is exercised every
time someone runs the CLI; its `RC 4` is the correct answer, not a defect.
