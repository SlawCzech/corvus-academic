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

Recenzję próbną puszcza `--action trial_review`, ale klucz odpowiedzi mierzy tylko
uwagi, więc nie mówi nic o jakości jej zaleceń. Raport liczy też `advice in reviews`: sformułowania w gotowej recenzji, które
zlecają coś autorowi albo planują obronę. Ma być 0: praca jest skończona, a tekst
idzie do systemu uczelni. Recenzji próbnej to nie dotyczy.

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

Ostatni przebieg (2026-11-01, `claude-sonnet-5-5`, po trzy powtórzenia): 20 z 21
przypadków. Prompt strojony na qwen3 dawał na Claude 3 z 7: model wypełniał limit
uzupełnień i oddawał `needs_additions` także dobrym rozdziałom. Pomogły dwie
rzeczy: limity są sufitem, nie celem, a `needs_additions` tylko wtedy, gdy bez
braku nie da się iść dalej. Claude to teraz punkt odniesienia; po tej zmianie
promptu qwen3 nie był mierzony.

## Pytania na obronę (`defence_questions`)

Bez własnych przypadków: te same trzy prace, bo klucza odpowiedzi tu nie ma.
Liczy się rodzaj pytania, nie to, które padło.

```bash
make eval-defence MODEL=claude              # ANTHROPIC_API_KEY
```

Bez modelu sprawdzane są: trzy pytania, limit słów, jedno pytanie w zdaniu (w tym
dwa sklejone przez „i jakie…”) i brak liczb, tabel, stron. Sędzia czyta, czy
student odpowie z głowy, czy pytanie należy do tej pracy i o co pyta: cel, metoda
czy wnioski. Sklejonych pytań sędzia sam nie łapie, stąd osobny regex.

Punkt wyjścia, 2026-11-01, `claude-sonnet-5-5`: 0 z 3, pytania po 47–85 słów, z
cytowanymi wynikami i numerami podrozdziałów, kilka pytań w jednej karcie. Po
zmianie promptu: 1 z 3, pytania po 11–19 słów i bez szczegółów, ale 2 z 9 nadal
sklejone przez „i”. Jeden przebieg, więc to wrażenie, nie średnia. Trzecia wpadka
to sędzia: „pasuje do każdej pracy” o pytaniu, które nazywa temat pracy. Na qwen3
nie mierzone.

## Postęp między wersjami (`check_progress`)

Osobny zestaw w `progress_cases/`. Pilnuje jednego: notatka ze spotkania to
kontekst, nie lista wymagań.

```bash
make eval-progress MODEL=claude             # ANTHROPIC_API_KEY
```

| id | co w nim siedzi |
|---|---|
| `prosba-wykonana` | notatka prosi o uzasadnienie próby, nowa wersja to robi; raport ma to zaliczyć |
| `prosba-niewykonana` | dwie prośby, jedna wykonana; raport ma powiedzieć jedno i drugie |
| `notatka-tylko-wspomina` | notatka wspomina Williamsona, wywiady i Volksbanki, o nic nie prosi; nic z tego nie wraca jako brak ani następny krok |

Sędzia czyta cały raport i odpowiada, czy padło to, co paść miało, i nie padło to,
co nie miało. Przebieg bez notatek nie ma tu przypadku: prompt jest wtedy co do
znaku taki jak wcześniej, a pilnuje tego test jednostkowy.

Ostatni przebieg (2026-11-01, `claude-sonnet-5-5`, po trzy powtórzenia): 9 z 9.
Kontrola: `notatka-tylko-wspomina` z notatką, ale bez `NOTES_RULE`, 0 z 3; za każdym
razem Williamson, wywiady i Volksbanki wracały jako braki albo propozycje. Pierwsza
wersja tego przypadku przechodziła także bez reguły, bo notatka sama mówiła „na inną
okazję”. Stąd zasada: przypadek na regułę trzeba sprawdzić bez reguły. Na qwen3 nie
mierzone.

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
mało zachęcający.

Na Claude, 2026-11-01, po trzy powtórzenia: `dryf-od-celu`, `cel-nie-caly` i
`runda-druga` 3/3, `obszar-bez-wymagan` 2/3 (raz podsunął koszty transakcyjne jako
brak). Pełna
recenzja po zmianach z ADR 0015: recall 0,83–1,00, 0 fałszywych alarmów,
rekomendacje 3/3, 8–13 duplikatów, ok. 85 s; poziom sprzed zmian.
