# Bug: BM25 keyword search ignores Cyrillic tokens

## Summary

BM25 keyword search in the knowledge-rag-proxy server only indexes Latin/ASCII tokens. Cyrillic (Russian) text is completely invisible to keyword search, even though the text is correctly extracted, chunked, and returned by `krp_get_document`. Semantic search partially compensates, but exact keyword matching on Russian words does not work at all.

## Environment

- KRP server: `uvicorn server.app:app --reload --port 8000`
- Source: `/Users/simens/Hobby/knowledge-rag-proxy/`
- Documents root: contains Russian-language PDFs, DOCX, and Markdown files

## Reproduction

### Document

File: `Резюме/Семен Гринев Евгеньевич.pdf` (3 pages, Russian text)

The document contains the following Russian text (among other content):

```
ФАУ ЦИАМ им. П.И. Баранова
...
Леонид Александрович Бендерский (Начальник сектора 7000-01-01 "Прикладового программирования")
...
Московский авиационный институт (национальный исследовательский университет)
...
Донской государственный технический университет
...
Методы искусственного интеллекта и предиктивная аналитика в проектах дефектоскопии
```

### Steps

1. **Keyword search (BM25 only, `hybrid_alpha=0`) for a Russian word that exists in the document:**

```bash
curl -s -X POST http://localhost:8000/search_knowledge \
  -H "Authorization: Bearer $KRP_BEARER" \
  -H "Content-Type: application/json" \
  -d '{"query": "ЦИАМ", "hybrid_alpha": 0, "max_results": 10}'
```

**Result:** `"result_count": 0` — zero results.

2. **Repeat with other Russian-only queries — all return 0 results:**

| Query | Expected hit | Actual result |
|---|---|---|
| `ЦИАМ` | `Резюме/Семен Гринев Евгеньевич.pdf` | 0 results |
| `Баранова` | same | 0 results |
| `Бендерский` | same | 0 results |
| `Московский авиационный институт` | same | 0 results |
| `Донской государственный технический` | same | 0 results |
| `дефектоскопии` | same | 0 results |
| `архитектор программного обеспечения` | same | 0 results |

3. **Keyword search for Latin/English terms from the SAME document works:**

```bash
curl -s -X POST http://localhost:8000/search_knowledge \
  -H "Authorization: Bearer $KRP_BEARER" \
  -H "Content-Type: application/json" \
  -d '{"query": "Python Docker FastAPI", "hybrid_alpha": 0, "max_results": 10}'
```

**Result:** Returns the document with a valid `bm25_rank`.

4. **`krp_get_document` returns the full text correctly** — so the text is extracted and stored, the problem is specifically in the BM25 search index tokenization, not in document parsing.

5. **Keyword search for Russian words from a Markdown document also fails:**

Searching `Бендерский` or `дефектоскопии` returns 0 — so it's not PDF-specific, it affects all document formats.

However, searching `Wellfound` (Latin, from `report_ru.md`) returns results normally. And searching mixed queries like `интеграционная платформа CAE решателей` returns results — but only because `CAE` is Latin; the Cyrillic words contribute nothing to the BM25 score.

## Root Cause Hypothesis

The BM25 tokenization/analyzer does not split Cyrillic text into searchable tokens. Likely causes:

1. **Tokenizer uses ASCII word boundaries** (`\w+` or similar), which excludes Cyrillic Unicode characters. A regex like `[a-zA-Z0-9]+` would only match Latin words.
2. **BM25 index (likely Qdrant or Elasticsearch) is configured with a default/standard analyzer** instead of a `russian` analyzer, which would require explicit mapping.
3. **Custom tokenizer in the KRP server code** only handles ASCII characters.

## Expected Behavior

Russian text should be tokenized and indexed for BM25 search just like Latin text. Searching for `ЦИАМ` should return documents containing that term.

## What to Investigate

1. Look at the BM25 indexing pipeline in the KRP server code (`/Users/simens/Hobby/knowledge-rag-proxy/`). Find where documents are tokenized for the keyword index.
2. Check the tokenizer/analyzer configuration — is it ASCII-only?
3. If using Qdrant: check the sparse vector configuration and tokenizer settings (`models.TokenizerType`).
4. If using Elasticsearch/OpenSearch: check the analyzer mapping for the text field.
5. Check if there's a custom text normalization step that strips non-ASCII characters.
