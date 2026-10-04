# Notatki na demo — AI Showcase, poniedziałek 2026-10-05

> Scenariusz ustalony 2026-10-04. Slajdy z notatkami prelegenta:
> [Corvus — AI Showcase](https://claude.ai/artifact/6HxsCvzRhP5Ube1w1DMLpy) (16 slajdów).
> Demo idzie z `main` — bez PR #4 (zliczanie tokenów, szyfrowanie klucza w kolejce), który wchodzi po demo.
> Publiczność: mała grupa programistów. Temat: jak używamy AI w prywatnych projektach.
> Format: **30 minut — prezentacja z demo w środku**, nie samo klikanie po aplikacji.
> Fikstury: [specs/demo-fixtures.md](specs/demo-fixtures.md) · mechanizmy: [specs/ai-extensions.md](specs/ai-extensions.md)

## Teza pokazu

Nie „aplikacja do recenzji prac”, tylko **„jak zbudować coś wokół LLM-a, żeby dało
się temu ufać”**. Na ekranie to formularze i przyciski — wszystko, co ciekawe,
jest pod spodem, więc trzeba to pokazać wprost. Samo klikanie po UI wygląda jak
kolejna nakładka na model.

## Scenariusz 30 minut

| Czas | Część | Slajdy | Co |
|---|---|---|---|
| 0:00–3:00 | Po co to jest | 1–2 | teza; siedem akcji zamiast czatu; „infrastruktura przerośnięta celowo” |
| 3:00–8:00 | Co jest pod spodem | 3–6 | dwa serwisy; graf recenzji; gdzie celowo nie ma modelu; kto co widzi |
| 8:00–18:00 | Demo | 7–8 | rozgrzewka + trzy sceny niżej; slajd z evals |
| 18:00–26:00 | Co poszło nie tak | 9–14 | cztery historie (niżej), reszta na pytania |
| 26:00–30:00 | Jak to powstało + pytania | 15–16 | Claude Code z rusztowaniem; teza na zamknięcie |

**Trik czasowy:** na slajdzie 3 (dwa serwisy) odpalić na żywo `verify_bibliography`
dla Adamczewskiego (ok. 91 s) — wynik jest gotowy na scenę 2.

**Zdanie na zamknięcie:** „Zaufanie do LLM-a nie bierze się z modelu, tylko z tego,
co wokół niego zmierzysz — i czego mu nie dasz robić.”

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

## Demo: rozgrzewka i trzy sceny

0. **Rozgrzewka (1 min):** `propose_topic` dla Pawlaka na żywo, ok. 19 s. W trakcie
   pokazać postęp kroków — dowód, że to nie nagranie.
1. **Recenzja Kiepskiego z pauzą (ok. 4 min).** Odpalona przed wejściem z „Pokaż mi
   uwagi…”, czeka na pauzie. Na żywo: lista uwag z cytatami → odznaczyć jedną →
   wznowić → recenzja w ok. 7 s, bez odznaczonej uwagi. Obok ślad w Langfuse:
   równoległe gałęzie, `Send`, pauza. Mechanizmy: grounding, `Send`, `interrupt`, checkpoint.
2. **Bibliografia Adamczewskiego (ok. 3 min).** Wynik przebiegu z triku czasowego:
   38 potwierdzonych, 1 niezgodna, 2 podejrzane, 3 spoza indeksu. Co rozstrzygnęła
   reguła, co agent, ile wywołań zużył. Puenta: agent sam zauważył, że autorzy to
   postaci z Trylogii.
3. **Slajd z evals (ok. 2 min).** Lokalnie recall 0,61–0,67; Sonnet 5.5 0,83–1,00,
   zero fałszywych zarzutów, rekomendacje 3/3 — i od razu granice (trzy prace,
   jeden przebieg, sędzia ten sam model; liczby lokalne sędziował qwen3).

Na pytania, gdy czas pozwoli: `check_progress` (Miauczyński v1 → v2, ok. 25 s).

**Z „problemów” niżej idą na scenę cztery:** 1 (nadgorliwość, z wpadką z
nieimportowanym promptem — osobny slajd), 3 (reguła też halucynuje), 2 (mały kontekst
jako balast), 6 (mechanizm działa, funkcji nie ma). Punkty 4, 5, 7 i 8 — na pytania.

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
   - Krok 4: punktacja. Skala w prompcie niczego nie zmieniła (Anioł 23–25/40),
     więc przedział punktów dla każdego kryterium liczy teraz kod z uwag
     (`application/scoring.py`), tak jak rekomendację; model wybiera w
     przedziale. Anioł: 28/40, ton „zasługuje na pozytywną ocenę”.
   - Wpadka po drodze: jedną rundę „strojenia” punktacji zrobiłem w pliku z
     promptem, którego żaden węzeł nie importował — i z recenzji wywnioskowałem,
     że „model ignoruje skalę”. Model jej nigdy nie widział. Wniosek o modelu
     warto poprzedzić sprawdzeniem, co faktycznie do niego poszło (ślad w Langfuse).
   - Co zostało: liczba uwag ogółem prawie nie spadła — spadła ich waga. Lista
     uwag poważnych zmienia się między przebiegami, więc punktacja też
     (Anioł ok. 27–31/40).
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
- **Jak to powstało:** ADR-y, plan faz, `CLAUDE.md`, ok. 940 testów — budowane z
  Claude Code; to część odpowiedzi na temat showcase'u.

## Pytania — odpowiedzi w jednym zdaniu

| Pytanie | Odpowiedź |
|---|---|
| Czemu nie czat? | Akcja ma znany kontekst i kształt wyniku, więc da się ją zmierzyć (ADR 0005). |
| Ile to kosztuje? | Recenzja 30–50 s na Sonnet 5.5; zliczanie tokenów jest w PR, wchodzi po demo. |
| Mniejszy model na proste kroki? | To byłby model routing — kilka sekund zysku, druga zmienna w evals; odpuszczone 2026-10-02. |
| Stroiłeś prompty pod testy? | Tak, na tych samych trzech pracach — fikstury demo to jedyny sprawdzian spoza zestawu. |
| A model lokalny? | Działa, ale gubi co trzecią wpisaną wadę, a recenzja trwa ok. 10 minut. |
| Bezpieczeństwo danych? | Tekst pracy tylko do dostawcy wybranego przy akcji; do Crossref tylko opisy bibliograficzne. |
| OpenAI? | Działa, jako pokaz przełączenia; kalibracja i evals tylko na Claude. |

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
- Wybór modelu: bez zapisanej preferencji UI bierze zapisany klucz (Claude przed
  OpenAI). Preferencja siedzi jednak w `localStorage` przeglądarki — jeśli w
  przeglądarce na demo zapisano kiedyś model lokalny, akcja pójdzie lokalnie
  (ok. 10 minut). Przed wejściem spojrzeć, czy w ramce „Model” stoi Claude.
- Limity zapytań na koncie dostawcy przy równoległych gałęziach recenzji.
- Plan awaryjny: wyniki z próby zostają w historii studentów — przy padzie sieci
  pokazać zapisane.

## Przed wejściem (ok. 30 min wcześniej)

- Na hoście `main`, nie gałąź PR #4.
- `make demo-reset PROMOTOR=<e-mail>` — stan wyjściowy, ten sam za każdym razem.
- Saldo u obu dostawców sprawdzone i doładowane — 2026-10-02 środki na koncie
  Anthropic skończyły się w połowie evals (błąd 400 „credit balance is too low”).
- Klucze Claude i OpenAI wpisane w ustawieniach promotora; **w ramce „Model” stoi Claude**.
- `make langfuse-up`, http://localhost:3100 otwarte.
- Odpalić recenzję Kiepskiego z „Pokaż mi uwagi…” i zostawić na pauzie.
- Laptop na zasilaniu, usypianie wyłączone.
- Karty w kolejności: slajdy → dashboard → Pawlak → Kiepski → Adamczewski → Langfuse.
- Plan awaryjny: zrzuty z próby generalnej (lista uwag Kiepskiego, wynik bibliografii,
  ślad w Langfuse) dołożone jako ukryte slajdy na końcu talii.

## Otwarte

- [x] Chmura rusza (2026-10-01): `propose_topic` na `claude-sonnet-5-5`, effort `medium`, 19 s (na Sonnet 5 przy domyślnym effort: 37 s). OpenAI: `propose_topic` na `gpt-6.1-sol`, 34 s.
- [x] Każda z 7 akcji raz na żywo na studentach demo; wynik wobec `EXPECTED.md`.
  Przeszły 2026-10-01 na Claude: `propose_topic` (Pawlak, 19 s), `generate_review` z
  pauzą i wznowieniem (Kiepski, 38 s do pauzy, 7 s po wznowieniu), pełna recenzja
  (Ochódzki, 70 s), `verify_bibliography` (Adamczewski, 91 s), `check_progress`
  (Miauczyński, 25 s), `evaluate_methodology` (Kargul, 25 s), `defence_questions`
  (Anioł, 14 s). 2026-10-02: `draft_meeting_note` z zapisem notatki (Pawlak, 4 s).
- [x] Planowane wady w bibliografii Adamczewskiego (2026-10-01): książka i artykuł,
  których nie ma (autorzy z Trylogii), oraz prawdziwy artykuł ze złym rokiem. Wynik
  przebiegu: 38 potwierdzonych, 1 niezgodna, 2 podejrzane, 3 spoza indeksu — dokładnie
  według `EXPECTED.md`. Agent sam zauważył, że autorzy to postaci z Sienkiewicza.
- [x] Claude jest głównym dostawcą, OpenAI tylko jako pokaz przełączenia (decyzja
  2026-10-02). Kalibracja i evals były robione na Claude — na OpenAI nie są zmierzone.
- [x] Domyślny dostawca dla akcji, gdy promotor ma klucz (sprawdzone 2026-10-02):
  UI wybiera zapisany klucz, Claude pierwszy; pokryte testem `modelChoice`.
- [x] Evals z opcją dostawcy (`make eval MODEL=claude`) i przebiegi na Sonnet 5.5 —
  liczby w [specs/ai-extensions.md](specs/ai-extensions.md).
- [x] **Tiering modeli per węzeł — odpuszczony (decyzja 2026-10-02).** Recenzja
  trwa 30–50 s na jednym modelu; mniejszy model na kroku map dałby kilka sekund,
  a dołożyłby drugą zmienną do evals. Jeśli ktoś zapyta: to byłby *model
  routing*, nie orkiestracja — trudność kroku jest znana z góry (ADR 0005).
- [x] **Streszczenia rozdziałów zostają włączone (decyzja 2026-10-02).** Pomiar nie
  pokazał zysku w wykrywalności, kosztują ok. 10 s — zostają, bo pokazują
  fan-out (`Send`) w śladzie. Powiedzieć to wprost, z liczbą.
- [x] Scenariusz i slajdy (2026-10-04).
- [ ] Próba generalna dwa razy od `demo-reset`, ze stoperem — demo ≤ 10 min, problemy ≤ 8 min.
- [ ] Zrzuty z próby jako ukryte slajdy awaryjne.
