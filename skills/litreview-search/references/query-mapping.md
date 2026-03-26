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
| `seed_paper` | N/A                           | N/A                             | `paper_id=doi_or_id`      | Use for forward/backward citation tracking |
| `exclude`    | Filter post-retrieval         | Filter post-retrieval           | Filter post-retrieval     | Remove matching papers from results        |
| `method`     | Append to `query`             | Append to `query`               | N/A                       | Treat as conceptual keyword                |

---

## API-Specific Details

### search_semantic (Semantic Scholar)

```
search_semantic(
  query="<query> <keyword> <method>",    # Combined keyword string
  author="<author_name>",                 # Optional: filter by author
  venue="<venue_name>",                   # Optional: filter by venue
  fields_of_study=["<field>"],            # Optional: list of fields
  year="<start>-<end>",                  # Optional: e.g. "2020-2024"
  limit=50                                # Results per call (max 100)
)
```

- Supports rich keyword search with boolean operators
- `fields_of_study` accepts Semantic Scholar taxonomy values (e.g., "Computer Science", "Medicine")
- `year` is a range string: "2020-2024"

### search_openalex (OpenAlex)

```
search_openalex(
  query="<query> <keyword> <method>",             # Combined keyword string
  publication_year="<start>-<end>",               # Optional: year range
  primary_topic_display_name="<field>",           # Optional: topic/field filter
  primary_location_source_display_name="<venue>", # Optional: journal/conference
  authorships_author_display_name="<author>",     # Optional: author name
  limit=50                                         # Results per call
)
```

- OpenAlex has extensive filtering; prefer it for field/venue-specific searches
- Supports institution, funder, and open-access filters (not mapped to factors but available manually)

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

### Example 4: Multi-Keyword Combined Query

**Factors:**
- `query`: "knowledge graph"
- `method`: "graph neural network"
- `keyword`: "entity alignment"
- `field`: "computer science"

**Combined query string:** `"knowledge graph graph neural network entity alignment"`

**Semantic Scholar call:**
```
search_semantic(query="knowledge graph graph neural network entity alignment", fields_of_study=["Computer Science"], limit=50)
```

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
