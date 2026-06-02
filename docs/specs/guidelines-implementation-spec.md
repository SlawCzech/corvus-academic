# Corvus — guidelines implementation spec

> Feature: load university requirements as RAG context
> for check_requirements and generate_review nodes.
> This spec covers file placement, loading mechanism,
> and node integration.

---

## Step 1 — Add guidelines files to repo

Place both files in:

```
agent/prompts/guidelines/
├── university_requirements_bachelor.md
└── university_requirements_master_article.md
```

These files are already generated — copy from docs/specs/:
- `university_requirements_bachelor.md`
- `university_requirements_master_article.md`

---

## Step 2 — Guidelines loader

Create `agent/src/application/guidelines.py`:

```python
"""Guidelines loader — loads university requirements by thesis type."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from corvus.domain.analysis import ThesisType

_GUIDELINES_DIR = Path(__file__).parent.parent.parent / "prompts" / "guidelines"

_GUIDELINES_FILES: dict[str, str] = {
    ThesisType.BACHELOR:        "university_requirements_bachelor.md",
    ThesisType.MASTER_ARTICLE:  "university_requirements_master_article.md",
}


@lru_cache(maxsize=4)
def load_guidelines(thesis_type: str) -> str:
    """Load university requirements for the given thesis type.

    Cached after first load — file is read once per process lifetime.
    Raises FileNotFoundError if the guidelines file does not exist.
    """
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")

    path = _GUIDELINES_DIR / filename
    return path.read_text(encoding="utf-8")


def get_guidelines_path(thesis_type: str) -> Path:
    """Return the resolved path to the guidelines file (for testing)."""
    filename = _GUIDELINES_FILES.get(thesis_type)
    if filename is None:
        raise ValueError(f"No guidelines file for thesis type: {thesis_type!r}")
    return _GUIDELINES_DIR / filename
```

---

## Step 3 — Add ThesisType to domain

File: `agent/src/domain/analysis.py`

Add after `ReviewTone`:

```python
class ThesisType(StrEnum):
    """Type of thesis being evaluated."""
    BACHELOR       = "bachelor"
    MASTER_ARTICLE = "master_article"
```

---

## Step 4 — Update ThesisMetadata

File: `agent/src/domain/metadata.py`

Add `thesis_type` field:

```python
@dataclass(frozen=True)
class ThesisMetadata:
    """Descriptive metadata for a thesis submission."""
    author:         str
    title:          str
    year:           int
    field_of_study: str
    thesis_type:    str   # ThesisType value
    review_tone:    str   # ReviewTone value, default "auto"
```

---

## Step 5 — Update ThesisMetadataDict

File: `agent/src/application/state.py`

```python
class ThesisMetadataDict(TypedDict):
    author:         str
    title:          str
    year:           int
    field_of_study: str
    thesis_type:    str   # ThesisType value
    review_tone:    str   # ReviewTone value
```

---

## Step 6 — Update Celery task

File: `agent/src/application/tasks.py`

Load guidelines inside the task (not at import time) so that
`lru_cache` handles repeated calls efficiently:

```python
from corvus.application.guidelines import load_guidelines

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def analyze_thesis(
    self,
    evaluation_id: str,
    text: str,
    metadata: dict,
) -> dict:
    """Analyze thesis — guidelines loaded from metadata.thesis_type."""
    try:
        guidelines = load_guidelines(metadata["thesis_type"])

        initial_state: AnalysisState = {
            "evaluation_id": evaluation_id,
            "metadata":      metadata,
            "text":          text,
            "guidelines":    guidelines,   # loaded here, not passed from gateway
            "findings":      [],
            "scores":        [],
            "review":        None,
            "status":        EvaluationStatus.ANALYZING,
            "error":         None,
            "review_tone":   metadata.get("review_tone", "auto"),
        }

        graph = build_analysis_graph()
        result = graph.invoke(initial_state)
        return result

    except Exception as exc:
        raise self.retry(exc=exc)
```

Note: `guidelines` is no longer passed from the gateway as a parameter.
The task loads it internally based on `thesis_type`. Remove `guidelines`
from the task signature entirely.

---

## Step 7 — Update gateway

File: `gateway/src/infrastructure/router.py`

