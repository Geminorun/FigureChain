# CBDB Import Design

Date: 2026-06-04

## Summary

This spec defines the first `figure-data` milestone for FigureChain: import the local CBDB SQLite snapshot into PostgreSQL as a durable, searchable data foundation.

The goal is not to build the final person-chain product yet. This phase creates the local data layer that later phases will use for person disambiguation, relationship review, Neo4j graph projection, and verified face-to-face encounter chains.

## Scope

### In Scope

- Use the local CBDB SQLite snapshot at `figure-data/cbdb_20260530.sqlite3`.
- Use the existing PostgreSQL `figure` database through `DATABASE_URL` in `.env`.
- Create and manage tables only inside the `figure_data` schema.
- Import CBDB people, aliases, dynasties, social relationship candidates, kinship candidates, office postings, and text/work codes.
- Import source references only when they are referenced by imported relationship, kinship, or office posting rows.
- Preserve the original CBDB row in `raw_cbdb jsonb` for imported data.
- Support idempotent upsert import runs.
- Generate local person IDs instead of using CBDB IDs as primary keys.
- Store CBDB IDs in `person_external_ids`.
- Preserve one local person per CBDB `c_personid` in the first version.
- Pre-create merge/disambiguation tables for future use.
- Support lightweight person search by traditional Chinese, simplified Chinese, aliases, romanized names, and partial matches.
- Validate imports with row count checks and sample person queries.

### Out of Scope

- Next.js frontend.
- FastAPI product API.
- Neo4j graph projection.
- Shortest person-chain search.
- Verified `encounters`.
- RAG, embeddings, or `pgvector` tables.
- ctext, Kanseki, Wikidata, or other source imports.
- Address-based co-presence inference.
- Automatic person merge.
- Treating CBDB relationships as verified face-to-face meetings.

## Project Structure

The repository should eventually contain two related projects:

- `figure-data`: data import, normalization, search support, candidate relationship generation.
- `figure-chain`: the future product application, including FastAPI, Neo4j, and Next.js.

This phase only implements `figure-data`.

## Technology

- Python project manager: `uv`
- CLI framework: Typer or Click
- Database access: SQLAlchemy 2.x
- Database migrations: Alembic
- PostgreSQL driver: psycopg 3
- API/data validation models: Pydantic
- Chinese conversion: OpenCC
- Database: existing PostgreSQL `figure`
- Schema: `figure_data`

`pgvector` is already available in the database, but this phase does not create vector tables or embedding jobs.

## Database Boundary

The import project must only create and modify objects under:

```text
figure_data.*
```

It must not create or modify tables in `public` or any future product schema.

The actual PostgreSQL URL must be stored in `.env` as:

```text
DATABASE_URL=<local PostgreSQL connection string>
```

The full connection string must not be committed.

## Data Model

### Import Tracking

`figure_data.import_batches`

Tracks every import run:

- ID
- snapshot name
- SQLite filename
- SQLite SHA-256
- started/finished timestamps
- status
- rows read
- rows inserted
- rows updated
- rows skipped
- error count
- error summary

### People

`figure_data.persons`

Local canonical person records. Uses a local UUID or ULID primary key.

Important normalized fields:

- `id`
- `primary_name_zh_hant`
- `primary_name_zh_hans`
- `primary_name_romanized`
- `search_name`
- `surname_zh_hant`
- `surname_zh_hans`
- `given_name_zh_hant`
- `given_name_zh_hans`
- `birth_year`
- `death_year`
- `index_year`
- `floruit_start_year`
- `floruit_end_year`
- `dynasty_code`
- `is_female`
- `notes`
- `raw_cbdb`
- `source_row_hash`
- import timestamps

CBDB unknown or placeholder values such as `0`, `-9999`, and empty strings should be normalized to `null` where the target field represents a real date or value. The original value remains available in `raw_cbdb`.

`figure_data.person_external_ids`

Stores source-specific IDs:

- local person ID
- source name, starting with `cbdb`
- external ID, such as CBDB `c_personid`
- source row hash

Future sources can add Wikidata QIDs or internal IDs without changing the person primary key.

`figure_data.person_aliases`

Imports `ALTNAME_DATA` and `ALTNAME_CODES`:

- local person ID
- alias traditional Chinese
- alias simplified Chinese
- alias romanized
- search name
- alias type code
- alias type labels
- source reference fields
- raw CBDB row
- source row hash

### Codes And Sources

`figure_data.dynasties`

Imports `DYNASTIES`.

`figure_data.source_works`

Imports all `TEXT_CODES` rows as a work/source dictionary.

`figure_data.source_refs`

Stores source references that are actually used by imported relationship, kinship, or office posting rows:

- source work ID
- source table
- source row hash or imported row ID
- pages
- notes

This phase does not import all `BIOG_SOURCE_DATA` rows.

### Social Relationship Candidates

`figure_data.association_codes`

Imports `ASSOC_CODES`, `ASSOC_TYPES`, and `ASSOC_CODE_TYPE_REL` enough to preserve:

- association code
- Chinese description
- English description
- role type
- association type codes
- association type labels
- examples
- raw CBDB rows

`figure_data.relationship_candidates`

Imports all `ASSOC_DATA` rows as candidates, not verified encounters.

Important fields:

- local person A ID
- local person B ID
- CBDB person IDs for traceability
- association code
- association label
- first year
- last year
- source work ID
- pages
- notes
- candidate strength
- candidate basis
- candidate status
- raw CBDB row
- source row hash

### Kinship Candidates

`figure_data.kinship_codes`

Imports `KINSHIP_CODES`.

`figure_data.kinship_candidates`

Imports all `KIN_DATA` rows as candidates or background kinship facts.

Important fields:

- local person A ID
- local person B ID
- kinship code
- kinship labels
- simplified kinship path
- upstep/downstep/marstep
- source work ID
- pages
- notes
- candidate strength
- candidate basis
- candidate status
- raw CBDB row
- source row hash

### Office Postings

`figure_data.office_codes`

Imports office and appointment code tables required to understand `POSTED_TO_OFFICE_DATA`.

`figure_data.office_postings`

Imports `POSTED_TO_OFFICE_DATA`.

Office postings are background data in this phase. They do not generate relationship candidates or encounter edges yet.

### Merge And Identity Tables

`figure_data.person_merge_candidates`

Reserved for future possible duplicate-person suggestions.

`figure_data.person_identity_links`

Reserved for future confirmed identity links across CBDB, Wikidata, and local people.

The first phase does not automatically merge people. One CBDB `c_personid` produces one local `persons` row.

## Candidate Classification

CBDB relationships are not verified face-to-face encounters. They are imported as candidates and classified for later review.

### Candidate Strength

Allowed values:

- `high`
- `medium`
- `low`
- `background`
- `not_applicable`

### Candidate Basis

Allowed values:

- `direct_interaction_likely`
- `co_presence_likely`
- `family_close`
- `family_distant`
- `textual_or_indirect`
- `unknown`

### Candidate Status

Allowed values:

- `imported`
- `needs_review`
- `promoted_to_encounter`
- `rejected`

### ASSOC_DATA Initial Rules

High-value candidates:

- Visited or was visited.
- Accompanied or was accompanied.
- Discussed scholarship.
- Followed/traveled with.
- Knew.
- Arrested or was arrested by.
- Tried or was tried by.
- Fought together.
- Student, disciple, menren.
- Retainer, staff member, adviser.

Medium-value candidates:

- Colleagues.
- Same club or association.
- Same school/class.
- Same examination setting.
- Recommendation.
- Impeachment.
- Opposition/attack.
- Political support.
- Military opposition.

Low or background:

- Same hometown.
- Same intellectual school.
- Same topic.
- Shared group without a concrete contact event.

Not applicable to encounter chains:

- Prefaces, postfaces, epitaphs, biographies.
- Letters, poems, gifted writings.
- Praise, criticism of works, literary style imitation.
- Intellectual transmission without personal contact.
- Death-related ritual writings.

### KIN_DATA Initial Rules

High-value candidates:

- Parents and children.
- Spouses.
- Siblings.
- Adoptive parents.
- Step-parents.

Medium-value candidates:

- Parents-in-law.
- Children-in-law.
- Close in-laws.
- Uncles/aunts.
- Grandparents and maternal grandparents.

Background:

- Distant ancestors.
- Lineage members.
- Claimed descendants.
- Remote cousins.
- Many-generation ancestors.

Not applicable:

- Missing data.
- Unknown.
- Not applicable.

Even a `high` candidate is not a verified encounter. It only means the row is a good review target.

## Import Flow

The CLI should expose at least:

```bash
figure-data migrate
figure-data import-cbdb --sqlite figure-data/cbdb_20260530.sqlite3
figure-data validate-cbdb
figure-data search-person "诸葛亮"
```

Import steps:

1. Read `cbdb_20260530.json`.
2. Verify the SQLite file SHA-256.
3. Create an `import_batches` row.
4. Import dynasties, source works, and code tables.
5. Import persons.
6. Import person external IDs.
7. Import aliases and generate traditional/simplified/search fields.
8. Import social relationship candidates.
9. Import kinship candidates.
10. Import office postings.
11. Import source refs used by imported candidates and postings.
12. Record final row counts, skips, errors, elapsed time, and status.

## Upsert Rules

Imports must be repeatable.

- A row already imported from the same source should not be duplicated.
- `source_row_hash` identifies whether imported source content changed.
- If the hash is unchanged, skip updating imported fields.
- If the hash changed, update imported fields.
- Never overwrite future manual/review fields such as review status, local notes, confirmed identity links, or verified encounters.

## Search

First-phase person search should support:

- Exact traditional Chinese match.
- Exact simplified Chinese match.
- Alias match.
- Romanized name match.
- Partial match.

Ranking:

1. Exact primary name match.
2. Exact alias match.
3. Exact romanized match.
4. Prefix or partial primary name match.
5. Prefix or partial alias match.
6. Other partial matches.

Search result fields:

- local person ID
- primary traditional name
- primary simplified name
- romanized name
- birth/death years
- index year
- dynasty
- matching aliases
- external IDs

## Validation

`figure-data validate-cbdb` should check both row counts and sample queries.

Expected approximate row counts from the local snapshot:

- `BIOG_MAIN`: 658,670
- `ALTNAME_DATA`: 207,219
- `ASSOC_DATA`: 188,649
- `KIN_DATA`: 557,265
- `TEXT_CODES`: 61,146
- `POSTED_TO_OFFICE_DATA`: 588,501

Sample person queries:

- `诸葛亮`
- `諸葛亮`
- `Zhuge Liang`
- `司马懿`
- `司馬懿`
- `Sima Yi`
- `司马炎`
- `司馬炎`
- `汪兆铭`
- `汪兆銘`
- `汪精卫`
- `Wang Zhaoming`

Validation should confirm that simplified input can find CBDB's traditional Chinese records.

## Risks And Mitigations

### CBDB Placeholder Values

Risk: CBDB uses values such as `0`, `-9999`, and empty strings for unknown or placeholder data.

Mitigation: Normalize them to `null` in semantic fields and retain the original values in `raw_cbdb`.

### Traditional/Simplified Conversion Errors

Risk: OpenCC conversion may not perfectly preserve names.

Mitigation: Keep CBDB traditional text as the source value. Simplified/search fields are search aids only.

### Relationship Misinterpretation

Risk: CBDB relationships are broader than face-to-face meetings.

Mitigation: Import them only as candidates. Later phases must promote reviewed rows into verified encounters.

### Large Import Size

Risk: Full person, relationship, kinship, and office imports are large enough to expose slow insert/update paths.

Mitigation: Use batched upserts. Use psycopg raw SQL or COPY where SQLAlchemy ORM operations are too slow.

### Reimport Overwriting Human Work

Risk: Future manual review or merge data could be overwritten by imports.

Mitigation: Separate imported fields from manual/review fields. Upserts only update imported fields.

### Duplicate People

Risk: CBDB may contain duplicate, merged, or ambiguous people.

Mitigation: Do not auto-merge in phase one. Preserve local person IDs and add merge/identity tables for future review.

## Success Criteria

The phase is complete when:

- Alembic can create `figure_data` schema and all first-phase tables.
- `figure-data import-cbdb` imports the approved CBDB tables into PostgreSQL.
- Re-running the import does not duplicate rows.
- Validation row counts match the local SQLite snapshot within expected filtering rules.
- Search finds the sample people through simplified Chinese, traditional Chinese, aliases where available, and romanized names.
- No Neo4j, RAG, frontend, or product API work is required for this phase.
