# Query Mapping: Factor Types to paper-search API Parameters

This reference table maps litreview factor types to the corresponding parameters for each paper-search MCP API endpoint.

---

## Factor Type → API Parameter Mapping

| Factor Type  | `search_semantic`              | `search_openalex`               | `snowball_search`         | Notes                                      |
|--------------|-------------------------------|----------------------------------|---------------------------|--------------------------------------------|
| `query`      | `query=value`                 | `query=value`                   | N/A                       | Primary search string; use for both APIs   |
| `keyword`    | Append to `query`             | Append to `query`               | N/A                       | Combine with `query` using AND/OR          |
| `author`     | `author=value`                | `author.display_name=value`     | N/A                       | May need to search by author ID in OA      |
| `venue`      | `venue=value`                 | `primary_location.source.display_name=value` | N/A      | Conference or journal name                 |
| `field`      | `fields_of_study=value`       | `primary_topic.display_name=value` | N/A                    | Academic field classification              |
| `year_range` | `year=start-end`              | `publication_year=start-end`    | N/A                       | Format: "2020-2024" → "2020:2024" in OA    |
| `seed_paper` | N/A                           | N/A                             | `paper_id=doi_or_id`      | Use for forward/backward/both citation tracking |
| `method`     | Append to `query`             | Append to `query`               | N/A                       | Treat as conceptual keyword                |
| `exclude`    | Filter post-retrieval         | Filter post-retrieval           | Filter post-retrieval     | Remove matching papers from results        |
| `pub_type`   | `publicationTypes=<s2_type>`  | `type=<oa_type>`                | N/A                       | See type mapping table below               |
| `open_access`| `openAccessPdf` (boolean)     | `is_oa=true`                    | N/A                       | Filter for freely available PDFs           |
| `citation_min`| `minCitationCount=N`         | `cited_by_count:>N-1`           | N/A                       | OA uses > operator, subtract 1             |
| `institution`| ❌ NOT SUPPORTED               | `authorships.institutions.id=<oa_id>` | N/A              | OA only. Resolve ID via `/institutions?search=` |
| `language`   | ❌ NOT SUPPORTED               | `language=<iso_code>`           | N/A                       | OA only. ISO 639-1 code (e.g. "en", "zh") |
| `funder`     | ❌ NOT SUPPORTED               | `awards.funder=<oa_id>`        | N/A                       | OA only. Resolve ID via `/funders?search=` |

---

## pub_type Cross-API Mapping

When a `pub_type` filter is active, translate the user-facing label to the API-specific value:

| User-facing label     | `search_semantic` value | `search_openalex` value |
|-----------------------|-------------------------|--------------------------|
| Journal article       | `JournalArticle`        | `article`                |
| Conference paper      | `Conference`            | `article`                |
| Review / survey       | `Review`                | `article` (+ keyword)   |
| Book                  | `Book`                  | `book`                   |
| Book chapter          | —                       | `book-chapter`           |
| Preprint              | —                       | `preprint`               |
| Dataset               | `Dataset`               | `dataset`                |
| Dissertation / thesis | —                       | `dissertation`           |
| Clinical trial        | `ClinicalTrial`         | —                        |
| Meta-analysis         | `MetaAnalysis`          | —                        |

> When a type is unsupported by one API (marked —), omit it from that API's query and inform the user.

---

## API-Limited Filter Warning

When `institution`, `language`, or `funder` filters are active, the agent MUST:
1. Include the filter in the OpenAlex query
2. Omit the filter from the Semantic Scholar query
3. Inform the user: "⚠️ [filter] 仅 OpenAlex 支持，Semantic Scholar 结果未应用此过滤。"

---

## API-Specific Details

### search_semantic (Semantic Scholar)

```
search_semantic(
  query="<query>",                        # Single primary keyword (do NOT combine multiple)
  author="<author_name>",                 # Optional: filter by author
  venue="<venue_name>",                   # Optional: filter by venue
  fields_of_study=["<field>"],            # Optional: list of fields
  year="<start>-<end>",                  # Optional: e.g. "2020-2024"
  publicationTypes="<type>",             # Optional: e.g. "JournalArticle", "Review"
  openAccessPdf=true,                    # Optional: only open-access papers
  minCitationCount=<N>,                  # Optional: minimum citations
  limit=50                                # Results per call (max 100)
)
```

- Supports rich keyword search with boolean operators
- `fields_of_study` accepts Semantic Scholar taxonomy values (e.g., "Computer Science", "Medicine")
- `year` is a range string: "2020-2024"
- Does NOT support: `institution`, `language`, `funder` filters

### search_openalex (OpenAlex)

