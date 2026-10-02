# Notatki na demo — AI Showcase, poniedziałek 2026-10-05

> Robocze. Scenariusz dogrywamy w niedzielę 2026-10-04.
> Publiczność: mała grupa programistów. Temat: jak używamy AI w prywatnych projektach.
> Format: **30 minut — prezentacja z demo w środku**, nie samo klikanie po aplikacji.
> Fikstury: [specs/demo-fixtures.md](specs/demo-fixtures.md) · mechanizmy: [specs/ai-extensions.md](specs/ai-extensions.md)

## Teza pokazu

Nie „aplikacja do recenzji prac”, tylko **„jak zbudować coś wokół LLM-a, żeby dało
się temu ufać”**. Na ekranie to formularze i przyciski — wszystko, co ciekawe,
jest pod spodem, więc trzeba to pokazać wprost. Samo klikanie po UI wygląda jak
kolejna nakładka na model.

## Układ 30 minut (szkic do niedzieli)

| Czas | Część | Co |
|---|---|---|
| 3 min | Po co to jest | promotor, prace dyplomowe, siedem predefiniowanych akcji zamiast czatu |
| 5 min | Co jest pod spodem | dwa serwisy, graf per akcja, klucz użytkownika, gdzie jest model, a gdzie go celowo nie ma |
| 10 min | Demo | trzy sceny niżej |
| 8 min | Problemy, z którymi trzeba było sobie poradzić | sekcja niżej — wybrać 3–4, resztę mieć na pytania |
| 4 min | Jak to powstało + pytania | Claude Code, ADR-y, evals jako pętla zwrotna |

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

## Problemy, z którymi trzeba było sobie poradzić

Materiał na część „nie wszystko poszło gładko”. Każdy punkt: co się stało, jak
wyszło na jaw, co pomogło, czego to uczy. Liczby są z przebiegów 2026-10-01/02.

1. **Model u dostawcy był nadgorliwy — recenzował licencjat jak artykuł do
   czasopisma.** Po przejściu na Claude recall nie był problemem (0,83–1,00);
   problemem było 27 uwag spoza klucza na trzech krótkich pracach i dobra praca
   odesłana do poprawy za identyfikację jednego współczynnika w modelu.
   - Krok 1: opis poziomu („praca dyplomowa na uczelni regionalnej, nie
     recenzja naukowa”), definicje wag, limit pięciu uwag. Fałszywe zarzuty
     1 → 0, ale dobra praca nadal odrzucona — wystarczyła jedna uwaga „krytyczna”.
   - Krok 2: **zamknięta lista** tego, co wolno nazwać krytycznym (brak celu,
     badanie niewykonane, wnioski sprzeczne z wynikami, hipoteza bez
     odpowiedzi). Rekomendacje 2/3 → 3/3.
   - Krok 3: to samo dla uwag poważnych i dla punktacji. Anioł (dobra praca):
     9 poważnych uwag → 3, wszystkie trzy merytorycznie zasadne.
   - Czego to uczy: model lepiej trzyma się reguły kategorycznej niż opisu
     tonu. I druga rzecz, którą trzeba powiedzieć wprost: prompty stroiłem na
     tych samych trzech pracach, na których mierzę — fikstury demo są jedynym
     sprawdzianem spoza zestawu.
   - Co zostało: punktacja nadal surowa (Anioł 25/40), liczba uwag ogółem
     prawie nie spadła — spadła ich waga.
2. **Architektura pod mały kontekst stała się balastem.** Lokalny model dostawał
   wycinek 7000 znaków; „Sprawdź postęp” porównywało przez to dwie strony
   tytułowe. Na pełnym tekście znalazło 5 z 6 wpisanych wad. Odwrotna strona:
   streszczenia rozdziałów (`Send` × N), zbudowane dla małego kontekstu, u
   dostawcy nie poprawiają wykrywalności i kosztują ok. 10 s — zmierzone, nie
   założone.
3. **Reguła też „halucynuje”.** Pierwsza wersja dopasowania bibliografii zgłosiła
   11 fałszywych alarmów: recenzja książki w Crossref brana za książkę,
   późniejsze wydanie brane za zły rok. Do tego Crossref odpowiedział 429 i 23
   z 42 pozycji zostały niesprawdzone. Pomogło: tempo według nagłówków limitu,
   katalogi bibliotek dla książek, agent dopiero dla ogona.
4. **Mapa dokumentu bez modelu miała błędy widoczne dopiero na prawdziwych
   pracach.** „1.9. Podsumowanie” brane za zakończenie całej pracy; spis treści
   z kropkami połykający wstęp. Drugi błąd siedział w kodzie od dawna, a mapy
   przypadków w evals były nieaktualne — evals mierzyły na złych danych.
5. **Zmiana modelu to nie zmiana jednej linijki.** Sonnet 5.5 zwraca treść w
   częściach (myślenie + tekst) — pierwsza akcja padła na parsowaniu. Wymuszony
   wybór narzędzia jest odrzucany, `max_tokens` trzeba podać jawnie (domyślne
   4096 obcinało recenzję), poziom `effort` zmienia czas z 37 s na 19 s.
   Structured output u dostawcy to prompt + walidacja + tura naprawcza; dwie
   analizy gubiły pole `severity`, dopóki prompt nie pokazał dosłownego kształtu JSON.
