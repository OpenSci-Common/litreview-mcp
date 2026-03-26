# Search Factor Reference — Agent Technical Guide

> **Purpose**: Technical reference for AI agents executing `search` and `search-factor-management` skills. This document defines how to interpret, validate, combine, and translate search factors into API queries.
> **When to read**: Before composing any search query or managing user's search factors.

---

## 1. Factor Type Registry

### 1.1 Primary factors (can independently trigger a search)

#### query
- **Role**: primary (keyword-type — each gets its own search round; see Rule 2)
- **Sub-types**: topic | concept (stored in `sub_type` field; APIs treat all identically). Note: `method` is a separate first-class primary factor type, not a sub_type of query.
- **Value format**: Free-text string, typically 1-5 words
- **API translation**:
  - S2: `query={value}` — matches title + abstract
  - OA: `search={value}` — matches title + abstract + fulltext
- **Validation**: Non-empty string. Warn user if >8 words (overly specific queries return few results).
- **Multiple query factors**: Each runs in its own search round; results are merged and deduplicated. Papers appearing in multiple rounds are ranked higher by relevance score.
- **User explanation template**: "This keyword will be searched against paper titles and abstracts. Papers containing this term (or closely related terms) will be returned."

#### keyword
- **Role**: primary (keyword-type — each gets its own search round; see Rule 2)
- **Value format**: Free-text string, typically 1-3 words
- **API translation**: Same as `query` — maps to `query={value}` (S2) / `search={value}` (OA)
- **Distinction from query**: Semantic only. Use `keyword` for supplementary terms that refine the search (e.g., "few-shot learning") vs. `query` for core topic concepts. APIs treat them identically.
- **Search behavior**: Each keyword factor gets its own search round, just like query factors. Do NOT append keywords to a query factor's value.
- **User explanation template**: "This supplementary keyword will be searched in paper titles and abstracts, in its own dedicated search round."

#### method
- **Role**: primary (keyword-type — each gets its own search round; see Rule 2)
- **Value format**: Technique or methodology name (e.g., "retrieval-augmented generation", "contrastive learning")
- **API translation**: Same as `query` — maps to `query={value}` (S2) / `search={value}` (OA)
- **Distinction from query**: Semantic only. Use `method` for specific techniques/algorithms vs. `query` for broader topics. APIs treat them identically.
- **Search behavior**: Each method factor gets its own search round. Do NOT append methods to a query factor's value.
- **User explanation template**: "This will search for papers about this specific technique or methodology, in its own dedicated search round."

#### author
- **Role**: primary (axis-type — can co-attach to keyword rounds as intersection param; see Rule 2)
- **Value format**: Person name string (e.g., "Yoshua Bengio")
- **Requires ID resolution**: YES — must resolve name to API entity ID before searching.
- **API translation** (two-step):
  - S2: Step 1: `GET /author/search?query={value}` → extract `authorId` from top result. Step 2: `GET /author/{authorId}/papers?fields=...`
  - OA: Step 1: `GET /authors?search={value}` → extract `id` from top result. Step 2: `GET /works?filter=authorships.author.id:{id}`
- **ID caching**: After first resolution, store IDs in factor's `api_ids` field. Skip resolution on subsequent searches.
- **Disambiguation**: If name resolution returns multiple candidates, present top 3-5 to user with affiliations and paper counts. Let user select the correct person.
- **Validation**: Non-empty string. If `api_ids` is empty, must resolve before searching.
- **User explanation template**: "This will find all papers authored by this researcher. The system first identifies the researcher in academic databases, then retrieves their publication list."

#### venue
- **Role**: primary (axis-type — can co-attach to keyword rounds as intersection param; see Rule 2)
- **Value format**: Journal or conference name (e.g., "NeurIPS", "Nature Machine Intelligence")
- **Requires ID resolution**: Only for OpenAlex (S2 accepts venue name directly).
- **API translation**:
  - S2: `venue={value}` as filter parameter on paper search
  - OA: Step 1: `GET /sources?search={value}` → extract `id`. Step 2: `filter=primary_location.source.id:{id}`
- **ID caching**: Cache OA source ID in `api_ids.openalex_id`.
- **Validation**: Non-empty string. Warn if venue name is ambiguous (e.g., "Nature" matches many sub-journals).
- **User explanation template**: "This will find papers published in this specific journal or conference. You can use it alone to browse a venue's publications, or combine with keywords to search within it."

