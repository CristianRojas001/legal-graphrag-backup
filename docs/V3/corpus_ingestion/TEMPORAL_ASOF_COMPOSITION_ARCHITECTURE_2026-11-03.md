# ADR: Temporal as-of composition of BOE legal sources (IRPF / LGSS unblock)

**Status:** Proposed. Requires owner decisions D1–D7 (§12) before implementation.
**Date:** 2026-11-03
**Applies to:** `CristianRojas001/legalgraphrag.v2.0`. The ingestion and release side is on branch `impl/corpus-ingestion`. The agent consumption side is the serving consultation branch; see §2 and §12 D5.
**Authority:** This document is additive. It does not amend `docs/V3/corpus_ingestion/OPERATIONS.md`, the coverage matrix, any reviewed manifest, or the frozen rev3 plan. Where it proposes contract changes, OPERATIONS.md must be updated by the implementing task, not by this ADR.
**Not done here:** no application code, migrations, ingestion, production access or paid calls.

---

## 0. Evidence base and verification of repository state

| Item | Verified value |
| --- | --- |
| Reported checkpoint `51f3045df69ce0d143574065234846410363ef47` | Tip of remote branch `origin/impl/corpus-ingestion` (commit "Inventory future-effective corpus versions", 2026-11-03 01:23 +0100). |
| Local checkouts at investigation time | `legalgraphrag.v2.0` was on `impl/jev-triage-20261101` (`0a90986f`), a consultation-agent branch that does **not** contain the checkpoint. The checkpoint was fetched and inspected in a separate detached worktree; the existing checkout was not modified. |
| History relationship | `impl/corpus-ingestion` shares **no merge base** with `impl/consultation-agent-v1` (`967fe0b6`) or `impl/jev-triage-20261101`. They are independent histories. |
| Shared agent corpus layer | `services/v3/agent/corpus/provision_store.py`, `corpus/refs.py`, `corpus/search_backend.py` and `SourceRefV1` are byte-identical across all three branches. `read.py`, `contracts.py`, `validator.py`, `turn_manager.py` and `views_v3.py` differ. |
| Release builder location | `services/v3/agent_release.py` and `agent_records.py` exist **only** on `impl/corpus-ingestion`. |
| Ingestion telemetry location | `services/v3/ingestion/telemetry.py` (`OperationRecorder`, `v3.ingestion.operation`) exists **only** on `impl/jev-triage-20261101`. `observability/events.py::emit_event` exists on both. |
| Official BOE reachability from this environment | `www.boe.es` refused by the egress proxy. No BOE artifact was fetched for this ADR. All legal-source facts come from OPERATIONS.md and the coverage matrix at the checkpoint. |

Documents and code read (at the checkpoint): OPERATIONS.md (all sections), `INGESTION_COVERAGE_MATRIX_2026-11-01.csv` (IRPF/LGSS rows), `reviews/*.json`, `models.py` (V3 models), migrations `0011`/`0012`, `ingestion/source_integrity.py`, `ingestion/source_ingestor.py`, `ingestion/boe_context.py`, `ingestion/target.py`, `v3_register_source_review`, `v3_validate_ingestion`, `scripts/verify_boe_xml_coverage.py`, `agent_release.py`, `agent_records.py`, agent `corpus/*`, `tools/{search,read,related,outline,corpus_scope,registry}.py`, `contracts.py`, `validator.py` (V2/V3 and finalize), `render.py`, `turn_manager.py`, prompts, and release/integrity/version-history tests.

---

## 1. Decision summary

Adopt a **block-level as-of composition**, which is an explicit, additive, second kind of reviewed source:

1. Every canonical unit stays bound byte-for-byte to exactly one block of one **official BOE consolidated HTML response**. That response is fetched by the guarded pipeline and hash-matched to the reviewed manifest, exactly as today. A composition simply allows different blocks to come from different official responses. The blocks are the current page plus historical `p=` selections. No text is synthesized, spliced inside a block, or normalized into a new HTML document.
2. Each substitution is mechanically justified by BOE's own version metadata: the block's version-selector label and the consolidated XML version (`id_norma`, `fecha_publicacion`, `fecha_vigencia`). It is also linked to the amending instrument's official Diario publication, which is retained as a hashed artifact.
3. The reconstruction is stored as a **new snapshot kind** (`as_of_composition`) with its legal date, its composition manifest and the hashes of all supporting artifacts. Artifacts are held once in a new immutable artifact table. Existing snapshots, manifests, hashes and unit identities are untouched.
4. Legal judgments are recorded as named human-review decisions with closed outcome codes. Examples are implied displacement (LGSS a248) and unsatisfied or unknown commencement conditions (LGSS a72). Software verifies that the records exist and are well formed; it never decides them. Unresolved material is released only as explicitly uncertain, or not at all (D2).
5. The release payload carries per-unit wording windows and a closed `wording_basis`. The agent's existing `build_source_ref` → `valid_at_legal_date` → validator V3 path then distinguishes applicable, future and uncertain wording. Pending (future-effective) wording is readable as temporal evidence but cannot be cited as applicable.
6. The release gate gains one corpus-wide mechanical rule: **no unit may present displayed wording whose BOE-declared effect or publication date is after the release legal date.** This applies to all 50 documents, not only the two blocked laws.

This is the minimum change that unblocks IRPF/LGSS without weakening any existing check. It generalizes to any BOE consolidated law whose amendments have different publication and effect dates.

---

## 2. Root cause confirmed from current code

