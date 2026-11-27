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

### An empty domain certifies nothing: `0 = 0` is not a pass

`conserva` is not a flag this instrument sets. It is the conjunction of three named factors, and the
receipt publishes the boolean **and** the factors, so one is recomputed from the other by a reader
who never installs the package:

```
conserva = cubetas_no_negativas ∧ dominio_no_vacio ∧ residuo_cero
```

Hand it an export with a header and no rows and the equation closes *exactly*: `0 = 0 + 0 + 0 + 0 +
0`, residual zero, every bucket zero. A tool that answered `CONSERVADO` here would be signing a
certificate over an empty population — the identity holds because there was nothing to hold. The
factor that fails is `dominio_no_vacio`, the receipt names it on its own line, and the exit code is
`2` (`NO_MEDIDO`), never `0`:

```console
$ ingest-conservation-guard --receipt tests/fixtures/export-vacio.csv \
      --clave telefono:digitos:ultimos10 --crudo telefono --validar activo
ACTA DE MIGRACION  export-vacio.csv
  entrada   export-vacio.csv  filas=0  sha256=a6147dcb722a4b63...
  clave     telefono:digitos:ultimos10  crudo=telefono
  ecuacion  0 = 0 + 0 + 0 + 0 + 0
  perdidas  0
  salida    claves=0  sha256=44136fa355b3678a...
  no conserva  dominio_no_vacio
  estado    NO_MEDIDO  RC=2
  firmado   ingest-conservation-guard 0.5.0
NO_MEDIDO: el dominio declarado esta vacio; no hay unidades que conservar y el acta no certifica nada
```

The same JSON, read with `jq` alone — no Python, no wheel, no network — re-derives the boolean from
the factors and names the one that failed. `ley true` is the receipt obeying its own schema:

```console
$ ingest-conservation-guard --receipt tests/fixtures/export-vacio.csv \
      --clave telefono:digitos:ultimos10 --crudo telefono --json 2>/dev/null \
    | jq -r '"ley \(.conserva == ([.conserva_condiciones[]] | all)) · conserva \(.conserva) · falla: \(.conserva_condiciones | to_entries | map(select(.value | not)) | map(.key) | join(" ")) · rc \(.rc) \(.estado)"'
ley true · conserva false · falla: dominio_no_vacio · rc 2 NO_MEDIDO
```

