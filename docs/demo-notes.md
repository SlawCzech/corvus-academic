# Notatki na demo — AI Showcase, poniedziałek 2026-10-05

> Robocze. Scenariusz dogrywamy w niedzielę 2026-10-04.
> Publiczność: mała grupa programistów. Temat: jak używamy AI w prywatnych projektach.
> Fikstury: [specs/demo-fixtures.md](specs/demo-fixtures.md) · mechanizmy: [specs/ai-extensions.md](specs/ai-extensions.md)

## Teza pokazu

Nie „aplikacja do recenzji prac”, tylko **„jak zbudować coś wokół LLM-a, żeby dało
się temu ufać”**. Na ekranie to formularze i przyciski — wszystko, co ciekawe,
jest pod spodem, więc trzeba to pokazać wprost. Samo klikanie po UI wygląda jak
kolejna nakładka na model.

## Mechanika AI do uwypuklenia

| Mechanizm | Co powiedzieć jednym zdaniem | Gdzie to widać |
|---|---|---|
| Cytat przy każdej uwadze + weryfikacja bez modelu | Model nie sprawdza modelu: kod szuka cytatu w tekście pracy, uwaga bez pokrycia odpada | `application/grounding.py`, `nodes/verify.py`; w UI cytat pod uwagą |
| Fan-out po rozdziałach (`Send`) | Liczba gałęzi wynika z danych, nie z decyzji modelu | ślad w Langfuse: równoległe gałęzie |
| Pauza na decyzję człowieka (`interrupt`) | Graf staje, stan leży w checkpoincie, promotor odznacza uwagi, graf rusza dalej | `nodes/promoter_review.py`, `FindingPicker` |
| Checkpointy w Postgresie | Zabity worker kosztuje jeden krok, nie całą recenzję | ADR 0010 |
| Agent tylko dla ogona | Reguła rozstrzyga większość bibliografii za darmo; pętla z narzędziami i budżetem 12 wywołań dostaje resztę | `nodes/bibliography.py`; wynik: co rozstrzygnęła reguła, co agent |
| Structured output: schema → walidacja → tura naprawcza | Poprawny JSON to jeszcze nie właściwy JSON | `application/structured.py` |
| Evals z wadami wpisanymi celowo | Wiem, czego model nie łapie, bo sam to tam włożyłem | `agent/evals/`, `EXPECTED.md` przy każdej pracy |
| Predefiniowane akcje zamiast czatu | Każda akcja ma swój graf, kontekst i kształt wyniku | ADR 0005 |
| Klucz użytkownika per akcja | Klucz jedzie osobno, żyje w ContextVar na czas przebiegu, nie trafia do stanu ani checkpointu | ADR 0011, `llm_factory.py` |
| Do Crossref idą tylko opisy bibliograficzne | Tekst pracy nigdy nie wychodzi poza dostawcę modelu | `nodes/bibliography.py` |

## Trzy sceny (propozycja)

1. **Recenzja Kiepskiego z pauzą.** Recenzja odpalona przed wejściem; na żywo:
   lista uwag z cytatami, odznaczenie jednej, wznowienie, recenzja bez niej.
   Obok ślad w Langfuse. Mechanizmy: grounding, `Send`, `interrupt`, checkpoint.
2. **Bibliografia Adamczewskiego.** Co rozstrzygnęła reguła, co agent, ile
   wywołań zużył. Mechanizmy: ReAct jako dwa węzły, budżet narzędzi.
3. **Slajd z evals.** Liczba, jak powstała, i wprost — czego jeszcze nie umie.

Reszta akcji działa i jest „jest też to”, nie punkt programu.
Krótkie akcje na żywo: `propose_topic` (Pawlak), `check_progress` (Miauczyński v1 → v2).

## Co powiedzieć samemu, zanim ktoś zapyta

- **Infrastruktura jest przerośnięta względem skali** (Jenkins, SonarQube, Celery,
  Flower dla jednego użytkownika) — to projekt do nauki stacku, celowo.
- **Jakość:** recall 0,61–0,67 na trzech syntetycznych pracach, lokalny model,
  ten sam model jako sędzia. Model gubi mniej więcej co trzecią wpisaną wadę.
  Liczba na Claude — do uzupełnienia po przebiegu evals.
- **Jak to powstało:** ADR-y, plan faz, `CLAUDE.md`, ok. 870 testów — budowane z
  Claude Code; to część odpowiedzi na temat showcase'u.

## Ryzyka na żywo

- Recenzja trwa minuty nawet na chmurze → odpalić przed wejściem, pokazać wynik.
- Brak wyboru dostawcy w UI = model lokalny (ok. 10 minut). Do naprawy przed demo.
- Limity zapytań na koncie dostawcy przy równoległych gałęziach recenzji.
- Plan awaryjny: wyniki z próby zostają w historii studentów — przy padzie sieci
  pokazać zapisane.

## Przed wejściem

- `make demo-reset PROMOTOR=<e-mail>` — stan wyjściowy, ten sam za każdym razem.
- Odpalić recenzję Kiepskiego z „Pokaż mi uwagi…” i zostawić na pauzie.
- Langfuse otwarty (`make langfuse-up`, http://localhost:3100).
- Klucze Claude i OpenAI wpisane w ustawieniach promotora.

## Otwarte

- [x] Chmura rusza (2026-10-01): `propose_topic` na `claude-sonnet-5-5`, effort `medium`, 19 s (na Sonnet 5 przy domyślnym effort: 37 s). OpenAI nadal niesprawdzone — brak klucza.
- [ ] Każda z 7 akcji raz na żywo na studentach demo; wynik wobec `EXPECTED.md`.
- [ ] Podejrzana pozycja w bibliografii Adamczewskiego (wyjątek od „nie zmyślamy źródeł”) — decyzja.
- [ ] Claude jako główny dostawca, OpenAI tylko jako pokaz przełączenia — decyzja.
- [ ] Domyślny dostawca dla akcji, gdy promotor ma klucz.
- [ ] Evals z opcją dostawcy + przebieg bazowy na jednym modelu (Sonnet).
- [ ] **Sobota, warunkowo po evals — tiering modeli per węzeł.** Mały model na
  `digest_chapter` (krok map), ewentualnie `extract_references` i
  `draft_meeting_note`; średni na analizy i agenta bibliografii; duży na
  `generate_review` tylko jeśli evals pokażą zysk wart wolniejszej odpowiedzi.
  Zostaje wyłącznie z liczbami: recall nie spada, czas spada. `get_llm` dostaje
  parametr poziomu. To *model routing*, nie orkiestracja — trudność kroku jest
  znana z góry (ADR 0005). Jeśli wejdzie: ADR 0012 (promotor wybiera dostawcę,
  nie model — zmiana względem ADR 0011).
- [ ] Próba generalna dwa razy od `demo-reset`, ze stoperem.