```
search_openalex(
  query="<query>",                                 # Single primary keyword (do NOT combine multiple)
  publication_year="<start>-<end>",               # Optional: year range
  primary_topic_display_name="<field>",           # Optional: topic/field filter
  primary_location_source_display_name="<venue>", # Optional: journal/conference
  authorships_author_display_name="<author>",     # Optional: author name
  type="<oa_type>",                               # Optional: e.g. "article", "review", "book"
  is_oa=true,                                      # Optional: only open-access papers
  cited_by_count=">N",                            # Optional: minimum citations (use > operator)
  authorships_institutions_id="<oa_id>",          # Optional: institution filter (resolve ID first)
  language="<iso_code>",                           # Optional: e.g. "en", "zh"
  awards_funder="<oa_id>",                         # Optional: funder filter (resolve ID first)
  limit=50                                         # Results per call
)
```

- OpenAlex has the most extensive filtering options
- Supports all filter types including `institution`, `language`, `funder` (which S2 does not)

### snowball_search (Citation Expansion)

```
snowball_search(
  paper_id="<doi_or_semantic_id>",  # Seed paper identifier
  direction="both",                  # "forward", "backward", or "both"
  limit=30                           # Max papers to retrieve
)
```

- Use when `seed_paper` factors are present
- `direction="forward"` → papers that cite the seed (citing)
- `direction="backward"` → papers cited by the seed (references)
- `direction="both"` → both directions combined

---

## Query Construction Examples

### Example 1: Simple Concept Search

**Factors:**
- `query`: "retrieval augmented generation"
- `field`: "computer science"
- `year_range`: "2021-2024"

**Semantic Scholar call:**
```
search_semantic(query="retrieval augmented generation", fields_of_study=["Computer Science"], year="2021-2024", limit=50)
```

**OpenAlex call:**
```
search_openalex(query="retrieval augmented generation", primary_topic_display_name="computer science", publication_year="2021-2024", limit=50)
```

---

### Example 2: Author + Venue Focus

**Factors:**
- `query`: "diffusion models"
- `author`: "Sohl-Dickstein"
- `venue`: "ICML"

**Semantic Scholar call:**
```
search_semantic(query="diffusion models", author="Sohl-Dickstein", venue="ICML", limit=50)
```

**OpenAlex call:**
```
search_openalex(query="diffusion models", authorships_author_display_name="Sohl-Dickstein", primary_location_source_display_name="ICML", limit=50)
```

---

### Example 3: Seed Paper with Snowball

**Factors:**
- `query`: "protein structure prediction"
- `seed_paper`: "10.1038/s41586-021-03819-2"  (AlphaFold2 DOI)
- `year_range`: "2021-2024"

**Calls:**
```
search_semantic(query="protein structure prediction", year="2021-2024", limit=50)
snowball_search(paper_id="10.1038/s41586-021-03819-2", direction="both", limit=30)
```

---

### Example 4: Multiple Primary Factors — Round-by-Round

**Factors:**
- `query`: "knowledge graph"
- `method`: "graph neural network"
- `keyword`: "entity alignment"
- `field`: "computer science"

**⚠️ Do NOT combine into one query.** Each primary factor gets its own search round:

**Round 1 — query "knowledge graph":**
```
search_semantic(query="knowledge graph", fields_of_study=["Computer Science"], limit=50)
search_openalex(query="knowledge graph", primary_topic_display_name="computer science", limit=50)
```

**Round 2 — method "graph neural network":**
```
search_semantic(query="graph neural network", fields_of_study=["Computer Science"], limit=50)
search_openalex(query="graph neural network", primary_topic_display_name="computer science", limit=50)
```

**Round 3 — keyword "entity alignment":**
```
search_semantic(query="entity alignment", fields_of_study=["Computer Science"], limit=50)
search_openalex(query="entity alignment", primary_topic_display_name="computer science", limit=50)
```

Results from all rounds are combined and deduplicated via `lr_search_ingest`.

---

## Result Field Mapping

When processing results, extract and normalize these fields for `lr_dedup` and `lr_score`:

| litreview field   | Semantic Scholar field       | OpenAlex field                     |
|-------------------|------------------------------|------------------------------------|
| `title`           | `title`                      | `title`                            |
| `authors`         | `authors[].name`             | `authorships[].author.display_name`|
| `year`            | `year`                       | `publication_year`                 |
| `venue`           | `venue.name`                 | `primary_location.source.display_name` |
| `doi`             | `externalIds.DOI`            | `doi`                              |
| `abstract`        | `abstract`                   | `abstract_inverted_index` (reconstruct) |
| `citation_count`  | `citationCount`              | `cited_by_count`                   |
| `semantic_id`     | `paperId`                    | N/A                                |
| `openalex_id`     | N/A                          | `id`                               |

Use DOI as the primary deduplication key when available. Fall back to normalized title + year + first author.