Remove `guidelines` from the Celery task call — it is now loaded
inside the task:

```python
class AnalysisRequest(BaseModel):
    thesis_type:    str
    author:         str
    title:          str
    year:           int
    field_of_study: str
    review_tone:    str = "auto"

# In the endpoint:
analyze_thesis.delay(
    evaluation_id=str(uuid4()),
    text=extracted_text,
    metadata={
        "author":         req.author,
        "title":          req.title,
        "year":           req.year,
        "field_of_study": req.field_of_study,
        "thesis_type":    req.thesis_type,
        "review_tone":    req.review_tone,
    },
)
```

---

## Step 8 — Update check_requirements node

File: `agent/src/application/nodes/requirements.py`

The node receives guidelines in `state["guidelines"]` — use them
directly as context in the system prompt:

```python
"""Requirements checking node — validates thesis against university guidelines."""

_SYSTEM_PROMPT = """You are checking a thesis against university requirements.

The requirements document is provided below. Check each requirement
systematically. For each violation found, create a Finding with:
- section: the specific requirement section (e.g. "1.4 Introduction")
- description: what is missing or incorrect
- severity: use ONLY the severity rules defined in section 4
  of the requirements document
- suggestion: concrete corrective action

Return ONLY a JSON array of findings:
[
  {
    "section": str,
    "description": str,
    "severity": "critical" | "major" | "minor",
    "suggestion": str
  }
]

If no violations found, return an empty array: []
Return raw JSON only — no markdown, no explanation."""


def check_requirements(state: AnalysisState) -> AnalysisState:
    """Check thesis conformance against university guidelines."""
    log = logger.bind(evaluation_id=state["evaluation_id"])

    try:
        llm = get_llm()
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"University requirements:\n{state['guidelines']}\n\n"
                f"Thesis text:\n{state['text'][:12000]}"
            )),
        ])

        data = json.loads(response.content.strip())
        new_findings = [
            Finding(
                section=f["section"],
                description=f["description"],
                severity=FindingSeverity(f["severity"]),
                suggestion=f["suggestion"],
            )
            for f in data
        ]

        log.info(
            "requirements check complete",
            findings_count=len(new_findings),
            critical=sum(1 for f in new_findings
                         if f.severity == FindingSeverity.CRITICAL),
        )

        return {**state, "findings": state["findings"] + new_findings}

    except Exception as exc:
        log.error("requirements check failed", error=str(exc))
        return {**state, "error": str(exc)}
```

---

## Step 9 — Frontend: thesis type selector

File: `frontend/components/analysis/UploadForm.tsx`

Add thesis type radio group (already partially planned):

```tsx
thesis_type: z.enum(["bachelor", "master_article"]),
```

UI labels:
```
Typ pracy:
○ Praca licencjacka
○ Praca magisterska (artykuł naukowy)
```

---

## Tests to write

File: `agent/tests/application/test_guidelines.py`

```python
# Test 1 — load_guidelines returns non-empty string for bachelor
# Test 2 — load_guidelines returns non-empty string for master_article
# Test 3 — load_guidelines raises ValueError for unknown thesis_type
# Test 4 — load_guidelines is cached (same object returned on second call)
# Test 5 — guidelines file contains "CRITICAL" section (smoke test)
```

File: `agent/tests/application/test_requirements_node.py`

```python
# Test 1 — node appends findings to existing state findings (does not replace)
# Test 2 — node correctly parses CRITICAL severity from model response
# Test 3 — node returns empty findings list when model returns []
# Test 4 — node sets state["error"] when model returns invalid JSON
# Test 5 — node passes guidelines from state to the model prompt
```

---

## Commit message

```
feat(agent): add guidelines loader and wire check_requirements node
```

---

## Verification

```bash
uv run pytest agent/tests/application/test_guidelines.py -v
uv run pytest agent/tests/application/test_requirements_node.py -v
uv run ruff check agent/
uv run pyright agent/
```

Manual check:
- [ ] bachelor guidelines load correctly for ThesisType.BACHELOR
- [ ] master guidelines load correctly for ThesisType.MASTER_ARTICLE
- [ ] check_requirements node produces findings with correct severity
- [ ] guidelines are NOT passed through the gateway (loaded in task)