#### seed_paper
- **Role**: primary (seed-type — always uses its own citation-API round; see Rule 6)
- **Value format**: Paper title (display) + `paper_id` (internal reference to literature.json)
- **Requires**: Paper must exist in literature.json with status `in_library`.
- **Does NOT use keyword search**: Uses citation/recommendation APIs instead.
- **Three operation modes** (agent must ask user which mode):
  - `backward`: What does this paper cite? → `GET /paper/{s2_id}/references` (S2) or read `referenced_works` field (OA)
  - `forward`: Who cites this paper? → `GET /paper/{s2_id}/citations` (S2) or `filter=cites:{oa_id}` (OA)
  - `recommend`: Similar papers → `POST /recommendations/v1/papers` with positive_paper_ids (S2) or read `related_works` (OA)
- **Multi-seed**: For recommend mode, multiple seed_paper factors are combined as positive examples to the Recommendations API.
- **Combining with filters**: After retrieving candidate list via citation/recommendation, apply filter factors (year_range, field, etc.) as post-filters on the result set.
- **Validation**: `paper_id` must exist in literature.json. `external_ids` must contain at least one API-resolvable ID.
- **User explanation template**: "Instead of keyword search, this uses your selected paper as a starting point to trace its citation network or find similar papers. This is the best way to discover papers you wouldn't find through keywords alone."

---

### 1.2 Filter factors (must combine with at least one primary)

#### field
- **Role**: filter
- **Value format**: Academic discipline name (e.g., "Computer Science", "Medicine")
- **API translation**:
  - S2: `fieldsOfStudy={value}` — flat list. Known values: Computer Science, Medicine, Physics, Mathematics, Biology, Chemistry, Engineering, Economics, Business, Political Science, Psychology, Sociology, Geography, History, Art, Philosophy, Environmental Science, Materials Science, Geology, Agricultural and Food Sciences, Education, Law, Linguistics
  - OA: `primary_topic_display_name={value}` — the MCP tool handles topic resolution internally.
- **Multiple fields**: OR logic. `fieldsOfStudy=Computer Science,Linguistics` returns papers in either field.
- **User explanation template**: "This restricts results to papers classified under this academic discipline. Useful when a keyword has different meanings in different fields."

#### pub_type
- **Role**: filter
- **Value format**: Publication type identifier
- **API translation**:
  - S2: `publicationTypes={s2_type}`. Values: JournalArticle, Conference, Review, Book, Dataset, ClinicalTrial, CaseReport, MetaAnalysis, Study, Editorial, LettersAndComments
  - OA: `type={oa_type}`. Values: article, book, book-chapter, dataset, dissertation, editorial, erratum, letter, paratext, peer-review, preprint, report, standard, supplementary-materials
- **Cross-API mapping table** (agent must translate):

| User-facing label | S2 value | OA value |
|---|---|---|
| Journal article | JournalArticle | article |
| Conference paper | Conference | article (no separate type) |
| Review / survey | Review | article (filter by keyword) |
| Book | Book | book |
| Book chapter | — | book-chapter |
| Preprint | — | preprint |
| Dataset | Dataset | dataset |
| Dissertation / thesis | — | dissertation |
| Clinical trial | ClinicalTrial | — |
| Meta-analysis | MetaAnalysis | — |

- **User explanation template**: "This filters by publication format. Tip: searching for Reviews first is a great way to quickly understand a new field."

#### year_range
- **Role**: filter
- **Value format**: String in format "YYYY-YYYY", "YYYY-" (open-ended), or "YYYY" (single year)
- **API translation**:
  - S2: `year={value}` — accepts "2020-2024", "2023-", "2024"
  - OA: `publication_year={value}` — accepts "2020-2024", ">2022", "2024"
- **Parsing rules**: Agent must parse user natural language into format:
  - "papers from the last 3 years" → compute current_year-3 to current_year → "2023-2026"
  - "recent papers" → default to "last 3 years" and confirm with user
  - "since 2020" → "2020-"
  - "2023 only" → "2023"
- **User explanation template**: "This limits results to papers published within the specified time window."

