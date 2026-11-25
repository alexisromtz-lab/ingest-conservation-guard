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

The witness is the point: not "there were collisions", but **who survived and who was
overwritten**, by row identifier.

To audit an export you already have, without writing a line of code:

```console
$ python bench/auditar_csv.py export.csv --columna titulo --clave slug
$ python bench/auditar_csv.py export.csv --columna telefono --clave digitos10
```

The script prints the receipt as JSON and exits with its code, so it can gate a migration in a
shell pipeline.

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

### Was it the projection, or was the row already repeated?

The lost mass has two causes and they get repaired on **opposite sides** of the pipeline: a
projection that folds two different raw values into one key is a code change; a row that already
appeared in the export is an input change. Passing `crudo_fn` — the key *before* the projection —
splits the bucket:

```python
recibo = auditar_mapeo(filas, clave_fn=slug_titulo, crudo_fn=lambda f: f["titulo"])
recibo.colisiones_por_proyeccion   # 0   the projection lost nothing
recibo.colisiones_por_repetido     # 29  the export carried 29 duplicate rows
```

Without `crudo_fn` both fields are `None`, never `0`: the split was not measured, and a bucket
nobody measured is not an empty bucket. The mass still closes — `proyeccion + repetido ==
masa_perdida` — because the distinction is a classification, not a fourth check.

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

Not on invented data. Four real exports, read-only, no values reproduced:

| dataset | key | domain | image | lost | by projection | by repeated row | rc |
|---|---|---|---|---|---|---|---|
| product photo manifest (86 rows) | `slug(titulo)` | 86 | 57 | 29 | **0** | **29** | 1 |
| same manifest | `producto_id` | 86 | 57 | 29 | **0** | **29** | 1 |
| business listings (13 rows) | `digitos(telefono)[-10:]` | 13 | 13 | 0 | 0 | 0 | **0** |
| business listings (13 rows) | `zona` | 13 | 1 | 12 | 0 | 12 | 1 |

The first two rows are the honest surprise, and the useful one: the receipt's first job was to
refute **my choice of key**, not to find a defect in anyone's code. 57 distinct titles map to 57
distinct slugs — the projection is injective on this data. The manifest has one row per *photo*,
not per product, so `titulo` and `producto_id` are the wrong row identity and the 29 lost rows are
literal duplicates. `colisiones_por_proyeccion == 0` says that in one number.

The last row is the counter-example, and it refuted a claim I had written before measuring it: I
expected `zona` to be a *label collapsing many values into one key*, and the receipt says
otherwise — `proyeccion == 0`, `repetido == 12`. The column holds **one** distinct value across 13
rows, so there was nothing to project: using it as a key would collapse the whole export into a
single record, and every lost row is a repeat of the same string. A column with one value is not a
key, and the split names the reason instead of leaving it to the reader.

| what | value |
|---|---|
| tests | the count lives in CI output, never in this table. A hand-written `N passed` is stale the next commit, and nothing was reading it: `tests/test_readme.py` now fails if this file ever pins one again |
| executable cases | 3 (patient import, catalogue sync by two projections, dropped-row write) |
| collisions detected in the patient case | 2 of 8 rows, witnesses `A-1/A-2` and `A-4/A-5` |
| production exports with client data audited | **NO_MEDIDO** |

The last row is the honest one. These four audits are catalogue and directory exports; a client
migration (patients, customers, appointments) has still not been run through the engine, and the
number of losses it would find in *your* data is a measurement nobody has made yet.

## Migrations: the certificate (`--receipt`)

A conservation audit answers "did anything disappear". A migration needs one more thing: a document
somebody else can check without installing this package. `--receipt` reads a real CSV or JSON
export, applies the projection you actually write, and prints the accounting identity with both ends
digested:

```
$ ingest-conservation-guard --receipt migracion.csv \
      --clave telefono:digitos:ultimos10 --crudo telefono --validar activo
ACTA DE MIGRACION  migracion.csv
  entrada   migracion.csv  filas=6  sha256=d706d9297093104b...
  clave     telefono:digitos:ultimos10  crudo=telefono
  ecuacion  6 = 3 + 2 + 0 + 1 + 0
  perdidas  0
  salida    claves=3  sha256=8255a43e1378521d...
  estado    COLISION_SILENCIOSA  RC=1
  COLISION  5588881111 conservado=A-3 pisados=A-4
  COLISION  7771234567 conservado=A-1 pisados=A-2
```

`perdidas_silenciosas` is the **residual** of that equation, computed and never asserted: a zero is
the result of the arithmetic, not a claim in a template. `--sin-claves` withholds the values of the
colliding keys (witnesses stay) when a key is personal data.

The same six-row fixture, audited with two different declarations of "the key *before* the
projection". Every cell below is recomputed by `tests/test_readme.py`:

| projection | raw key | domain | image | by projection | by repeated row | rejects | silent losses | rc |
|---|---|---|---|---|---|---|---|---|
| `telefono:digitos:ultimos10` | `telefono` | 6 | 3 | 2 | 0 | 1 | 0 | 1 |
| `telefono:digitos:ultimos10` | `nombre:plano:lower` | 6 | 3 | 0 | 2 | 1 | 0 | 1 |
| `id` | `id` | 6 | 6 | 0 | 0 | 0 | 0 | 0 |

The first two rows hold the entire argument for splitting the lost mass in two: **same rows, same
loss, opposite repairs**. Declared against the raw phone, the two spellings of `7771234567` are one
number written twice and the fix belongs in the projection. Declared against the normalised name,
they are the same raw value arriving twice and the fix belongs in the export. A certificate that
reported `2 lost` without the split would be correct and useless.

Normalisers are declarative and closed: `identidad`, `strip`, `lower`, `upper`, `plano` (accents
off), `slug`, `digitos`, `ultimos10`. A misspelt transform is a hard error, because silently
auditing a different projection than the one the certificate names is the very failure this package
exists to catch, one level up.

### Adopting it without PyPI

`.pre-commit-hooks.yaml` is in the repository root. The hook audits **one declared input**, so it
does not take staged filenames — edit `args` to point at your export and declare your projection:

```yaml
repos:
  - repo: https://github.com/alexisromtz-lab/ingest-conservation-guard
    rev: v0.4.0
    hooks:
      - id: ingest-conservation-guard-receipt
        args: ["--receipt", "migraciones/clientes.csv", "--clave", "telefono:digitos:ultimos10",
               "--crudo", "telefono", "--json"]
```

Exit `1` stops the commit because records merged in silence; exit `4` stops it because the identity
does not close.

## Version notes

`0.4.0` adds `--receipt` (the migration certificate above, with SHA-256 of both ends and the split
of lost mass into projection and repeated row), `.pre-commit-hooks.yaml`, and `tests/test_readme.py`,
which recomputes the migration table and the per-case exit codes and fails when this file disagrees
with the engine. The engine itself is unchanged: same buckets, same three codes, same supremum.

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
