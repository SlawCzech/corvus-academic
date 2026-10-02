# Rozszerzenia AI — co zostało zrobione i czego uczy

> Status: zrobione 2026-09-30, gałąź `feat/ai-extensions` · jeden commit na punkt.
> Powiązane: [ADR 0010](../adr/0010-graph-checkpoints-and-late-acks.md) ·
> [agent/evals/README.md](../../agent/evals/README.md) ·
> [architecture.md](../architecture.md)

Dwa cele naraz: nauczyć się mechanizmów LangGraph na prawdziwym problemie i
podnieść jakość recenzji. Kolejność nie jest przypadkowa — najpierw to, co
pozwala **zmierzyć** każdą następną zmianę (tracing, evals), potem jakość,
potem mechanika grafu.

## Graf recenzji po zmianach

```
START ─┬─ analyze_structure ────┐
       ├─ analyze_methodology ──┤
       ├─ check_requirements ───┤
       └─ route_chapters ─Send×N─ digest_chapter ─ check_coherence ─┤
                                                                   ↓
                     verify (bez modelu) → promoter_review (interrupt?) → generate_review
```

## Punkty

| # | Co | Gdzie | Mechanizm do zrozumienia |
|---|---|---|---|
| 0 | BYOK na aktualnych modelach (`claude-sonnet-5-5`, `gpt-6.1-sol`) | `infrastructure/llm_factory.py` | — |
| 1 | Tracing każdego przebiegu w self-hosted Langfuse | `infrastructure/tracing.py`, `infra/langfuse/` | callbacki LangChain; `config` przekazywany przez graf do każdego `llm.invoke` przez contextvar |
| 2 | Evals: syntetyczne prace z wpisanymi wadami + sędzia | `agent/evals/` | LLM-as-judge tylko do dopasowania; metryki w czystym Pythonie |
| 3 | Structured output: schema → Ollama `format`, walidacja, tura naprawcza | `application/structured.py`, `replies.py` | constrained decoding vs walidacja vs repair |
| 4 | Cytat przy każdej uwadze + deterministyczna weryfikacja i deduplikacja | `application/grounding.py`, `nodes/verify.py` | reducer `operator.add` i jego obejście `Overwrite` |
| 5 | Map-reduce po rozdziałach: czy wnioski wynikają z wyników | `application/chapters.py`, `nodes/coherence.py` | `Send` — dynamiczny fan-out; `input_schema` węzła; join |
| 6 | Postęp na żywo (które kroki gotowe) | `tasks._stream`, migracja 0005, `ActionProgress.tsx` | `graph.stream(stream_mode=["updates","values"])` |
| 7a | Checkpointy w Postgresie, wznowienie po padnięciu workera | `infrastructure/checkpoints.py`, ADR 0010 | checkpointer, `thread_id`, pending writes, allowlista serde; Celery `acks_late` |
| 7b | Promotor odznacza uwagi przed napisaniem recenzji | `nodes/promoter_review.py`, `FindingPicker.tsx` | `interrupt` + `Command(resume=…)` |
| 8 | Weryfikacja bibliografii w Crossref, agent dla reszty | `application/bibliography.py`, `nodes/bibliography.py` | pętla ReAct jako dwa węzły + krawędź warunkowa; `ToolNode`; budżet narzędzi |

## Wyniki evals (qwen3:30b-a3b, sędzia qwen3:30b-a3b)

| stan | recall | underrated | dup | false flags | failed nodes | czas |
|---|---|---|---|---|---|---|
| przed (punkt wyjścia) | 0.61 | 1 | 0 | 0 | 1 | 1552 s |
| po 3 + 4 + 5 (drugi przebieg, 2026-09-30) | 0.67 | 0 | 3 | 0 | 0 | 1846 s |

## Wyniki evals na dostawcy (claude-sonnet-5-5, effort medium, sędzia ten sam model) — 2026-10-01