6. **Mechanizm działa, a funkcji nie ma.** Pauza grafu (`interrupt`) działała od
   pierwszego dnia, ale w UI nie było jak do niej wrócić: dashboard pokazywał
   „0 akcji w toku”, status wyświetlał się jako `awaiting_input`. Human in the
   loop to w połowie problem interfejsu.
7. **Operacyjne, czyli to, co zabiera najwięcej czasu.** Klucz bez przypisania
   do workspace'u pokazany jako „nie udało się połączyć”; środki na koncie
   skończone w połowie evals; „zawieszony” dostawca, który okazał się uśpionym
   laptopem. Stąd: komunikat dostawcy pokazywany wprost, limit 180 s na
   wywołanie, saldo na liście kontrolnej.
8. **Evals mają swoje granice.** Trzy przypadki, jeden przebieg, sędzia tym samym
   modelem — różnica jednej uwagi to 0,17 recall. Wystarcza, żeby zobaczyć
   kierunek (nadgorliwość, rekomendacje), nie wystarcza do porównywania wariantów.

## Co powiedzieć samemu, zanim ktoś zapyta

- **Infrastruktura jest przerośnięta względem skali** (Jenkins, SonarQube, Celery,
  Flower dla jednego użytkownika) — to projekt do nauki stacku, celowo.
- **Jakość:** na lokalnym modelu recall 0,61–0,67 (gubi co trzecią wpisaną wadę);
  na Claude Sonnet 5.5 recall 1,00, zero fałszywych zarzutów, rekomendacje 3/3 —
  ale to trzy syntetyczne prace, jeden przebieg i ten sam model jako sędzia.
- **Jak to powstało:** ADR-y, plan faz, `CLAUDE.md`, ok. 870 testów — budowane z
  Claude Code; to część odpowiedzi na temat showcase'u.

## Ustalenia z 2026-10-01 warte pokazania

- **Model u dostawcy czyta całą pracę, lokalny wycinek** — jedna decyzja w jednym
  miejscu (`excerpt.reading_budget`). „Sprawdź postęp” przy limicie 7000 znaków
  porównywało dwie strony tytułowe; na pełnym tekście znalazło 5 z 6 wad wpisanych
  w wersję drugą Miauczyńskiego (szacunek 3,7 mld zł, autor wśród respondentów,
  tabela 7 zapowiedziana jako 8).
- **Bibliografia: trzy źródła, agent tylko dla ogona.** Crossref dla artykułów,
  potem Biblioteka Narodowa i Open Library dla książek — bez modelu rozstrzyga się
  37 z 42 pozycji. Pierwsza wersja zgłosiła 11 fałszywych alarmów (recenzje książek
  zamiast książek, późniejsze wydania); dobry przykład, że reguła też halucynuje.
- **Mapa dokumentu bez modelu** miała dwa błędy znalezione dopiero na prawdziwych
  pracach: podsumowanie rozdziału brane za zakończenie pracy i spis treści z
  kropkami połykający wstęp. Liczby w mapie są policzone, nie odczytane przez model.
- **Human in the loop na żywo:** pauza po 38 s, stan w checkpoincie 13 minut,
  wznowienie z wyborem promotora (24 z 25 uwag), recenzja w 7 s.

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
- Saldo u obu dostawców sprawdzone i doładowane — 2026-10-02 środki na koncie
  Anthropic skończyły się w połowie evals (błąd 400 „credit balance is too low”).

## Otwarte

- [x] Chmura rusza (2026-10-01): `propose_topic` na `claude-sonnet-5-5`, effort `medium`, 19 s (na Sonnet 5 przy domyślnym effort: 37 s). OpenAI nadal niesprawdzone — brak klucza.
- [~] Każda z 7 akcji raz na żywo na studentach demo; wynik wobec `EXPECTED.md`.
  Przeszły 2026-10-01 na Claude: `propose_topic` (Pawlak, 19 s), `generate_review` z
  pauzą i wznowieniem (Kiepski, 38 s do pauzy, 7 s po wznowieniu), pełna recenzja
  (Ochódzki, 70 s), `verify_bibliography` (Adamczewski, 91 s), `check_progress`
  (Miauczyński, 25 s). Zostają: `evaluate_methodology`, `defence_questions`,
  `draft_meeting_note`.
- [x] Planowane wady w bibliografii Adamczewskiego (2026-10-01): książka i artykuł,
  których nie ma (autorzy z Trylogii), oraz prawdziwy artykuł ze złym rokiem. Wynik
  przebiegu: 38 potwierdzonych, 1 niezgodna, 2 podejrzane, 3 spoza indeksu — dokładnie
  według `EXPECTED.md`. Agent sam zauważył, że autorzy to postaci z Sienkiewicza.
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
