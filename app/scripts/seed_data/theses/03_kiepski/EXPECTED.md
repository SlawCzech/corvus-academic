# Ferdynand Kiepski — expected findings

BA, weak. Rubric: `bachelor.md` (UE Katowice, Zarządzenie 117/22 zał. 1).
Body ~31 000 chars (whole document ~33 500 with title page and statements).

Every defect below is planted on purpose. A review that misses the CRITICAL ones
is a miss; one that praises the thesis is a bug.

## CRITICAL (rubric § 5)

1. **Introduction has no research problem, aim, or questions/hypotheses.** It
   says "chciałbym pokazać, że ta opinia ma swoje uzasadnienie" — an opinion to
   confirm, not a research question.
2. **Conclusion refers to no problem or hypothesis** — there were none; it
   re-states the opinion as "potwierdzone".
3. **Fewer than 25 literature items** — 5 books, the rest is netography and
   non-sources.
4. **Fewer than 4 foreign-language items** — one (Keynes, 1936).
5. **Unidentifiable sources**: "(internet)", "Źródło: internet", "opracowanie
   własne na podstawie internetu", "Film o bezrobociu na świecie, YouTube",
   "Ogłoszenia o pracy, Gazeta Wrocławska, różne wydania".
6. **Citations not in APA**: "(Keynes)", "(Samuelson)" without years, "(internet)";
   bibliography in three different formats, "Samuelson P., Nordhaus W., Ekonomia."
   with no year or publisher; not numbered.

## MAJOR

7. **Volume** far below the suggested 80 000–130 000 chars.
8. **Introduction incomplete** besides (1): no scope (subject/object/time/space),
   no methods, no characterisation of the literature.
9. **Literature outdated and not matched to the problem** — newest book 2007,
   nothing on over-education or skills mismatch.
10. **Chapter 3 (history, monuments, zoo, football in Wrocław) is unrelated** to
    the research problem — padding.
11. **No list of tables** although there are four tables.
12. **Language**: first person throughout ("wybrałem", "przeprowadziłem") despite
    the template's impersonal-form rule; colloquialisms ("najniższa krajowa",
    "umowy śmieciowe", "pierwszą lepszą pracę").

## Methodology and substance

13. **Sample does not match the subject.** Six residents of one tenement, none
    with higher education (2× primary, 2× vocational, 1× secondary, 1× incomplete
    secondary) — then declared "osoby wykształcone w szerokim tego słowa
    znaczeniu". "Educated" is never defined.
14. **Author is a respondent**, and the others are his household and neighbours
    (initials F.K., H.K., W.K. give it away) — framed as an advantage.
15. **Scope in the title (Poland and the world) vs data (one building).**
    4.3 claims the results are "reprezentatywne … dla całego problemu … na świecie".
16. **Conclusions contradict the data.** Four of six did not look for work in a
    year; the author himself turned down offers; H.K.'s employer is hiring and
    nobody applied — yet the conclusion is "nie ma pracy dla ludzi z wykształceniem".
    H.K.'s dissenting answer is dismissed as "nie jest reprezentatywna".
17. **Factual errors in theory**: the Phillips curve described backwards
    (higher unemployment → higher inflation); Keynes credited with the view that
    unemployment is largely voluntary — the opposite of his argument.
18. **Text vs table**: the text says unemployment in Poland was 25% in 2004,
    table 1 says 19.0%. *Needs tables extracted — they are, see note.*
19. **Recommendations do not follow from the analysis**: higher benefits so the
    educated can wait for a fitting offer, grants without a business plan,
    limiting employment of foreigners.

## Note: tables and the extractor

`app/src/document/extractor.py` reads the DOCX body in document order and
renders each table in place, one line per row with cells joined by " | "
("Tabela 1. Stopa bezrobocia w Polsce" is followed by "2004 | 19,0"). Tables
1–4 reach the model in the DOCX as well as in a PDF export, so (18) is
detectable. (13) never depended on it — the sample is also described in prose
(4.1).
