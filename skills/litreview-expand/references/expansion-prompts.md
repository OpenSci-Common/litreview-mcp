# Expansion Prompts: Abstract Analysis for Concept Extraction

This reference provides prompt templates for analyzing paper abstracts to identify new search factors.

---

## Primary Prompt: Concept Extraction from Abstract Batch

Use this prompt when analyzing a batch of abstracts from library papers to propose new search factors.

```
You are a research assistant helping to expand a literature review search.

Below are abstracts from papers already in the literature library, followed by the currently registered search factors.

Your task: identify new concepts, methods, terms, and research directions that appear in these abstracts but are NOT yet captured by the existing search factors. These will become new search factors to expand the literature search.

## Currently Registered Search Factors
<INSERT lr_factor_list() output here>

## Paper Abstracts
<INSERT abstracts here, formatted as:>
[Paper 1] <title> (<year>)
<abstract>

[Paper 2] <title> (<year>)
<abstract>
...

## Instructions
1. Read all abstracts carefully.
2. Identify recurring technical terms, methodologies, datasets, evaluation benchmarks, and sub-fields.
3. Note any concepts that appear in 2 or more abstracts.
4. Identify emerging or frontier topics that may represent new search directions.
5. Classify each new concept by factor type: query, method, field, keyword, venue, author.
6. Ignore concepts already present in the registered factors list.
7. Suggest 5-10 new factors, prioritizing those with highest potential to surface relevant unseen papers.

## Output Format
Return a structured list:
- [type] "term" — rationale (appears in N papers, relevance explanation)

Focus on specificity: prefer "contrastive decoding" over "decoding", "Constitutional AI" over "alignment".
```

---

## Focused Prompt: Single Paper Deep Analysis

Use this when the user asks to expand based on a specific high-relevance paper.

```
You are helping expand a literature review by deeply analyzing a single key paper.

## Paper Metadata
Title: <title>
Authors: <authors>
Year: <year>
Venue: <venue>
Abstract: <abstract>

## Currently Registered Search Factors
<INSERT lr_factor_list() output here>

## Task
Analyze this paper and identify:
1. Core technical contributions and methods — what novel techniques does it introduce?
2. Related work it cites as foundational — what earlier methods does it build on?
3. Benchmarks and datasets it uses — what evaluation setups are standard in this area?
4. Co-authors or research groups active in this field — who are the key contributors?
5. Adjacent research directions it mentions but does not fully address.

## Output
List 3-8 suggested new search factors not already registered:
- [type] "term" — rationale

Prioritize terms specific enough to yield targeted search results.
```

---

## Focused Prompt: Field Frontier Detection

Use this when the user wants to identify emerging trends in a field.

```
You are analyzing recent papers to identify frontier research directions in a specific field.

## Field Context
The user is researching: <user's research topic>
Current year: <current_year>
Recent papers analyzed: <N> papers from <year_range>

## Abstracts (most recent papers first)
<INSERT abstracts here>

## Task
Identify:
1. Methods or techniques that appear to be gaining traction (mentioned as "recent", "novel", "proposed in this work")
2. Problem formulations that seem to be newly standardized
3. Benchmarks or datasets released in the past 2 years
4. Terms that suggest an emerging sub-field branching off from the main topic

## Output
Return in two sections:

### Established but Unregistered Concepts
(well-known in the field, likely productive search terms)
- [type] "term"

### Emerging / Frontier Concepts
(newer terms that may represent the field's current frontier)
- [type] "term" — evidence from abstracts
```

---

## Usage Notes

- Always fetch the current factor list with `lr_factor_list(active_only=true)` before running any prompt, so the model can avoid duplicates.
- For the batch analysis prompt, include 5-15 abstracts. Too few reduces quality; too many may cause the model to miss patterns.
- When running the single-paper prompt, prefer high-score papers (score > 0.8) as seeds, as they are most likely to be central to the field.
- After generating suggestions, always present them to the user for selection rather than auto-registering — the user may have domain knowledge about which terms are productive.
- Concepts from the prompts should be validated by checking if `search_semantic` or `search_openalex` returns meaningful results when used as queries, before committing them as permanent factors.