| # | Finding | Code evidence |
| --- | --- | --- |
| R1 | A reviewed source is exactly **one** HTML artifact. The manifest has one `sha256`, and validation fails unless the fetched HTML hashes to it. | `source_integrity.py:10` `validate_review_manifest`; `:41` hash equality. |
| R2 | Canonical unit text must equal that artifact's block text (`context_text(..., exclude_editorial=True)`), and the citable block set must equal the artifact's block set. A unit can therefore only carry the wording that this single BOE response displays. | `source_integrity.py:144`, `:185`. |
| R3 | A BOE consolidated HTML response is a whole-law view keyed by **publication date of the update** (`p=YYYYMMDD`; the per-block selector radio `value` is the version's publication date). It is not an as-of-effect view. The current page displays not-yet-effective wording. The parser already recognizes BOE's own `[No vigente aún]` / `en vigor a partir del` labels but only stores them as metadata. | `boe_context.py:353–386` (`classify_form` label grammar incl. `[No vigente aún]`); `source_forms()` stores selector HTML in unit metadata. OPERATIONS "IRPF whole-law version selector" and "Official version semantics" sections (BOE FAQ/ELI: `version_date` = publication date). |
| R4 | Neither the current page (it contains future IRPF a24/a85 and LGSS a144/a169/a171–a173/a309 wording) nor any single older selection is the 2026-11-02 law. The 2026-10-03 selections omit later in-force changes: IRPF 7.ñ, and LGSS a61/a190–a192. | OPERATIONS 2026-11-03 sections; coverage matrix rows. |
| R5 | A snapshot stores one `source_html`. The release gate selects the snapshot whose `source_html` hashes to `manifest.sha256` and requires exact equality of current document/unit rows with that snapshot. There is no field or operation for a multi-source composition. `wording_valid_from/to` exist but are never populated. | `models.py:540–557`; `agent_release.py:206–241` (`snapshot = next(...)` at `:223`, equality at `:240`); `tests/v3/test_v3_ingestion_version_history.py` asserts the wording dates stay `None`. |
| R6 | One wording per provision per release. `V3LegalUnit.unit_id` is globally unique, the sidecar requires exactly one record per unit, and the agent store is keyed by `unit_id`. The validator's read set is also keyed by `unit_id`. | `models.py:564`; `agent_release.py::_validate_content`; `provision_store.py::IndexRecordsProvisionStore`; `validator.py:707–731`. |
| R7 | **Temporal information never reaches the Researcher.** `_canonical_payload` rewrites `current`/`amended` to `unknown`. `build_source_ref` therefore yields `valid_at_legal_date="unknown"` for every released provision. Validator V3 flags every citation `NOT_VALID_AT_LEGAL_DATE` and annotates "verifique la versión aplicable". The only date available is the law's entry-into-force date, copied into every unit, which is not a wording date. Editorial provenance, version selectors, `source_context` and tables live in `metadata` and are not part of any tool output contract (`SourceRefV1`, `ProvisionTextV1`, `SearchHitV1`). | `agent_release.py:248,259`; `refs.py:20–24`; `validator.py:733–743`, `:1781–1792`; `source_ingestor.py:981,1042`; `tests/v3/test_v3_agent_release_database.py:108` asserts `'unknown'`. |
| R8 | The XML comparator selects a version by date only. It is a diagnostic, not a legal selection: it chose a repealed RDL 7/2023 version for LGSS a274–a287, and a different 2026-10-23 version for IRPF a7. | `scripts/verify_boe_xml_coverage.py:33` `applicable_version`; OPERATIONS LGSS/IRPF follow-ups. |
| R9 | **No corpus-wide guard against future-effective wording.** The release gate never inspects the displayed version's effect date, so any of the 48 approved documents could already present not-yet-effective wording. This is unmeasured. | Absence of any selector-date check in `source_integrity.py` and `agent_release.py`. |

**Root cause in one sentence:** the source contract equates "reviewed legal text" with "one official HTML response", while BOE publishes per-block versions keyed by publication date. As a result, the applicable as-of text of a law with deferred amendments is not available in any single response. The release and agent layers also have no representation of wording-level validity, so even a correct text could not be presented as applicable.

---

## 3. Supported today / proposed / unresolved

| Area | Already supported by code or official evidence | Proposed here | Unresolved, requiring legal review |
| --- | --- | --- | --- |
| Source identity and hash | Single artifact, exact SHA-256, `id_local` identity, structural completeness, tables, editorial separation (`source_integrity.py`). | The same checks applied per block against that block's own artifact. Multiple artifacts held in an immutable store. | — |
| Version metadata | BOE selector labels parsed and stored; XML versions with `id_norma`/dates; Diario captures referenced in OPERATIONS. | Parse selector labels into structured versions; compare XML by **named** version; Diario artifacts hashed and required for every substitution. | Whether BOE metadata reflects all legal effects (BOE FAQ: express amendments only). |
| Snapshot immutability | Trigger `legal_v3_snapshot_no_update_delete`; content digest. | New nullable columns; new `as_of_composition` kind; artifact table with the same trigger pattern. | — |
| Release gate | Exact manifest, snapshot and row equality; rejects missing manifests. | Composition branch, future-wording rule, legal date and wording window in the release manifest. | — |
| Agent temporal semantics | `legal_date` with its basis; `valid_at_legal_date`; V3 annotations; `VERSION_UNCERTAIN` gap code. | Wording windows and `wording_basis` in the payload; temporal evidence in `read_provision`. | — |
| IRPF | 7.ñ / 7.x wording verified against Diario; a24/a85 historical wording matched (p=20261003); future a85 table identified. | Composition: base page plus a24/a85 from p=20261003, with the 2027 wording as pending evidence. | Effect of the RDL 26/2026 derogation; whole-law attestation of deferred effects. |
| LGSS | Deferred blocks matched in p=20241221 / p=20220727; a274–a287 and a329–a337 compared; dtdecima explained. | Composition: base page plus 6 substituted blocks. | a72 commencement condition (open); a248 implied displacement (interpretation); RDL 7/2023 derogation effect; whole-law attestation. |

---

## 4. Options considered

| Option | Description | Verdict |
| --- | --- | --- |
| A. Wait for or choose one BOE selection | Keep the single-artifact contract and pick the "best" `p=` version. | **Rejected.** Shown impossible for both laws (R4). It would also recur for every law with deferred amendments. |
| B. Synthesize a spliced HTML and hash it | Build a new HTML from several captures and treat it as the artifact. | **Rejected.** It presents a fabricated document as an official artifact, and its hash proves nothing about origin. |
| C. Relax conservation or normalize hashes | Allow near-matches, nonce stripping, or exclusion of future blocks. | **Rejected** by the constraints. It weakens existing guarantees. |
| D. Canonical text from consolidated XML | Switch the source of truth to BOE XML block versions. | **Rejected for now.** It needs a new parser and new table/header semantics, and it discards the HTML gate. XML is kept as a mandatory cross-check. |
| E. Full bitemporal unit model | Many versions per provision as `V3LegalUnit` rows with validity intervals. | **Rejected for now.** It breaks the global `unit_id` uniqueness, chunk/graph foreign keys, one-record-per-unit releases, the agent store and validator keys (R6). A large migration with no need for the 2026-11-02 cutoff. Possible future evolution. |
| F. Exclude IRPF/LGSS from the release | Ship the release without the two laws. | **Not a solution.** The gate requires the whole corpus, and these are P1 laws. Possible only as an owner-approved interim policy (D1). |
| **G. Block-level as-of composition (recommended)** | Each unit is bound to one block of one official response. Substitution is justified by BOE metadata plus Diario evidence. Stored as a distinct snapshot kind with explicit legal review. | **Recommended.** Additive. Reuses every existing check per block. Keeps citation identity and makes no claim of being an official publication. |

A paragraph-level splice inside a block is **out of scope** for v1. It is needed only when no official block version equals the as-of wording, for example one BOE version containing paragraphs with different effect dates. v1 fails closed with code `NO_OFFICIAL_BLOCK_VERSION`, and such cases go to human review (§5.3.6). Current evidence does not show this case for IRPF or LGSS at 2026-11-02.

---

## 5. Recommended architecture

### 5.1 Date vocabulary (normative)

| Symbol | Meaning | Where it lives |
| --- | --- | --- |
| **P** | Publication date of a version (BOE `fecha_publicacion`; selector radio `value`; Diario date). | Version records |
| **E** | Legal-effect date of a version (BOE `fecha_vigencia` / "en vigor a partir del"; Diario effect clause). | Version records |
| **L** | Legal date of a composition and of a release (2026-11-02 for this cutoff). | Composition manifest, snapshot `legal_date`, release `manifest.json` |
| **C** | Evidence cutoff: the date the artifacts were captured. Amendments published after C are unknown to the snapshot. | Composition manifest |
| **Q** | Legal date of the user's question (`LegalContextV1.legal_date`, basis `user` / `consultation_date` / `evaluation_override`). | Agent state |
| **[W_from, W_to]** | Wording window of a unit: from the E of the selected version, to the day before the earliest known pending E (open if none). | Unit `metadata.temporal`; projected into the sidecar |

Rules:
- A version is **applicable at L** iff `E ≤ L` and `P ≤ L`.
- A version with `P > L` but `E ≤ L` is retroactive. It is not used automatically: it raises `PUBLISHED_AFTER_LEGAL_DATE` for review.
- The law's entry-into-force date is never a wording date (OPERATIONS rule, retained).

### 5.2 Source provenance

#### 5.2.1 Artifact store (new, immutable)

Table `legal_v3_source_artifacts` (model `V3SourceArtifact`):

| Field | Type | Notes |
| --- | --- | --- |
| `id` | BigAuto | |
| `sha256` | char(64), **unique** | SHA-256 of `content.encode('utf-8')` (same rule as today). |
| `document_id` | char(255), indexed | The consolidated law the artifact concerns. For Diario artifacts this is the law being amended; the instrument id is in `official_id`. |
| `official_id` | char(255) | BOE id of the artifact's own document: the law itself, or e.g. `BOE-A-2026-20823`. |
| `artifact_kind` | closed choice | `boe_consolidated_html`, `boe_consolidated_xml`, `boe_diario_html`. |
| `url` | text | Exact URL fetched; must be on `https://www.boe.es/`. |
| `selection_p` | char(8), null | `p=` value for historical consolidated selections. |
| `content` | text | Exact UTF-8 response. A non-UTF-8 response is rejected. |
| `retrieved_at` | datetime | |
| `retrieved_by_run` | FK → `V3IngestionRun`, PROTECT, null | The composition run that fetched it. |

Rules:
- Immutable via a PostgreSQL trigger (same pattern as `0012`, new function `legal_v3_artifact_immutable`).
- Inserted only by the composition command, using `get_or_create` keyed by `sha256` within the persisting transaction under `lock_corpus_writer()`.
- Not used for, or back-filled into, existing single-artifact snapshots. They keep `source_html` inline.

#### 5.2.2 Composition manifest (new manifest kind)

The manifest is stored in the same place as today (`V3SourceRecord.extra_metadata['integrity_manifest']`), registered by the unchanged `v3_register_source_review`, and kept under review as `docs/V3/corpus_ingestion/reviews/<ID>.asof-<L>.json`.

A manifest **without** `kind`, or with `kind: "single_artifact"`, follows the existing path unchanged.

```json
{
  "kind": "as_of_composition",
  "schema": 1,
  "approved": true,
  "document_id": "BOE-A-2015-11724",
  "legal_date": "2026-11-02",
  "evidence_cutoff": "2026-11-0X",
  "base_artifact": "<sha256 of current consolidated HTML>",
  "artifacts": [
    {"sha256": "…", "kind": "boe_consolidated_html", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724", "selection_p": null, "role": "base"},
    {"sha256": "…", "kind": "boe_consolidated_html", "url": "https://www.boe.es/buscar/act.php?id=BOE-A-2015-11724&p=20241221&tn=1", "selection_p": "20241221", "role": "block_source"},
    {"sha256": "…", "kind": "boe_consolidated_xml", "url": "https://www.boe.es/datosabiertos/api/legislacion-consolidada/id/BOE-A-2015-11724/texto", "role": "xml_crosscheck"},
    {"sha256": "…", "kind": "boe_diario_html", "url": "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-21872", "official_id": "BOE-A-2026-21872", "role": "amending_instrument"}
  ],
  "citable_blocks": ["…as-of inventory…"],
  "excluded_blocks": [],
  "context_blocks": [{"block_id": "…", "role": "…"}],
  "reviewed_inline_notices": [{"block_id": "a72", "sha256": "042ccc9b…"}],
  "blocks": {
    "a144": {
      "source_artifact": "<sha of p=20241221 selection>",
      "selected_version": {"selection_p": "20241221", "published": "2024-12-21", "effective_from": "2025-03-03",
                           "xml": {"id_norma": "BOE-A-2024-26693", "fecha_publicacion": "20241221", "fecha_vigencia": "20250303"}},
      "pending_versions": [{"source_artifact": "<base sha>", "published": "2026-10-21", "effective_from": "2026-12-01",
                            "xml": {"id_norma": "BOE-A-2026-21872", "fecha_publicacion": "20261021", "fecha_vigencia": "20261201"},
                            "effect_evidence": {"artifact": "<diario sha>", "provision_ref": "disposición final cuarta",
                                                "clause_text": "<verbatim effect clause>"}}],
      "decision": "SUBSTITUTE_PRIOR_VERSION_DEFERRED_AMENDMENT",
      "legal_basis": "reviewed_composition"
    }
  },
  "not_in_force_blocks": [],
  "restored_blocks": [],
  "status_evidence": [{"official_id": "BOE-A-2024-664", "artifact": "<sha>", "effect": "DEROGATION_OF_INSTRUMENT", "affects_instrument": "BOE-A-2023-25759"}],
  "legal_review": {
    "reviewer": "<recorded by owner>",
    "reviewed_on": "YYYY-MM-DD",
    "scope_attestation": {"code": "DEFERRED_EFFECTS_AND_REPEALS_CHECKED", "instruments_reviewed": ["BOE-A-…"], "flagged_blocks_reviewed": ["…"]},
    "decisions": [
      {"block_id": "a248", "question": "IMPLIED_DISPLACEMENT", "outcome": "accepted", "interpretation": "CC_2_2_LATER_INCOMPATIBLE_LAW",
       "rationale_ref": "docs/V3/corpus_ingestion/OPERATIONS.md#lgss-article-248-chronology-2026-11-03"},
      {"block_id": "a72", "question": "COMMENCEMENT_CONDITION", "outcome": "open", "rationale_ref": "…"}
    ]
  },
  "release_with_uncertainty": ["a72"]
}
```

Notes:
- Blocks absent from `blocks` are taken from the base artifact. Their basis is computed mechanically (§5.5).
- `reviewed_inline_notices` replaces the LGSS-specific hard-coded a72 hash in `boe_context.editorial_notes` (`boe_context.py:103`). It is optional; see D7.
- Closed `decision` codes:
  - `KEEP_BASE`
  - `SUBSTITUTE_PRIOR_VERSION_DEFERRED_AMENDMENT`
  - `SUBSTITUTE_PRIOR_VERSION_PUBLISHED_AFTER_L`
  - `RESTORE_BLOCK_REPEAL_NOT_YET_EFFECTIVE`
  - `EXCLUDE_BLOCK_NOT_YET_IN_FORCE`
- Closed `question` codes:
  - `IMPLIED_DISPLACEMENT`
  - `COMMENCEMENT_CONDITION`
  - `INSTRUMENT_DEROGATION_EFFECT`
  - `TRANSITIONAL_REGIME`
  - `RETROACTIVE_EFFECT`
  - `OVERLAPPING_AMENDMENTS`
  - `INTRA_BLOCK_MIXED_EFFECT`
- Closed `outcome` codes: `accepted`, `rejected`, `open`.

#### 5.2.3 How this avoids misrepresentation

- Each unit's `metadata.canonical_url` points to **its own** artifact URL plus `#block` (e.g. `…&p=20241221&tn=1#a144`).
- The document keeps `source_url` = the base canonical URL, as required by the existing gate.
- Document metadata records:
  - `content_format: "boe_asof_composition"`
  - `representation: "reconstructed_as_of"`
  - `official_publication: false`
  - `legal_date`
  - `composition_digest`
- `version_label` becomes `Composición a fecha L a partir de N textos consolidados oficiales del BOE`. It never uses the `Última actualización publicada el …` form.
- The agent sees this through `wording_basis` (§5.6). Rendered text must not call the document an official consolidation.

### 5.3 Temporal reconstruction rules (mechanical algorithm + review triggers)

Inputs: the base artifact B (current consolidated HTML), declared block-source artifacts, the XML artifact X, Diario artifacts, and L.

For each block `b` in B (citable or context):

1. **Read displayed version.**
   - Parse the checked radio of `b`'s version selector into `(P, E, not_yet_in_force)`.
   - If there is no selector, use the `pie_unico` "Texto añadido, publicado el P, en vigor a partir del E" note.
   - If neither exists, the block is the original text: `E = document entry-into-force`, `basis_hint = original`.
   - A label with no effect date (e.g. "Texto consolidado a fecha D.") gives `E = unknown`.
2. **Applicable?**
   - If `E ≤ L` and `P ≤ L`: `KEEP_BASE`.
   - If E is unknown: the block is `unestablished` unless the manifest gives Diario evidence for E.
3. **Not applicable** (`E > L`, `P > L`, or `[No vigente aún]`):
   - The manifest **must** substitute the immediately preceding version in `b`'s own radio list (next older `p`) with E′ ≤ L.
   - The block-source artifact's own selector for `b` must show that version checked.
   - The XML version named in the manifest must exist with matching dates, and the block text must equal it (named-version comparison, not date-only).
   - If the immediately preceding version also has E′ > L, recurse to the next older one.
   - The displaced newer version(s) are recorded as `pending_versions`, with XML identity and Diario effect evidence.
4. **Block added by a future version** (no older radio, or absent from the preceding selection): `EXCLUDE_BLOCK_NOT_YET_IN_FORCE`, recorded in `not_in_force_blocks` with evidence. This is a declared as-of inventory change, not an exclusion of a citable block, so the existing exclusion rule is untouched.
5. **Block repealed or suppressed by a future version** (B shows a repealed range or "sin contenido" with E > L): `RESTORE_BLOCK_REPEAL_NOT_YET_EFFECTIVE` from the preceding selection. The repeal is recorded as pending.
6. **Mixed effects inside one BOE version** (the Diario effect clause gives different dates to parts of a single block): fail closed with `NO_OFFICIAL_BLOCK_VERSION`. Requires a `INTRA_BLOCK_MIXED_EFFECT` review. v1 offers no automatic splice.
7. **Derogated amending instruments** (Congress non-validation or derogation resolution): versions attributed to such an instrument are never selected mechanically. A substitution that skips them requires `status_evidence` plus an `INSTRUMENT_DEROGATION_EFFECT` review decision.
8. **Overlapping amendments to one block** (e.g. RDL 13/2022 + LO 10/2022): handled by the version chain. A composite block that matches a single BOE version is `KEEP_BASE`. An `OVERLAPPING_AMENDMENTS` review is required only when the XML version attribution is inconsistent with the Diario texts.
9. **Transitional provisions** inside the law are ordinary units (`dt-*`) and stay retrievable. Transitional rules in **amending instruments** (outside the corpus) are recorded per block as `transitional_evidence`: instrument, provision reference, verbatim clause text plus SHA-256 verified present in the Diario artifact, and window. These are exposed as non-citable evidence (§5.6).
10. **Tables:** a substituted block carries the tables of its own artifact. The existing per-block table checks (rows, cells, spans, captions) run against that artifact. Pending versions keep their rendered tables (`_unit_block_text`) inside `pending_versions`. A table found only inside a `soloTexto` editorial notice is historical context, not operative (existing evidence pattern).
11. **Window:**
    - `W_from` = E of the selected version (or the document entry-into-force date for original text).
    - `W_to` = (minimum E among `pending_versions`) − 1 day; null if there are none.
    - The snapshot's `wording_valid_from` = max over units of `W_from`, and `wording_valid_to` = min over units of `W_to`. These are the window in which the whole composition is the complete as-of text known at C.

### 5.4 Immutable snapshots: schema and version contracts

**Migration `0014_v3_asof_composition`** (additive only):

1. `CreateModel V3SourceArtifact`, plus the immutability trigger (RunPython, PostgreSQL only, reversible).
2. `AddField V3DocumentSnapshot.snapshot_kind`: CharField(32), **null=True, no default**. `NULL` means the existing observation semantics. The only other value is `as_of_composition`.
3. `AddField V3DocumentSnapshot.legal_date`: DateField, null=True.
4. `AddField V3DocumentSnapshot.composition`: JSONField, null=True. It holds the exact registered manifest.

Adding nullable columns without a default is a catalog-only `ALTER TABLE … ADD COLUMN` in PostgreSQL. It rewrites no rows and does not fire the row-level `BEFORE UPDATE` trigger. Existing rows keep identical stored values, and their digests recompute unchanged.

**Composition snapshot content:**
- `document`, `units`, `chunks`: the same payload shape as `_retain_document_snapshot` today.
- `source_html`: `NULL`.
- `snapshot_kind`: `"as_of_composition"`.
- `legal_date`: L.
- `composition`: the manifest.
- `wording_valid_from` / `wording_valid_to`: per §5.3 step 11.
- `content_digest` = SHA-256 over canonical JSON `{"payload": …, "source_html": null, "composition": manifest, "artifacts": sorted([sha256…]), "legal_date": "YYYY-MM-DD"}`.
- The observation digest formula is unchanged.

**Required code detail.** `_retain_document_snapshot` currently returns early, without creating a row, when `source_html is None` and an identical payload exists (`source_ingestor.py:871`). The composition path must bypass that de-duplication. Otherwise a composition whose payload equals a prior observation would never get its snapshot, and the gate would fail.

**Version contracts:**

| Contract | Old | New |
| --- | --- | --- |
| Manifest | implicit single-artifact | `kind` ∈ {absent / `single_artifact`, `as_of_composition`}, `schema: 1` |
| Ingestion run | `INGEST_VERSION='v3-boe-single-source-v1'` | Composition runs: `'v3-boe-asof-composition-v1'`; `input_checksum` = composition digest; `metadata.content_format='boe_asof_composition'`; `metadata.artifacts=[sha…]` |
| Unit metadata | `block_id`, `tables`, `editorial_provenance`, `source_forms`, `canonical_url` | Plus `temporal` (§5.6.1) for **all** documents (derived mechanically for single-artifact ones; not a release-relevant change of text) plus `source_artifact` (sha) for composed units |
| Release `manifest.json` | release id, hashes, counts, embedding model | Plus `payload_schema: 2`, `legal_date`, `temporal_status_policy` (`masked` / `basis_gated`, see D3), `wording_valid_through` (min unit `W_to`, or null) |
| Sidecar `documents.json` units | as today | Plus a `temporal` object; `status`/`effective_from`/`effective_to` projected per §5.6.1 |

Unit identities (`unit_id`, unit and chunk PKs), chunk text and `text_sha256` rules are unchanged. `version_id = unit_id@snapshot:<sha12>` is already content-addressed, so a substituted wording gets a new `version_id` under the same citation identity.

### 5.5 Legal uncertainty: basis levels

Every unit receives exactly one `wording_basis`:

| `wording_basis` | How it is obtained | Agent status | `valid_at_legal_date` for Q |
| --- | --- | --- | --- |
| `boe_consolidated` | Single-artifact or `KEEP_BASE` block whose displayed version has an explicit E ≤ L and P ≤ L in BOE metadata. | `current` only if `temporal_status_policy=basis_gated` (D3); else `unknown` (today's behavior). | yes in window / no outside / unknown if masked |
| `reviewed_composition` | Substituted / restored / excluded block whose mechanical evidence chain is complete, covered by the reviewer's scope attestation. | `current` | yes in window / no outside |
| `reviewed_interpretation` | A `legal_review.decisions` entry with outcome `accepted` and an interpretation code. | `current` | yes in window, with notice `INTERPRETATION_APPLIED:<code>` |
| `conditional` | A `COMMENCEMENT_CONDITION` decision with outcome `open`. | `unknown` | unknown, with notice `CONDITION_UNRESOLVED` |
| `contested` | Any other `open` decision, or a mechanical rule that requires review and has none. | `unknown` | unknown, with notice `LEGAL_REVIEW_OPEN` |
| `unestablished` | No E available. | `unknown` | unknown (today's behavior) |

Gate policy:
- `conditional`/`contested` units are allowed in a release **only** if listed in `release_with_uncertainty` (D2).
- A `rejected` decision without an alternative composition blocks the document.

### 5.6 RAG integration: exact changes to reach the Researcher

Storing metadata is not enough: R7 shows the current tool contracts drop it. The following path is required end to end.

#### 5.6.1 Release payload (`agent_release._canonical_payload`)

Signature: `_canonical_payload(*, require_reviewed=False, legal_date=None, temporal_status_policy='masked')`.

For each unit:
- Read `unit.metadata['temporal']`. If absent (legacy rows), derive it from `source_forms` and `editorial_provenance` with the S1 parser.
- Emit:
  ```json
  "temporal": {
    "schema": 1,
    "wording_basis": "…",
    "wording_effective_from": "…",
    "wording_effective_to": "…",
    "legal_date": "L",
    "selected_version": {"published": "…", "effective_from": "…", "amending_id": "…|null"},
    "pending_versions": [{"published": "…", "effective_from": "…", "amending_id": "…", "text": "…", "text_sha256": "…"}],
    "amendments": [{"official_id": "…", "provision_ref": "…", "published": "…", "effective_from": "…", "url": "…"}],
    "transitional_evidence": [{"official_id": "…", "provision_ref": "…", "text": "…", "sha256": "…", "applies_until": "…|null"}],
    "notices": ["CLOSED_CODE", "…"]
  }
  ```
- Projection rule: if `wording_basis ∈ {reviewed_composition, reviewed_interpretation}`, or it is `boe_consolidated` under policy `basis_gated`, emit `status='current'`, `effective_from=W_from`, `effective_to=W_to`. Otherwise keep today's projection (`status='unknown'`, document dates).
- DB columns `V3LegalUnit.effective_from/effective_to` and chunk dates are **not** repurposed: the OpenSearch projection (`opensearch_index.py:102`) and the legacy engine read them with document-level meaning.

Embedding record specs (`agent_records._specs`) do not include `temporal`, so existing checkpoints stay valid. Only units whose canonical text changes (the IRPF/LGSS substituted blocks) need new vectors.

#### 5.6.2 Agent store and refs (shared corpus layer, both branches)

- `provision_store.StoredUnit`: add `temporal: dict = {}`; `_unit()` reads `row.get('temporal') or {}`. Old sidecars still load.
- `refs.build_source_ref`: unchanged validity arithmetic. It already gives `no` outside `[start, end]` and `yes` for `current` + start + `is_current_text`. Add:
  - `wording_basis` (from temporal, default `unestablished`);
  - `next_wording_effective_from` (min pending E);
  - `temporal_notices` (closed codes).
- `SourceRefV1` (contracts) gets these optional additive fields:
  ```
  wording_basis: Literal["boe_consolidated","reviewed_composition","reviewed_interpretation","conditional","contested","unestablished"] = "unestablished"
  next_wording_effective_from: date | None = None
  temporal_notices: list[Literal["INTERPRETATION_APPLIED","CONDITION_UNRESOLVED","LEGAL_REVIEW_OPEN","PENDING_WORDING","RECONSTRUCTED_AS_OF","WORDING_BEFORE_WINDOW","WORDING_AFTER_WINDOW"]] = []
  ```
  The interpretation code is carried in `ProvisionTemporalV1`, not in the literal.

#### 5.6.3 Tool outputs

- `search_law`: no ranking or filter change. Hits already carry `ref`, so the Researcher sees `wording_basis` and `next_wording_effective_from` at discovery time. The index keeps exactly one record per unit, containing the applicable text. Pending wording is **not** embedded.
- `read_provision`: `ProvisionTextV1` gains `temporal: ProvisionTemporalV1 | None` containing:
  - `amendments`, `transitional_evidence`;
  - `pending_versions` (each with `effective_from`, `amending_id`, `text`, `text_sha256`, `in_force_at_legal_date: bool`);
  - `notices`, and `interpretation` (code plus `rationale_ref`).

  Pending text is returned but is **not citable**, by construction:
  - The validator read set is keyed by `unit_id` (R6), and quote verification matches `quote_fragments` against the applicable text (`validator.py` V2 text lookup).
  - A quote taken from pending wording therefore fails quote verification.
  - A citation of the applicable version when `Q > W_to` yields `valid_at_legal_date='no'` and the existing V3 annotation.

  Making pending versions separately citable would need validator/state keyed by `(unit_id, version_id)`. That is deferred to v2.
- `get_document_outline` and `list_corpus_documents`: unchanged except that outline entries inherit `status` from the payload.

#### 5.6.4 Validator, render, prompt (serving consultation branch)

- Validator V3: unchanged trigger logic. Annotation text per notice:
  - `CONDITION_UNRESOLVED` → "vigencia condicionada no verificada; verifique la versión aplicable";
  - `LEGAL_REVIEW_OPEN` → "aplicabilidad pendiente de revisión jurídica";
  - `RECONSTRUCTED_AS_OF` is informational and adds no annotation.
- Render (`render.py:170`): "versión vigente a Q" only when `valid_at_legal_date=='yes'` and `status=='current'` (as today). Append "(interpretación revisada)" for `reviewed_interpretation` and "(texto reconstruido a fecha L a partir de versiones consolidadas oficiales del BOE)" for `reviewed_composition`.
- Prompt (the active `system_v*.md`, one sentence added to **Time**): "If `wording_basis` is `conditional` or `contested`, or `next_wording_effective_from` ≤ the legal date, record a `VERSION_UNCERTAIN` gap. Pending wording in `temporal` is not in force before its date and must not be cited." Prompt changes follow the consultation branch's existing evaluation rules.
- Telemetry (CLAUDE.md rule): add turn counts `cited_by_wording_basis` (closed keys) and `pending_wording_reads` to `consultation/telemetry.py::turn_metrics`. Update `ops_report.py`, the runbook and `tests/v3/test_consultation_telemetry_coverage.py`. Telemetry carries no text.

### 5.7 Release safety

`_canonical_payload(require_reviewed=True, legal_date=L, …)` raises with a closed reason on any of the following.

**All documents:**

| Code | Rule |
| --- | --- |
| SA-1 `FUTURE_WORDING_PRESENTED` | Any unit whose displayed version (selector checked label or `pie_unico`) has `E > L`, `P > L`, or `[No vigente aún]`, in a single-artifact snapshot. Mechanical, corpus-wide (R9). |
| SA-2 `LEGAL_DATE_REQUIRED` | Production staging/promotion without L. |
| SA-3 | Existing checks unchanged: reviewed manifest, snapshot/hash match, exact row equality, per-artifact conservation. |

**Composition documents** (`manifest.kind == as_of_composition`):

| Code | Rule |
| --- | --- |
| CR-1 | Exactly one snapshot with `snapshot_kind='as_of_composition'`, `composition == registered manifest` (canonical JSON equality), `legal_date == manifest.legal_date == L`. Recomputed digest matches. |
| CR-2 | Every manifest artifact exists in `legal_v3_source_artifacts` with matching SHA-256 (recomputed from `content`), kind and URL. URL host is `www.boe.es`. Each HTML artifact's `#id_local` equals `document_id`, except Diario artifacts, which must equal their `official_id`. |
| CR-3 | Base artifact passes the existing page-level structure checks. Each block-source artifact passes the page-level checks: no substantive content outside blocks, no unvetted controls or visuals. |
| CR-4 | Each unit passes the existing per-block conservation, editorial, table and form checks **against its own source artifact**. |
| CR-5 | As-of inventory = base citable set − `not_in_force_blocks` + `restored_blocks`, and equals the parsed and manifest `citable_blocks`. |
| CR-6 | Every substitution satisfies §5.3 step 3: selector chain, named XML version, dates. Every pending version has a Diario effect clause whose verbatim text occurs (whitespace-normalized) in its Diario artifact. |
| CR-7 | Every block in the base whose displayed version is not applicable at L is substituted, restored or excluded. None may be silently kept. |
| CR-8 | `legal_review` present, with `scope_attestation.code`. Every mechanically flagged block has a decision. `conditional`/`contested` units appear in `release_with_uncertainty`, else reject. |
| CR-9 | `L ∈ [snapshot.wording_valid_from, snapshot.wording_valid_to]` (open upper bound allowed). |
| CR-10 | Old code reading a composition manifest fails closed. Verified: `manifest.get('sha256')` is absent, so `snapshot is None` raises "Reviewed source artifact is absent". |

**Serving-time safety:**
- Release `manifest.json` records `wording_valid_through`.
- After that date, affected units naturally return `valid_at_legal_date='no'` for `Q > W_to`, and the validator annotates. Pending wording is visible but uncitable. Nothing is silently presented as current.
- Ops rule: rebuild the composition and release at each pending effect date (calendar = the set of pending E values). Example: LGSS on 2026-12-01; IRPF and LGSS on 2027-01-01.
- An ops alert is emitted when the serving date passes `wording_valid_through`. `pin_release` must **not** refuse a release on that basis (no outage).

---

## 6. Data flow

```
Official BOE artifacts, fetched by the guarded pipeline (V3_INGESTION_TARGET), each SHA-256 bound to the manifest
  ├─ base consolidated HTML (current page)
  ├─ historical consolidated HTML selections (act.php?id=…&p=YYYYMMDD&tn=1)
  ├─ consolidated XML (block versions with id_norma / fecha_publicacion / fecha_vigencia)
  └─ Diario HTML of amending / validating / derogating instruments
        │  get_or_create by sha256 (immutable table legal_v3_source_artifacts)
        ▼
reviewed composition manifest  ──  v3_register_source_review (unchanged command; dispatch on kind)
        ▼
v3_compose_as_of <ID> --legal-date L  [--dry-run]
   fetch → hash-match → parse base → parse_boe_block for each substituted block
   → validate_composition (CR-2…CR-9)
        ▼
_persist_parsed_document(..., composition=manifest)        (same transaction, corpus writer lock)
   → prior state retained as observation snapshot (existing behavior)
   → V3LegalDocument / V3LegalUnit / V3SearchChunk updated in place (same unit_id / PKs; graph-safe replacement)
   → V3DocumentSnapshot(kind=as_of_composition, legal_date=L, composition, wording window)
        ▼
v3_validate_ingestion --document-id <ID>   (composition-aware)
        ▼
_canonical_payload(require_reviewed, legal_date=L, policy)   (SA-*, CR-*)  → documents.json with unit.temporal
        ▼
build-records (PAID; separately authorized) → stage (manifest.json: legal_date, policy, wording_valid_through) → promote/rollback (unchanged CAS)
        ▼
Agent turn: pin_release → IndexRecordsProvisionStore (StoredUnit.temporal)
   → search_law hits: ref.wording_basis, next_wording_effective_from
   → read_provision: applicable text + temporal (amendments, pending wording, transitional evidence, notices)
   → build_source_ref(Q): valid_at_legal_date yes / no / unknown
   → validator V2 (quotes only from applicable text) / V3 (window, status, notices) → render
```

---

## 7. Deterministic validation vs legal interpretation

| Question | Mechanical (software decides pass/fail) | Human legal review (software checks only the record) |
| --- | --- | --- |
| Is this artifact the official BOE response declared? | URL host, SHA-256, `id_local`, kind | — |
| Is the unit text exactly the official block text? | Per-block conservation, tables, editorial separation, forms | — |
| What versions exist, and what are their P/E according to BOE? | Selector labels, XML attributes, named-version text equality | — |
| Is the displayed wording future-effective per BOE metadata? | SA-1 / CR-7 | — |
| Does the Diario contain the declared effect clause? | Verbatim clause found in the hashed Diario artifact | That the clause governs this block/paragraph and fixes this E |
| Did a later law implicitly displace a deferred earlier wording (LGSS a248)? | Detect: two versions with incompatible text and E ordering inverted vs P | `IMPLIED_DISPLACEMENT` decision |
| Has a statutory condition for commencement or repeal been met (LGSS a72)? | Detect: a reviewed inline notice referencing a condition | `COMMENCEMENT_CONDITION` decision (needs proof of an enacted regulation, or of its absence, by L) |
| Effect of non-validation or derogation of a decree-law (RDL 26/2026, RDL 7/2023)? | Detect: versions attributed to an instrument named in `status_evidence` | `INSTRUMENT_DEROGATION_EFFECT` decision |
| Transitional survival of prior wording (e.g. RDL 2/2024 DT1)? | Window arithmetic against the declared `applies_until` | `TRANSITIONAL_REGIME` decision, if the window intersects L |
| Are there effects BOE metadata does not express (implied repeals, entry-into-force clauses not reflected)? | Not detectable | `scope_attestation` (whole-law) |
| Mixed effect dates inside one BOE block version | Detect: two or more effect clauses for one block | `INTRA_BLOCK_MIXED_EFFECT` (v1: blocks the document) |

Software success **never** constitutes legal certification. A composed document is releasable only with the reviewer's recorded attestation and decisions. The rendered output labels reconstructed wording as such.

---

## 8. Migration, compatibility, rollback, production safety

**Migration**
- `0014` is additive: a new table, a trigger and three nullable columns.
- Apply only in an explicitly authorized deployment window (existing OPERATIONS rule).
- Before and after applying, recompute: the 69 snapshot digests, the documents/units/chunks/snapshots/graph fingerprints (the protected-baseline method in OPERATIONS), and confirm `legal_v3_snapshot_no_update_delete` is enabled. All must be identical.

**Compatibility**
- Single-artifact manifests: unchanged validation path.
- Old agent with new sidecar: unknown keys are ignored (`_unit` uses `.get`).
- New agent with old sidecar: `temporal` absent, so `unestablished`, which is today's behavior.
- `payload_schema` absent means 1.
- With policy `masked`, the payload for the 48 documents differs from today only by the added `temporal` key.

**Rollback**
- *Code:* revert. Old code fails closed on composition manifests (CR-10). It does not misread them.
- *Sidecar:* the existing `v3_agent_release rollback --expected-current`.
- *Canonical rows of a composed document:* the prior state is retained as an immutable observation snapshot by the existing `_persist_parsed_document`. A restore to the original IRPF/LGSS rows uses the verified original-20 archive (`original20-pre-reingestion.zip`, SHA-256 `1205875a…`) through the separately authorized restore procedure. No new restore tooling is proposed.
- *Schema:* forward-only once any `as_of_composition` row or artifact exists. Reversing `0014` would drop immutable evidence and is prohibited.

**Production safety**
- No snapshot or artifact row is ever updated or deleted.
- No existing manifest is rewritten.
- IRPF/LGSS remain BLOCKED until their composition passes in isolated PostgreSQL **and** their legal review record is complete.
- Write-target guard, corpus writer lock, manifest-change concurrency check and failed-run audit behavior are reused unchanged.
- The `rnd` script-nonce issue is handled as today: a changed artifact gets a newly reviewed hash; there is no normalization.
- Paid embedding and index publication remain separately authorized.

---

## 9. Staged implementation plan (Sonnet)

Base all ingestion-side work on `impl/corpus-ingestion@51f3045d`. Run every test against disposable loopback PostgreSQL (`V3_INGESTION_TARGET=isolated`, `test_` database), never DigitalOcean.

Baseline suite = the isolated command in OPERATIONS "Isolated verification" plus `test_boe_editorial_notes.py`, `test_boe_xml_coverage_comparison.py`, `test_boe_xml_version_selection.py`, `test_v3_boe_structural_scope_regressions.py`, `test_v3_quoted_amendment_integrity.py` and `test_original20_regional_reingestion.py`. The last recorded result was 147 passed. Run `ruff check .` per task.

Each task is one commit (CLAUDE.md commit discipline) and must update OPERATIONS.md when behavior changes.

### S0: Decisions and branch setup (no code)
- **Inputs:** owner answers D1–D7.
- **Action:** create the feature branch from `impl/corpus-ingestion`.
- **Verify:** `git merge-base --is-ancestor 51f3045d HEAD`.
- **Gate:** decisions recorded in this ADR's §12, in the owner's words.

### S1: Version metadata parsing and read-only inventory
- **Add** `services/v3/ingestion/boe_versions.py`:
  - `parse_version_selector(form_html) -> list[VersionOption(p, kind, published, effective|None, not_yet_in_force, checked)]`. Same label grammar as `classify_form`; fail on anything else.
  - `displayed_version(unit_metadata) -> VersionOption|None`.
  - `added_text_effect(editorial_provenance)`.
- **Extend** `scripts/verify_boe_xml_coverage.py`:
  - `--block-version BLOCK=ID_NORMA@YYYYMMDD` (repeatable): compare the named version instead of `applicable_version`.
  - `--inventory`: JSON per block of `(id_norma, fecha_publicacion, fecha_vigencia)` and HTML displayed version.
- **Add** read-only command `v3_temporal_inventory --legal-date L [--document-id …]`. It reads retained reviewed snapshots and reports, per document, units with displayed `E>L`, `P>L`, `E unknown`, `[No vigente aún]`. Counts and ids only. It holds no lock, writes nothing and refuses `production` unless `--read-only-ack`.
- **Tests:** label grammar (all `classify_form` patterns, including empty-date and `[No vigente aún]`); `BOE-A-1885-6627` fixture radios; unordered XML versions with a named version; inventory on a synthetic snapshot with one future block.
- **Gate:**
  - Baseline suite passes.
  - Inventory run over the isolated corpus copy for all 48 reviewed documents.
  - Result (counts only) appended to OPERATIONS.
  - Corpus fingerprint unchanged.
  - **If any of the 48 shows SA-1 exposure, record it as a new blocker.** It must not be waived.

### S2: Schema `0014` and artifact store
- **Files:** `models.py` (`V3SourceArtifact`; three snapshot fields), `migrations/0014_v3_asof_composition.py`.
- **Tests (new `test_v3_source_artifacts.py`):**
  - artifact update/delete raises `DatabaseError`;
  - `sha256` uniqueness;
  - pre-existing snapshot rows keep identical digests after migrate;
  - `0012` trigger still enabled;
  - `makemigrations --check` clean.
- **Gate:** baseline suite and new tests pass. `python manage.py makemigrations --check --dry-run` reports no changes.

### S3: Behavior-preserving per-block parse/validate refactor
- **`source_ingestor.py`:** extract the per-block body of `_parse_boe_document` into `_parse_block(...)`. Add `parse_boe_block(source, html, canonical_url, block_id, base_context) -> ParsedLegalUnit`. Hierarchy and section path come from the base. Unit identity is derived from the block heading and must equal the base unit id.
- **`source_integrity.py`:** extract `validate_page_structure(html, document_id)` and `validate_block_conservation(block, unit, canonical_url)`. `validate_reviewed_boe_artifact` composes them with identical behavior.
- **(D7, optional)** `editorial_notes(block, reviewed_inline_notices=None)`: when a manifest supplies notices, use them; otherwise keep the existing a72 constant until S9 for LGSS.
- **Tests:** a golden test re-parsing every retained reviewed artifact available as a fixture asserts deep equality of `ParsedLegalDocument` and identical validation outcomes before and after.
- **Gate:**
  - Same comparison over all 48 retained reviewed source HTMLs from the isolated corpus copy: **0 diffs**.
  - Baseline suite passes.

### S4: Composition manifest and validator
- **Add** `services/v3/ingestion/asof_composition.py`:
  - `validate_composition_manifest(manifest, document_id)` (schema, closed codes, dates, uniqueness);
  - `compose_document(source, manifest, artifacts, legal_date) -> ParsedLegalDocument` (§5.3; per-unit `metadata.temporal`, `metadata.source_artifact`; document metadata per §5.2.3);
  - `validate_composition(parsed, manifest, artifacts, legal_date)` (CR-2…CR-9).
- **`validate_review_manifest`:** dispatch on `kind`.
- **Tests (new `test_v3_asof_composition.py`, offline mini-fixtures):** one positive (base + 1 historical selection + XML + Diario, one substituted block with a table, one pending version) and at least 16 negatives:
  1. artifact hash mismatch;
  2. non-BOE URL;
  3. wrong `id_local`;
  4. substituted block not checked in its source selector;
  5. substituted version E > L;
  6. skipped intermediate version;
  7. named XML version missing or dates differ;
  8. XML text differs;
  9. pending version without Diario clause;
  10. clause text not in Diario;
  11. future base block kept (CR-7);
  12. inventory mismatch;
  13. table cell drift in substituted block;
  14. open decision not in `release_with_uncertainty`;
  15. missing `scope_attestation`;
  16. `P > L` without review;
  17. intra-block mixed effects → `NO_OFFICIAL_BLOCK_VERSION`.
- **Gate:** all pass. Each negative asserts its closed reason code.

### S5: Compose command, persistence, snapshot kind, validation, telemetry
- **Add** `management/commands/v3_compose_as_of.py <official-id> --legal-date YYYY-MM-DD [--dry-run]`:
  - requires `require_ingestion_target()` for writes and an approved `as_of_composition` manifest;
  - fetches each artifact URL with the existing session/User-Agent and exact hash-match;
  - composes and validates, then persists.
- **`_persist_parsed_document`:** kwarg `composition`; sets the composition run version and checksum; uses the existing `expected_manifest` concurrency guard.
- **`_retain_document_snapshot`:** kwargs `snapshot_kind`, `composition`, `legal_date`, `wording_valid_from/to`; bypass the de-duplication when `composition` is set; composition digest per §5.4.
- **`v3_validate_ingestion`:** composition-aware (snapshot present, artifacts present, `input_checksum` == composition digest).
- **Telemetry:** wrap the command in `OperationRecorder("asof_composition", subject=document_id)` with counts (artifacts, substituted, pending, excluded, restored) and closed codes. If `ingestion/telemetry.py` is absent on the ingestion branch, port it verbatim from `impl/jev-triage-20261101` (D5). Add the operation to `OPERATIONS`, `ops_report.py`, the runbook and `test_telemetry_enforcement.py`, wherever those exist.
- **Tests (isolated PostgreSQL):**
  - end-to-end compose on the S4 fixture;
  - prior observation snapshot retained;
  - unit ids, unit and chunk PKs preserved;
  - graph-safe replacement rules unchanged;
  - injected failure rolls back everything, and the FAILED run audit commits;
  - manifest-changed-during-run rejected;
  - dry-run writes nothing;
  - telemetry emitted on success and failure.
- **Gate:** baseline suite, S4 and S5 tests pass. The fingerprints of unrelated documents are unchanged in the test database.

### S6: Release gate and temporal payload
- **`agent_release.py`:**
  - `_canonical_payload(require_reviewed, legal_date, temporal_status_policy)` with SA-1/SA-2 and CR-1…CR-10, temporal emission and projection (§5.6.1);
  - `stage_canonical_release` / `_switch_canonical_release` read `legal_date` and policy from args and the candidate `manifest.json`;
  - `stage_release` writes `payload_schema`, `legal_date`, `temporal_status_policy`, `wording_valid_through`.
- **`agent_records.py`:** pass `legal_date` and policy through.
- **`v3_agent_release` CLI:** `--legal-date` and `--temporal-status-policy` for `build-records`/`stage`; required in production.
- **Tests:**
  - policy `masked`: payload equals today's except the added `temporal` key, and `test_v3_agent_release_database.py:108` still sees `unknown`;
  - policy `basis_gated`: `yes` inside and `no` outside the window;
  - composition document passes;
  - SA-1 rejects a single-artifact future block;
  - old-format release still verifies;
  - embedding specs unchanged.
- **Gate:** all pass. A validation-only gate run on the isolated corpus copy gives the same BLOCKED reason as production today (IRPF/LGSS manifests), plus any SA-1 findings from S1.

### S7: Agent consumption (shared corpus layer + serving branch)
- **Shared files (apply identically on both branches):** `corpus/provision_store.py` (`StoredUnit.temporal`); `corpus/refs.py` (new ref fields).
- **Serving branch:**
  - `contracts.py` (`SourceRefV1` fields, `ProvisionTemporalV1`, `ProvisionTextV1.temporal`);
  - `tools/read.py` (attach temporal);
  - `validator.py` (notice-specific V3 annotation text only);
  - `render.py` (labels);
  - active prompt (one sentence);
  - `consultation/telemetry.py`, `ops_report.py`, runbook and `test_consultation_telemetry_coverage.py`.
- **Contract fixture:** S6 writes `tests/v3/fixtures/release_payload_v2.json` (synthetic). The same file is copied to the serving branch and consumed by its tests. This is the cross-branch contract.
- **Tests:**
  - valid matrix (Q before W_from, inside, after W_to; each basis);
  - a quote from pending wording fails V2 quote check;
  - pending reads counted in telemetry;
  - old sidecar loads with defaults.
- **Gate:** serving-branch full agent suite passes. Telemetry coverage test passes. No change to tool count or budgets.

### S8: IRPF and LGSS evidence, manifests, isolated trial (operator with BOE network access; no production writes)
- **Optional helper:** extend `v3_draft_source_review` with `--as-of L --artifact-dir DIR` to emit a **non-approving** draft composition (`approved:false`). Mechanical decisions are prefilled from selectors and XML. Review questions are listed as `open`.
- Capture every artifact listed in §10; record hashes in the coverage matrix.
- Run S1 `--block-version` comparisons per substituted block.
- Legal reviewer completes `legal_review`. The engineer must not fill legal outcomes.
- Run an isolated PostgreSQL replacement trial against the restored corpus copy: `v3_compose_as_of`, then `v3_validate_ingestion`, then the S6 gate (validation-only).
- **Gate (per law):**
  - composition passes;
  - only the listed blocks differ from the base parse;
  - XML named-version comparison 100% for substituted and pending blocks;
  - table cells and spans match;
  - all other documents and snapshots fingerprint-identical;
  - review record complete or the law stays BLOCKED.

### S9: Production (separately authorized window)
1. Apply `0014`; take the before/after fingerprints (§8).
2. Register both manifests (`v3_register_source_review`).
3. Run `v3_compose_as_of` per law, then `v3_validate_ingestion`.
4. Run the full `_canonical_payload(require_reviewed=True, legal_date=2026-11-02)` validation-only gate under the writer lock.
5. Record counts, run ids and digests in OPERATIONS and the matrix.
6. Embeddings and release staging/publication remain a further explicit authorization.

**Dependencies:**
- S1 → S6 (SA-1 needs the parser) and S8.
- S2 → S5.
- S3 → S4 → S5 → S6 → S7 and S8 → S9.
- S7 can proceed in parallel with S8 once S6's fixture exists.

---

## 10. How IRPF and LGSS resolve if legal review succeeds

Software success does not certify either law. Each becomes releasable only when its review record is complete. Hashes below come from OPERATIONS. Fresh captures will differ wherever BOE's `rnd` nonce changes and must be re-reviewed.

### IRPF `BOE-A-2006-20764`, L = 2026-11-02

| Block | Base (current page) | As-of decision | Evidence already recorded | Review needed |
| --- | --- | --- | --- | --- |
| a7 | 7.ñ (RDL 29/2026, E 2026-10-08) and 7.x (Ley 4/2026, E 2026-10-23) | `KEEP_BASE` | Both paragraphs match the Diario originals; normalized `a7` matches XML version `BOE-A-2026-20823` | Rest of article 7 under scope attestation |
| a24 | Future wording (E 2027-01-01) | `SUBSTITUTE_PRIOR_VERSION_DEFERRED_AMENDMENT` from `p=20261003` (SHA `eff053e4…`) | Matches the XML version attributed to the 2026-10-02 repeal resolution and the 2006 original version | `INSTRUMENT_DEROGATION_EFFECT` (RDL 26/2026, BOE-A-2026-20526) |
| a85 | Future wording plus a 5-row / 20-cell table (E 2027-01-01) | Substitute from `p=20261003`; the 2027 wording and table become `pending_versions` | `p=20261003` a85 matches Ley 26/2014 art. 1.57; no table; the future table matches the RDL 29/2026 Diario and the 2027 XML version | Same as a24 |

- Diario artifacts to retain: BOE-A-2026-20823 (RDL 29/2026, including the DF giving 2027-01-01), BOE-A-2026-20528 (Ley 4/2026), BOE-A-2026-20526 (Congress resolution), BOE-A-2014-12327 (Ley 26/2014).
- Window: a24/a85 `W_to` = 2026-12-31. Composition `wording_valid_to` = 2026-12-31. Rebuild for L = 2027-01-01.
- Whole-law attestation: the S1 inventory plus reviewer reading of the final and transitional provisions of every instrument with an IRPF version published in 2026. The mechanical XML scan found only a24/a85 with E > L.

### LGSS `BOE-A-2015-11724`, L = 2026-11-02

| Block(s) | As-of decision | Evidence already recorded | Review needed |
| --- | --- | --- | --- |
| a61, a190–a192 | `KEEP_BASE` (RDL 31/2026 effects 2026-11-01 / 2026-10-23) | Differ between the 2026-10-03 selection and the current page | Scope attestation |
| a144, a169, a171, a172, a173 | `SUBSTITUTE_PRIOR_VERSION_DEFERRED_AMENDMENT` from `p=20241221` (SHA `86d7913b…`), Ley 6/2024 versions E 2025-03-03; RDL 31/2026 wording pending E 2026-12-01 | Full text match; 17/17 Ley 6/2024 paragraphs present; RDL 31/2026 DF 4 defers | Mechanical, plus attestation |
| a309 | Substitute from `p=20220727` (SHA `8432e0f1…`), RDL 13/2022 version E 2023-01-01; RDL 31/2026 wording pending E 2027-01-01 | 5/5 paragraphs present | Confirm no intervening version (S1 selector chain check enforces this mechanically) |
| a274–a280, a282, a284, a287 | `KEEP_BASE` (RDL 2/2024 versions); RDL 7/2023 versions never selected | HTML equals the BOE-A-2024-10235 XML version; tables a277 (2) and a282 (1) match; extra XML tables are `soloTexto` history | `INSTRUMENT_DEROGATION_EFFECT` (BOE-A-2024-664); `TRANSITIONAL_REGIME` closed (window ended 2024-10-31) |
| a329, a331, a332, a337 | `KEEP_BASE` | Composite of RDL 13/2022 + LO 10/2022 paragraphs verified against the Diario texts | `OVERLAPPING_AMENDMENTS`: confirm the composite is in force at L (both effects ≤ 2023-01-01) |
| dtdecima | `KEEP_BASE` (suppressed E 2025-04-01; no operative table) | RDL 11/2024 art. 1.10 + DF 3 | Mechanical |
| a248 | `KEEP_BASE` (RDL 11/2024 rewrite, E 2025-04-01) | All 14 paragraphs match the 2024 Diario text | `IMPLIED_DISPLACEMENT`: if accepted → `reviewed_interpretation`; if open → `contested` (needs `release_with_uncertainty` or blocks); if rejected → requires an alternative composition (v1 cannot produce it automatically; LGSS stays blocked) |
| a72 | `KEEP_BASE`; the inline conditional-repeal notice is a reviewed inline notice | Text equals the Ley 19/2021 XML version; Council of Ministers record (2026-04-14) and Congress record (2026-06-15) show the regulation still in draft | `COMMENCEMENT_CONDITION`: only official proof of an enacted regulation (or authoritative evidence of none) by L closes it. Otherwise `conditional`, releasable only if listed in `release_with_uncertainty` (D2) |

- Window: a144–a173 `W_to` = 2026-11-30; a309 `W_to` = 2026-12-31. Composition `wording_valid_to` = 2026-11-30. Rebuild for L = 2026-12-01 and 2027-01-01.
- The 2026-10-03 selection's `da-nueva-sic` identity ambiguity is irrelevant: that artifact is not used, and block-scoped parsing (S3) never parses unrelated blocks of a source artifact.

---

## 11. Estimates (separate dimensions)

| Dimension | Estimate | Main drivers |
| --- | --- | --- |
| **Engineering complexity** | Medium–high. | Touches the immutable snapshot table, the release gate, a parser refactor that must be byte-identical, and a cross-branch agent contract. The design itself is additive and reuses existing checks. |
| **Execution effort** (Sonnet-sized tasks, excluding legal review and authorization waits) | S1 1–1.5 d · S2 1 d · S3 2 d · S4 2.5–3 d · S5 2 d · S6 1.5–2 d · S7 2–2.5 d (two branches) · S8 1–2 d engineering · S9 0.5 d. **Total ≈ 14–17 engineer-days.** | S3 golden diff over 48 documents; S4 negative matrix; S7 dual-branch port and telemetry coverage. |
| **Legal-review uncertainty** | IRPF: low–medium (two substitutions; one derogation-effect decision plus attestation). LGSS: medium–high. | a248 is an interpretation. a72 is likely to remain `conditional` unless official enactment evidence by 2026-11-02 is found. The derogation effect of RDL 7/2023 needs confirming. The whole-law attestation scope is large. |
| **Residual risk after release** | Effects not expressed in BOE consolidation metadata (implied repeals; BOE FAQ). | Mitigated only by reviewer attestation. It is disclosed through `wording_basis`, and it is the same residual risk the other 48 documents already carry. |

---

## 12. Owner decisions required before S1

| Id | Decision | Recommendation |
| --- | --- | --- |
| D1 | Accept the as-of composition (a reconstruction from official artifacts, explicitly labeled) as a releasable source kind. | Accept. The alternative is an indefinite block, or an interim exclusion of two P1 laws. |
| D2 | Policy for `conditional`/`contested` units: release marked uncertain (`valid_at_legal_date='unknown'` plus a notice), or block the whole document. | Allow only per-block with explicit reviewer listing in `release_with_uncertainty`. Expected for a72. |
| D3 | `temporal_status_policy` for the 48 single-artifact documents: keep `masked` (today: every citation "verifique vigencia"), or `basis_gated` (BOE-consolidation basis gives "versión vigente" within its window). | Ship S6 with `masked` as the default. Switch to `basis_gated` only after the S1 inventory shows no SA-1 exposure and the consultation evaluation is rerun. This is a corpus-wide behavior change. |
| D4 | Identity and role of the legal reviewer, and where review rationale documents live. | A named person or role recorded in the manifest. Rationale referenced to OPERATIONS anchors or a new review note per law. |
| D5 | Branch integration: the ingestion and consultation histories are unrelated. Decide where the shared corpus-layer patch and `ingestion/telemetry.py` live. | Release side on `impl/corpus-ingestion`; agent side on the serving consultation branch; shared fixture as the contract; port `telemetry.py` verbatim to the ingestion branch. |
| D6 | First release legal date L. | 2026-11-02 (stated cutoff), with rebuilds on 2026-12-01 and 2027-01-01. |
| D7 | Replace the existing LGSS-specific hard-coded a72 notice hash in `boe_context.editorial_notes` with manifest-declared `reviewed_inline_notices`. | Do it in S3 (behavior-identical for all current documents). It removes the only law-specific runtime rule. |

---

## 13. Issues noticed outside this scope (flagged, not changed)

1. `services/v3/verification/temporal_checker.py` (legacy engine) uses `datetime.date.today()` instead of the consultation legal date. This is unrelated to the agent path.
2. The ingestion branch lacks the ingestion telemetry the project rules require. The consultation branch lacks the snapshot, integrity and release modules. The two histories need an explicit integration plan beyond this ADR (D5 covers only what this change needs).
3. SA-1 exposure of the 48 already-approved documents is unknown until S1 runs. BOE-A-1985-17303 carries a future whole-decree repeal (2027-05-25). That is a document-level `effective_to`, not future wording. It should be recorded in `temporal` and must not trigger SA-1.