#### institution
- **Role**: filter
- **API support**: OpenAlex ONLY. S2 does not support institution filtering.
- **Value format**: Institution name (e.g., "MIT", "Tsinghua University")
- **Requires ID resolution**: Yes, via OA `/institutions?search={value}`.
- **API translation**:
  - S2: NOT SUPPORTED — do not include in S2 query. Agent MUST inform user.
  - OA: `authorships_institutions_id={oa_institution_id}`
- **Warning message to user** (MUST display when this filter is active):
  > "Note: institution filtering is only supported by OpenAlex. Semantic Scholar results will not be filtered by institution."
- **User explanation template**: "This filters for papers where at least one author is affiliated with this institution. Note: this only works with one of our two data sources (OpenAlex)."

#### open_access
- **Role**: filter
- **Value format**: Boolean (true/false)
- **API translation**:
  - S2: `openAccessPdf` parameter (boolean)
  - OA: `is_oa=true`
- **User explanation template**: "When enabled, only papers with freely available full-text PDFs will be returned. Useful when you need to download and analyze the full paper."

#### citation_min
- **Role**: filter
- **Value format**: Integer (minimum citation count)
- **API translation**:
  - S2: `minCitationCount={value}`
  - OA: `cited_by_count=">N"` where N = user's minimum value minus 1 (OA uses `>` not `>=`, so subtract 1 from the user's input)
- **Side effect warning** (MUST display when value > 0):
  > "Note: minimum citation count filtering will exclude recently published papers that haven't had time to accumulate citations. Consider running a separate search without this filter to catch important new work."
- **User explanation template**: "This sets a minimum number of times a paper has been cited by other papers. Higher values return more established/influential works, but will miss recent publications."

#### funder
- **Role**: filter
- **API support**: OpenAlex ONLY.
- **Value format**: Funding agency name (e.g., "National Science Foundation", "ERC")
- **Requires ID resolution**: Yes, via OA `/funders?search={value}`.
- **API translation**:
  - S2: NOT SUPPORTED
  - OA: `awards_funder={oa_funder_id}`
- **Warning message to user**: Same pattern as institution — inform user this only works on OpenAlex.
- **User explanation template**: "This filters for papers funded by a specific agency. Useful for tracking research output from particular funding programs. Note: only supported by OpenAlex."

#### language
- **Role**: filter
- **API support**: OpenAlex ONLY.
- **Value format**: ISO 639-1 language code (e.g., "en", "zh", "de", "fr")
- **API translation**:
  - S2: NOT SUPPORTED
  - OA: `language={value}`
- **Warning message to user**: Same pattern as institution.
- **User explanation template**: "This filters by the language of the paper. Currently the system focuses on English literature, but this allows filtering for other languages when needed. Note: only supported by OpenAlex."

---

## 2. Query Composition Rules

When composing a search from multiple active factors, follow these rules strictly:

### Rule 1: At least one primary factor required
If no primary factor (query/keyword/method/author/venue/seed_paper) is active, DO NOT execute a search. Ask the user to add or activate a search subject.

### Rule 2: Multiple primary factors → one keyword-type per round, then merge

Primary factors fall into two sub-categories with different combination rules:

**Keyword-type primaries** (`query`, `keyword`, `method`): NEVER combine multiple keyword-type factors into a single API query — combining keywords narrows results to near-zero. Each keyword-type factor gets its own search round.

**Axis-type primaries** (`author`, `venue`): These naturally narrow results and CAN co-exist with a keyword-type factor in the same round as additional API parameters. They act as intersection filters (e.g., "papers about X by author Y at venue Z").

**`seed_paper`**: Always runs in its own round via citation/recommendation APIs (Rule 6).

Combination examples:
- Two query factors → round 1 with query A, round 2 with query B, merge results.
- query + author → single round: `search(query="X", author="Y")` — this is an intersection, not separate rounds.
- query + author + venue → single round: `search(query="X", author="Y", venue="Z")`.
- Two authors (no query) → round 1 with author A, round 2 with author B, merge results.
- query A + query B + author → round 1: `search(query="A", author="Y")`, round 2: `search(query="B", author="Y")`, merge.
- All filter factors apply to every round.

### Rule 3: All filters → AND
All active filter factors apply simultaneously. A paper must satisfy ALL active filters to appear in results.

