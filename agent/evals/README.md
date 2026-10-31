# Evals — czy zmiana promptu albo modelu poprawiła recenzję

Trzy syntetyczne prace licencjackie z wadami wpisanymi celowo, klucz odpowiedzi
do każdej i skrypt, który puszcza je przez prawdziwy graf akcji i liczy wynik.
Bez tego każda zmiana promptu to wrażenie z jednego przebiegu.

```bash
make eval                                   # qwen3:30b-a3b, wszystkie przypadki
make eval MODEL=gemma4:26b                  # inny model, ten sam klucz
make eval MODEL=qwen3:30b-a3b CASES="pokolenie-z"
cd agent && uv run python -m evals.run --model qwen3:30b-a3b --judge claude  # ANTHROPIC_API_KEY
cd agent && uv run python -m evals.run --model claude                        # graf i sędzia na Claude
```

Chodzi na hoście, przeciw Ollamie z hosta (`127.0.0.1:11434` — nie `localhost`,
bo na Macu z postawionym compose `::1:11434` to kontener bez modeli czatu). Nie
potrzebuje Postgresa, Celery ani `app`. Pełen przebieg na qwen3:30b-a3b to ok.
25 minut.

## Przypadki

| id | co w nim siedzi |
|---|---|
| `kryptowaluty` | słaba praca: cel bez problemu, pytań i hipotez; 9 źródeł, prawie same strony www, zero obcojęzycznych; ankieta „wśród znajomych” uogólniona na „Polaków” |
| `oszczednosci` | dobra praca; wpisane tylko: bibliografia nie alfabetycznie od poz. 14 i tabele bez spisu tabel. Głównie test tego, co model **zmyśli** |
| `pokolenie-z` | wnioski sprzeczne z wynikami (39% wskazuje płacę, zakończenie mówi o 70% za czynnikami pozafinansowymi), 23 osoby z jednej firmy uogólnione na pokolenie, rozdział o Taylorze niezwiązany z problemem, hipotezy nigdy niezweryfikowane |

Prace są skrócone (7–12 tys. znaków zamiast 80–130), żeby całość mieściła się
w wycinku, który czyta węzeł. Wymóg długości w wytycznych jest dlatego
przeskalowany (`dataset.condensed_guidelines`); reszta to prawdziwy dokument.

Każdy przypadek ma `document_map.json` — mapę, którą `app` wysłałby razem z
tekstem (z niej `check_coherence` tnie pracę na rozdziały). Po edycji pracy:
`make eval-maps`. Od 2026-09-30 spisy treści mają numery stron — bez nich
mapa `app` brała spis za treść (zgłoszone osobno).

Znana rzecz spoza klucza: w `pokolenie-z` „Kozioł” stoi po „Koźmińskim” — w
polskim porządku alfabetycznym powinien przed. Model, który to wyłapie, ma
rację; w wyniku liczy się to jako `unmatched`.

## Fragmenty (`review_fragment`)

Osobny zestaw w `fragment_cases/`, bo ta akcja nie zwraca uwag z wagą, a jej
najważniejszego wymogu, łagodnego tonu, nie utrzyma żaden test jednostkowy.

```bash
make eval-fragments                         # qwen3:30b-a3b, wszystkie przypadki
make eval-fragments MODEL=claude            # ANTHROPIC_API_KEY
```

| id | co w nim siedzi |
|---|---|
| `solidny-rozdzial` | dobry rozdział na temat; model nie ma czego szukać na siłę |
| `urwany-rozdzial` | dobry rozdział urwany w połowie zdania; nie wolno mu tego wytknąć |
| `poza-tematem` | sprawny rozdział nie na temat; jedyny, który ma wrócić `needs_changes` |
| `runda-druga` | druga runda: jedna z dwóch próśb wykonana; szkic ma powiedzieć jedno i drugie |

Bez modelu sprawdzane są limity list, brak ocen liczbowych i ostrych sformułowań.
Sędzia czyta sam feedback (bez podsumowania) i odpowiada, czy zachęca do dalszej
pracy, oraz czy padło to, co paść miało, i nie padło to, co nie miało.

Ostatni przebieg (2026-10-31, `qwen3:30b-a3b`): 4 z 4. Przypadki graniczne
(`poza-tematem`, `solidny-rozdzial`) przeszły też po trzy razy osobno, bo jedna
reguła w prompcie potrafi przesunąć model w drugą stronę. Na Claude jeszcze
niepuszczone. Podsumowania mają 90–115 słów, w jednym akapicie.

## Co znaczą liczby

- **recall** — ile wpisanych wad recenzja nazwała. Główna liczba.
- **underrated** — nazwana, ale z niższą wagą, niż każą wytyczne (brak hipotez
  jako MINOR).
- **dup** — ile uwag powtarza wadę, którą już nazwała inna uwaga.
- **false flags** — uwagi twierdzące coś, co nie jest prawdą (np. „brak
  zakończenia”). Najdroższy błąd: promotor, który złapie jeden, przestaje ufać reszcie.
- **unmatched** — uwagi o czymś spoza klucza. Nie z definicji złe; rośnie
  między dwiema wersjami promptu — warto przeczytać.
- **failed nodes** — gałęzie, które padły (np. zły JSON).

Dopasowanie uwagi do wady robi model-sędzia (`judge.py`), bo „brak hipotez
badawczych” i „the introduction states no hypothesis” to ta sama wada. Cała
reszta to zwykły Python (`metrics.py`) z testami. Sędzia powinien być co
najmniej tak mocny jak testowany model.

Każdy przebieg zapisuje `results/<czas>-<model>.json` ze wszystkimi uwagami —
zaskakującą liczbę da się przeczytać, zamiast puszczać jeszcze raz.

## Historia wyników

| kiedy | co się zmieniło | model | recall | underrated | dup | false flags | failed nodes | czas |
|---|---|---|---|---|---|---|---|---|
| 2026-09-30 | punkt wyjścia (przed structured output i weryfikacją cytatów) | qwen3:30b-a3b | 0.61 | 1 | 0 | 0 | 1 | 1552 s |
| 2026-09-30 | + structured output, cytaty i weryfikacja (punkty 3–4) | qwen3:30b-a3b | 0.67 | 0 | 3 | 0 | 0 | 1846 s |

### Obszar i cel (ADR 0015)

Trzy przypadki na ryzyka nowych pól, `qwen3:30b-a3b`, 2026-10-31, po trzy powtórzenia
tam, gdzie wynik bywał różny:

| Przypadek | Co sprawdza | Wynik |
|---|---|---|
| `dryf-od-celu` | ankieta bada nie tych ludzi, co cel: widać to tylko z pola | 4/4 |
| `obszar-bez-wymagan` | obszar nie staje się listą lektur | 1/1 |
| `cel-nie-caly` | cel nie psuje dobrego rozdziału | 2/3 po zaostrzeniu reguły |

`runda-druga` wyszła 2/3: kierunek za każdym razem dobry, raz sędzia uznał ton za
mało zachęcający. Na Claude nie mierzone.