A producer on the client's side implements the same three names. The verifier in
[`conservation-ledger`](https://github.com/alexisromtz-lab/conservation-ledger) reads a receipt with
this shape and reaches `VACIO`/`2` on its own, without knowing which instrument wrote it — the two
packages agree because both derive the same conjunction, not because either one knows the other's
name.

### Measured on a real export, not on a fixture

The tables above are fixtures, because a certificate has to be cheap to reproduce. This one is
34 195 rows of real public data, and the input digest below is the one the receipt itself prints
([`censo.json`](censo.json) pins it; `tests/test_censo.py` keeps this table and that file in step).

`world-cities.csv` from `datasets/world-cities` (branch `master`, retrieved 2026-11-25),
34 195 rows, sha256 `9edb0db14c312fb27058d6fe9633a6904cc915163cff939db92553125c154d30`:

| projection | raw key | domain | image | by projection | by repeated row | rejects | no key | silent losses | rc |
|---|---|---|---|---|---|---|---|---|---|
| `name:plano:lower` | `name` | 34 195 | 32 171 | **153** | **1 871** | 0 | 0 | 0 | 1 |
| `geonameid` | — | 34 195 | 34 195 | — | — | 0 | 0 | 0 | 0 |

Read the two cause columns separately, because they name different repairs:

- **153 rows** are lost to the projection and would have survived an exact key: `Ābādeh`/`Abadeh`,
  `Santa Bárbara`/`Santa Barbara`, `Belém`/`Belem`, `San José`/`San Jose`. Folding accents is a
  decision the projection made; if the destination considers those different places, the projection
  is wrong and the normaliser is where the loss was introduced.
- **1 871 rows** repeat a raw value an earlier row already carried: `Victoria` names nine distinct
  cities in this file, `Richmond` nine. No projection can separate them, because the export never
  carried what distinguished them. The repair belongs upstream, in the export's key, not here.

`--clave geonameid` conserves all 34 195 rows at RC 0 — an identity key has no kernel to fold, which
is the control proving the engine is not simply always red. `--sin-claves` prints
`COLISION  <omitida> conservado=Ābādeh pisados=Abadeh` and keeps the witnesses. Two consecutive runs
produce byte-identical `entrada.sha256` and `salida.sha256`, so two receipts can be diffed.

Status of this section: **`MEDIDO_EN_EXPORTACION_PUBLICA`**. It is not `MEDIDO_EN_PRODUCCION`: no
client migration has been certified with this yet. The day one is, that export's digest and numbers
replace these, and until then the distinction is stated rather than blurred.

Whoever holds the file can re-derive every cell above — including the output digest — with
`bench/replay_censo.py`. It downloads the export, compares its SHA-256 with the pin **before**
measuring anything, and then recomputes both rows:

```console
$ python bench/replay_censo.py
export verificado: world-cities 1336699 B 9edb0db14c312fb2...
  identico name:plano:lower: domain=34195 image=32171 by_projection=153 by_repeated_row=1871 ...
  identico geonameid: domain=34195 image=34195 by_projection=None by_repeated_row=None ...
REPLAY IDENTICO · 2 filas · instrumento 0.4.2 · estado MEDIDO_EN_EXPORTACION_PUBLICA
```

Four verdicts, and the ladder refuses to let a milder one hide a worse one:

| code | meaning | why it is not the other one |
|---|---|---|
| `0` | every cell reproduced | the pin is still true |
| `1` | a cell did not reproduce | the code moved or the row is wrong: a proven defect |
| `2` | the export could not be obtained | `NO_MEDIDO`, and it never masks a `1` |
| `4` | the bytes are not the pinned export | nothing measured from them would mean anything |

The `replay-censo` job in `.github/workflows/ci.yml` runs it on every push, so the table above is
checked on a machine that has never seen mine. `tests/test_replay_censo.py` exercises the three
offline verdicts against a tampered copy of the fixture.

### Chaining two acts: the seam is a measurement

An act digests the bytes it read and — with `--export` — the bytes it wrote. Without that second
pair nothing downstream can ever cite the output: the next act's `entrada.sha256` is the digest of a
*file*, and an in-memory map has none.

```console
$ python -m ingest_conservation_guard --receipt migracion.csv \
      --clave telefono:digitos:ultimos10 --crudo telefono --export paso1.csv --json
  "salida": {"archivo": "paso1.csv", "claves": 3,
             "sha256": "8255a43e...", "sha256_archivo": "ede784ce..."}

$ python -m ingest_conservation_guard --receipt paso1.csv --clave clave --crudo clave --json
  "entrada": {"archivo": "paso1.csv", "filas": 3, "sha256": "ede784ce..."}
  "ecuacion": {"dominio": 3, "imagen": 3, ...}
```

The export is written sorted by key, so two runs over the same rows produce the same file, and the
digest is read back from the file that landed on disk rather than from the text that was meant to
be written. `--export` together with `--sin-claves` is refused: the artifact contains the keys, and
an act cannot publish and withhold them at once.

Two independent measurements of the same seam, and they answer different questions:

| seam | measurement | what it proves | what it cannot see |
|---|---|---|---|
| count | `imagen(1) == dominio(2)` | the second act received as many rows as the first kept | identity: rewrite one witness and the count still says 3 |
| bytes | `sha256_archivo(1) == entrada.sha256(2)` | the second act read the artifact the first wrote | nothing about the rows themselves |

Measured on the six-row fixture: `6 = 3 + 3` — three rows kept, three declared as collisions, zero
silently lost — with **both** seams sealed. Then rewrite one witness inside `paso1.csv` and re-audit:
the counts still say `3 -> 3`, and the digests disagree. That is the exact state a count-only
checker calls conserved.

`conservation-ledger` composes such receipts with `chain`, checks both measurements per seam and
computes the composite equation by telescoping — `dominio(1) = imagen(n) + sum(restos)` — so a chain
of conserving acts is judged as one pipeline and never as a list of green lights.

### Verifying a receipt without our code

A certificate only its issuer can check is a claim, not a certificate. Every number the `acta`
publishes is confirmable with `shasum`, `wc -l` and a sum — no install, no trust in this package:

| what | command | measured |
|---|---|---|
| the input is the one certified | `shasum -a 256 tests/fixtures/migracion.csv` | `d706d9297093104b…` = `entrada.sha256` |
| the output is the certified one | `shasum -a 256 paso1.csv` | `ede784ce0813c547…` = `salida.sha256_archivo` |
| the output is the whole image | `wc -l < paso1.csv` | `4` = 3 claves + cabecera |
| the act closes | the six terms of `ecuacion` | `6 = 3 + 2 + 1 + 0 + 0` |

```console
$ shasum -a 256 tests/fixtures/migracion.csv paso1.csv
d706d9297093104b22c20301e2e74f92ff83f2c5352c6ea6e4326c7108935581  tests/fixtures/migracion.csv
ede784ce0813c547178cf900cf1e3e9fa5b963f38b83c03ffb0803d03105b042  paso1.csv
$ wc -l < paso1.csv
4
```

What the auditor gets for free: the file in their hands is byte-for-byte the one that was certified,
and it holds exactly the rows the receipt says it holds. What `shasum` does **not** prove is that
`dominio` was counted over an undrained population — bytes vouch for identity, not for the census.
For that, `conservation-ledger` composes several receipts and closes the seam between them.

### Why `--export` is not optional

A receipt describes two populations: what it **declares** (digests, counts, identities) and the
**file** it wrote. Without `--export` the second one does not exist
(`test_sin_export_la_salida_no_nombra_ningun_archivo`), and no downstream verifier can invent it.
The consequence is measured, not argued — in `conservation-ledger` v0.2.3 the same chain
gets exit `0` from the receipt-only composer and exit `2` from `verify.sh`, which prints
`COBERTURA nivel2=1/2 actos` because it must open every artifact to certify one
(`test_el_veredicto_no_colapsa_dos_poblaciones`). Both programs are right; only one of them can see
the file, and only the client decides which answer they need. If a migration has to be auditable by
someone who does not trust you, export: the certificate you hand over is the one whose rows they can
count themselves.

### Adopting it without PyPI

`.pre-commit-hooks.yaml` is in the repository root. The hook audits **one declared input**, so it
does not take staged filenames — edit `args` to point at your export and declare your projection:

```yaml
repos:
  - repo: https://github.com/alexisromtz-lab/ingest-conservation-guard
    rev: v0.5.0
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

`0.4.1` retires `produccion = NO_MEDIDO` where it can be retired. The receipt above has now run on
a real 34 195-row public export, `censo.json` pins that file by SHA-256 with the exact commands, and
`tests/test_censo.py` recomputes every cell — including the output digest — whenever the export is
on disk. It is `MEDIDO_EN_EXPORTACION_PUBLICA`, not `MEDIDO_EN_PRODUCCION`: no client migration has
been certified yet, and the file says so.

`0.4.2` makes the receipt name its author. Until now an `acta` document said what it measured, by
which projection, over which bytes — and not which binary wrote it, so a certificate found in a
drawer could not be traced to a version and a receipt that had aged could not be told from one that
had been altered. Both the certificate and the per-case documents now carry `instrument` and
`instrument_version`, stamped by the package itself. The census was re-run over the pinned 34 195-row
export with `0.4.2` before its `instrument_version` was moved: every cell identical, which is the
only thing that makes the new number a measurement instead of a wish.

`0.4.3` makes an act chainable. Until now `salida` digested the image — a sorted in-memory key map
— so no later act could cite it: its own `entrada.sha256` is the digest of a *file*, and those are
two different subjects. `--export` writes the image as CSV and publishes `salida.archivo` +
`salida.sha256_archivo`, read back from disk. An act that produced no artifact publishes neither
key: `NO_MEDIDO`, never a zero. The census was re-run over the pinned 34 195-row export with `0.4.3`
before `instrument_version` moved, and every cell reproduced.

`0.4.4` publishes who can check the certificate: `### Verifying a receipt without our code` names
the three commands — two `shasum` calls and a `wc -l` — that confirm both digests and the row count
on a machine with none of our packages, and `tests/test_verificar_sin_codigo.py` measures all three
cells with the system tools instead of with the engine. No behaviour changed; the census was re-run
over the pinned export with `0.4.4` before `instrument_version` moved, and both rows reproduced to
the digest of their output.

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

## Citar

La versión 0.5.0 está depositada en Zenodo: `10.5281/zenodo.24575087`. `CITATION.cff`
lleva el mismo identificador, y `tests/test_cita.py` falla si las dos superficies
discrepan.

## License

MIT. See [LICENSE](LICENSE).