| stan | recall | underrated | dup | false flags | unmatched | rekomendacje | czas |
|---|---|---|---|---|---|---|---|
| pełna recenzja, ze streszczeniami rozdziałów | 0.83 | 0 | 10 | 1 | 27 | 2/3 | 97 s |
| bez streszczeń rozdziałów (`REVIEW_CHAPTER_DIGESTS=false`) | 1.00 | 1 | 8 | 1 | 23 | 2/3 | 66 s |
| kalibracja: poziom pracy dyplomowej, wagi, limit uwag (2026-10-01) | 0.83 | 0 | 8 | 0 | 23 | 2/3 | 89 s |
| kalibracja z zamkniętą listą uwag krytycznych (2026-10-02) | 1.00 | 1 | 11 | 0 | 19 | 3/3 | 101 s |
| + co jest uwagą poważną, a co drobną (2026-10-02) | 1.00 | 1 | 9 | 0 | 20 | 3/3 | 107 s |
| + przedziały punktacji liczone z uwag (2026-10-02) | 0.83 | 1 | 9 | 0 | 18 | 3/3 | 96 s |

Trzy przypadki, po jednym przebiegu — różnica w recall to jedna uwaga, czyli szum.
Co z tego wynika: streszczenia rozdziałów nie poprawiają wykrywalności, gdy każda
analiza czyta całą pracę, a kosztują ok. 10 s na recenzję. Jedyny sygnał na ich
korzyść: bez nich „hipotezy niezweryfikowane” wyszły z zaniżoną wagą.

Liczb z qwen3 nie da się z tymi wprost zestawić (inny sędzia). Problemem na
dostawcy nie jest recall, tylko nadgorliwość: 23–27 uwag spoza klucza na trzech
krótkich pracach, a dobra praca (`oszczednosci`) dostaje „Zwrócić do poprawy”.

Kalibracja (`prompts/scopes.py`, `CALIBRATION`) mówi analizom, że czytają pracę
dyplomową, a nie artykuł do recenzji. Sam opis poziomu nie wystarczył: dobra praca
nadal wracała do poprawy przez jedną „krytyczną” uwagę o specyfikacji modelu.
Pomogło dopiero zamknięcie listy tego, co wolno nazwać krytycznym. Prompty są
strojone na tych samych trzech pracach, na których są mierzone — sprawdzianem
spoza zestawu są fikstury demo.

Punktacji evals nie mierzą. Jej przedziały wynikają z uwag i liczy je kod
(`application/scoring.py`): bez uwagi poważnej w kryterium 8–10, z jedną 7–8,
z kilkoma 6–7, z krytyczną najwyżej 5. Model wybiera w przedziale; wynik spoza
niego jest przycinany i logowany (`review_scores_held_to_findings`).

Pełne liczby i każda uwaga: `agent/evals/results/`.

## Decyzje, które warto umieć obronić

- **Langfuse, nie LangSmith** — prompt niesie tekst pracy studenta; ślady
  zostają na tej samej maszynie co praca.
- **Weryfikacja cytatów bez modelu** — model sprawdzający model dokłada drugi
  punkt awarii; `normalize` + trigramy są deterministyczne i testowalne co do znaku.
- **Deduplikacja ostrożna** (próg 0.5 na rdzeniach) — połączenie dwóch różnych
  wad gubi jedną, zostawienie duplikatu tylko ją podwaja.
- **`Send` zamiast supervisora** — liczba gałęzi wynika z danych (rozdziały),
  nie z decyzji modelu; to nadal predefiniowana akcja (ADR 0005).
- **Agent tylko dla ogona bibliografii** — reguła rozstrzyga większość pozycji
  za darmo; agent (wolny na lokalnym modelu) dostaje to, czego reguła nie umie.
- **Crossref, nie OpenAlex** — OpenAlex liczy dziś koszt za zapytanie.
- **Wznowienie pod tym samym id taska** — wątek checkpointu, wiersz statusu i
  `revoke` przy anulowaniu dotyczą jednego przebiegu.

## Co zostało otwarte

- Ollama na hoście potrzebuje `OLLAMA_NUM_PARALLEL=3`, żeby analizy i
  streszczenia rozdziałów naprawdę szły równolegle.
- Evals na `gemma4:26b` dla porównania z qwen3 (`make eval MODEL=gemma4:26b`).
- Redelivery taska, który za każdym razem zabija workera, nie ma limitu
  (ADR 0010, Consequences).
