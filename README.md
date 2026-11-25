# ingest-conservation-guard

Receipts of bucket conservation for data ingestion, migrations and catalogue sync.

`pydantic` and JSON Schema tell you whether one row is well formed. None of them
tells you whether the **set** survived the transform. That is where data is lost
without anyone noticing:

```python
pacientes = {"ana-ruiz|7775550199": a4, "ana-ruiz|7775550199": a5}
len(pacientes)   # 1
```

Two distinct patients. One key. No exception, no warning, a plausible count. The
row that loses is whichever one the loop wrote first, and the record of it having
existed is a line in a CSV that was already deleted.

This package turns that silent subtraction into an arithmetic identity you can
assert on:

```
dominio_declarado == imagen + rechazos + sin_clave + colisiones
toda cubeta >= 0
```

## Install

```console
pip install ingest-conservation-guard      # zero dependencies, Python >= 3.11
ingest-conservation-guard pacientes        # or: python -m ingest_conservation_guard
```

## Use

```python
from ingest_conservation_guard import auditar_mapeo

recibo = auditar_mapeo(filas, clave_fn, validar_fn=es_valido, mapeo=lo_que_escribi)
if recibo.rc != 0:
    raise SystemExit(recibo.estado)   # no se escribe ni una fila
```

```console
$ python -m ingest_conservation_guard pacientes
pacientes    COLISION_SILENCIOSA    RC=1  dominio=8 = imagen=4 + rechazos=2 + sin_clave=0 + colisiones=2
    COLISION clave=ana-ruiz|7775550199 conservado=A-4 pisados=A-5
    COLISION clave=jose-ramirez|7771234567 conservado=A-1 pisados=A-2
```

The witness is the point: not "there were collisions", but **who survived and who
was overwritten**, by row identifier.

### Exit codes

| RC | status | meaning |
|---|---|---|
| `0` | `CONSERVADO` | `dominio == suma`, no collisions: the transform preserved the population |
| `1` | `COLISION_SILENCIOSA` | two or more records share a key; the receipt names the merged ones |
| `2` | `NO_MEDIDO` | nothing was compared (bad invocation, empty input): never a pass |
| `4` | `RUPTURA_CONSERVACION` | a bucket is negative, the identity does not close, or the mapping you wrote is not the image of the projection |

There is no code that means "probably fine". With several targets the run's code is the
**supremum** of the individual codes under `4 > 1 > 2 > 0` (`combinar_rc`), never `max`:
`max(1, 2) == 2`, so an integer maximum lets a receipt that measured nothing cover a receipt that
proved a silent merge. Ordering the codes by what they mean, not by their value, is the point.

### Auditing a real write

If you pass `mapeo=` (the dict or index your code actually populated), the receipt
audits **the write**, not the intention. A mapping missing a key the projection
produced, or holding a key the projection never produced, is `RC 4` — the shape of
the failure where an import reports 1 420 rows and stores 1 412.

### Transversality of a whitelist

A guard of the form `if clave in PERMITIDOS` cannot suppress a collision: it
filters on the *image*, and collisions live in the *kernel*. A whitelist suppresses
the risk only when it is an exact transversal —

```
para toda y en pi(W):  |W ∩ pi^-1(y)| == 1
```

```python
from ingest_conservation_guard import verificar_transversal

verificar_transversal(permitidos, clave_fn)
# {'transversal': False, 'permitidos': 5, 'imagenes': 3, 'nucleo': 2, 'colisiones': [...]}
```

## Why every bucket is counted twice

A bucket defined by subtraction closes in the integers even when the counts are
incompatible:

```
68 + 0 + (-1) = 67        # la aritmetica cuadra, el censo miente
```

That exact arithmetic came out of a real census of a Markdown corpus, where a
heading pattern and a regex disagreed by one and the total still added up. Each
bucket here is therefore counted by its own pass, and `cubetas >= 0` is checked on
its own: subtraction never refutes its own terms, only the positivity bound does.

## Determinism

`Recibo.as_dict()` sorts keys and orders collisions by key, so two runs over the
same input produce byte-identical JSON. Receipts are meant to be attached to a
delivery, stored, and compared later — a receipt that changes between runs proves
nothing.

## Measured

| what | value |
|---|---|
| tests | `19 passed` (`python -m pytest -q`) |
| executable cases | 3 (patient import, catalogue sync by two projections, dropped-row write) |
| collisions detected in the patient case | 2 of 8 rows, witnesses `A-1/A-2` and `A-4/A-5` |
| production exports audited | **NO_MEDIDO** — this package has not yet been run over a client's real export |

The last row is the honest one. The engine is deterministic and the law is checked
by construction; the number of losses it finds in *your* data is a measurement
nobody has made yet.

## Limits

- It detects collisions inside **one** projection. Two different key functions that
  both lose rows need two audits.
- It does not deduplicate, merge or repair. It produces the receipt; the decision
  stays with you.
- `mapeo=` is compared by **key set**, not by values: it proves which keys were
  written, not that the stored payload is correct.
- Witnesses name records inside the audited list only; rows dropped by the source
  query before the audit are outside its universe and are reported as such
  (`NO_MEDIDO`), never as zero.

## License

MIT. See [LICENSE](LICENSE).
