# Failures: F08, L14, P29

This report summarizes where each expected document was lost in the pipeline and the smallest fix.

## F08 (fixed)
Expected docs: BOE-A-2006-20764
Cited IDs: BOE-A-2006-20764

Drop location:
- none

Notes:
- Query expansion includes amortizacion IRPF variants.
- Reference boost promotes BOE-A-2006-20764 on amortizacion queries.

## L14 (fixed)
Expected docs: BOE-A-1985-17303, BOE-A-2022-4583
Cited IDs: BOE-A-1985-17303, BOE-A-2022-4583 (also cites BOE-A-1996-8930)

Drop location:
- none (post-fix). Both laboral sources are present in final context and citations.

Notes:
- Laboral artist queries force-add 1985/2022 chunks when missing.
- Area filter keeps those docs via allowlist.

## P29 (partial, CELEX missing)
Expected docs: BOE-A-1996-8930, CELEX:32001L0029
Cited IDs: BOE-A-1996-8930

Drop location:
- CELEX:32001L0029: not retrieved (not in index).

Notes:
- PI intent boost ensures LPI is retrieved and cited.
- If CELEX is not indexed, answer should mention missing EU directive in sources (soft uncertainty).