### Rule 4: Same-type filters → OR
Two field factors ("Computer Science" + "Linguistics"): paper must be in EITHER field.
Two pub_type factors ("Review" + "Conference"): paper must be EITHER type.

### Rule 5: API-limited filters require transparency
When institution, funder, or language filters are active, the agent MUST:
1. Include the filter in the OpenAlex query
2. Omit the filter from the Semantic Scholar query
3. Inform the user which filters are not applied to which API
4. Format: "This search uses [N] factors. [Factor X] and [Factor Y] only apply to OpenAlex results. Semantic Scholar results are not filtered by these conditions."

### Rule 6: seed_paper uses different API path
seed_paper does not use keyword search endpoints. Workflow:
1. Determine operation mode (backward/forward/recommend) — ask user if not specified
2. Call citation/recommendation API
3. Get raw candidate list
4. Apply any active filter factors as post-filters (year_range, field, etc.)
5. Score and rank with metric registry
6. Present to user

---

## 3. User-Facing Confirmation Template

Before executing any search, present the search plan to the user. Use the same language as the skill prompts (Chinese):

```
检索计划（共 N 轮）：
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
第 1 轮: [type] "[value]"            → [API parameter]
第 2 轮: [type] "[value]"            → [API parameter]

过滤条件（应用于所有轮次）:
  • [type]: [value]                  → [API parameter]
  • [type]: [value]                  → [API parameter]
  • [type]: [value] ⚠ 仅 OpenAlex   → [API parameter]

数据源: Semantic Scholar, OpenAlex
限制: [filter X] 仅 OpenAlex 支持，Semantic Scholar 结果不受此过滤。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
确认执行？（确认 / 调整 / 取消）
```

---

## 4. Factor Management Operations

The `search-factor-management` skill handles these operations:

### Add factor
1. User specifies type + value (or describes in natural language → agent extracts type + value)
2. Agent validates: correct type? non-empty value? no duplicate in library?
3. For types requiring ID resolution (author, venue, institution, funder): resolve immediately, cache in `api_ids`
4. If resolution returns ambiguous results: present candidates to user for selection
5. Write to search_factors.json with `active: true`
6. Explain to user what this factor does using the explanation templates above

### Activate / deactivate
1. Set `active` field to true/false
2. Inform user: "Factor [X] is now [active/inactive]. It [will/will not] be included in your next search."

### Promote from content factor
1. User selects a content factor from content_factors.json
2. Agent creates corresponding search factor with `provenance: "promoted_from_content"`
3. If matching content factors exist across multiple papers, agent reports: "This author appears in [N] papers in your library."
4. Mark all matching content factors as `promoted: true`

### Delete factor
1. Remove from search_factors.json
2. Update any content factors with `promoted: true` back to `promoted: false`
3. Historical search sessions referencing this factor are NOT modified (they store factor snapshots)

### List active factors
Present current active factors grouped by role:

```
Active search factors:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
主检索因子:
  关键词类（每个单独搜索一轮）:
    1. [query/topic] "RAG optimization"
    2. [method] "dense passage retrieval"
  轴类（附加到每轮关键词搜索中）:
    3. [author] "Patrick Lewis"
  种子论文类（独立轮次，使用引文/推荐 API）:
    4. [seed_paper] "Attention Is All You Need"

过滤因子（应用于所有搜索轮次）:
  5. [field] Computer Science
  6. [year_range] 2022-2026
  7. [open_access] true

停用（保留但不参与搜索）:
  8. [citation_min] 50
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## 5. Error Handling

| Situation | Agent action |
|---|---|
| No primary factor active | Do not search. Ask user to add or activate a search subject. |
| Author name resolves to 0 results | Inform user. Suggest checking spelling or trying alternate name forms. |
| Author name resolves to multiple candidates | Present top candidates with affiliations. Let user choose. |
| API rate limit hit | Wait and retry with exponential backoff (max 3 retries). Inform user if persistent. |
| One API fails but other succeeds | Present results from working API. Note that results are partial. |
| Filter not supported by one API | Apply filter only to supporting API. Clearly inform user. |
| Search returns 0 results | Suggest: broaden time range, remove filters one by one, try synonym keywords. |
| Search returns >500 results | Suggest: add filters to narrow down, increase citation_min, narrow time range. |
