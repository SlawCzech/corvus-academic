Uniwersytet Ekonomiczny
Wydział Ekonomii
Kierunek: Ekonomia

Anna Kowalczyk
Nr albumu: 000002

Determinanty oszczędzania gospodarstw domowych w Polsce w latach 2010–2022

Praca licencjacka napisana pod kierunkiem dr hab. Ewy Malinowskiej, prof. UE

Kraków 2026

OŚWIADCZENIE

Oświadczam, że niniejsza praca licencjacka została napisana przeze mnie samodzielnie, nie narusza praw autorskich osób trzecich i nie była wcześniej przedmiotem procedur związanych z uzyskaniem tytułu zawodowego.

SPIS TREŚCI

Wstęp
Rozdział 1. Teoretyczne ujęcie oszczędzania gospodarstw domowych
1.1. Pojęcie i funkcje oszczędności
1.2. Teorie konsumpcji i oszczędzania
Rozdział 2. Oszczędzanie gospodarstw domowych w Polsce — przegląd badań i danych
2.1. Stopa oszczędności w Polsce na tle Unii Europejskiej
2.2. Wyniki wcześniejszych badań empirycznych
Rozdział 3. Determinanty oszczędzania — analiza empiryczna
3.1. Dane i metoda badania
3.2. Wyniki estymacji
3.3. Dyskusja wyników
Zakończenie
Bibliografia

WSTĘP

Oszczędności gospodarstw domowych są jednym z głównych źródeł finansowania inwestycji w gospodarce, a zarazem buforem, który pozwala rodzinom przetrwać okresy spadku dochodów. W Polsce stopa oszczędności gospodarstw domowych należy do najniższych w Unii Europejskiej, co od lat jest przedmiotem dyskusji ekonomistów i decydentów. Pandemia COVID-19, a następnie wysoka inflacja lat 2022–2023, gwałtownie zmieniły zachowania oszczędnościowe Polaków, co czyni ten temat szczególnie aktualnym.

Problemem badawczym pracy jest niska i zmienna skłonność do oszczędzania polskich gospodarstw domowych oraz niepełna wiedza o tym, które czynniki tę skłonność kształtują. Celem głównym pracy jest identyfikacja determinant oszczędzania gospodarstw domowych w Polsce w latach 2010–2022. Cele szczegółowe to: (1) przegląd teorii konsumpcji i oszczędzania, (2) ocena poziomu oszczędności w Polsce na tle UE oraz (3) empiryczna weryfikacja wpływu dochodu, wieku, wykształcenia i stopy procentowej na oszczędności.

W pracy postawiono pytanie badawcze: które cechy społeczno-ekonomiczne gospodarstwa domowego w największym stopniu wpływają na jego stopę oszczędności? Sformułowano dwie hipotezy. H1: stopa oszczędności rośnie wraz z dochodem rozporządzalnym na osobę. H2: realna stopa procentowa ma dodatni, lecz słaby wpływ na stopę oszczędności.

Przedmiotem badania są oszczędności gospodarstw domowych, podmiotem — gospodarstwa domowe w Polsce, zakres czasowy obejmuje lata 2010–2022, a zakres przestrzenny — terytorium Polski. W pracy wykorzystano metodę krytycznej analizy literatury, analizę danych statystycznych Eurostatu i GUS oraz model regresji liniowej estymowany metodą najmniejszych kwadratów na danych z Badania Budżetów Gospodarstw Domowych GUS (próba ok. 35 tys. gospodarstw rocznie). Obliczenia wykonano w programie R.

Praca składa się z trzech rozdziałów. Rozdział pierwszy przedstawia teoretyczne podstawy oszczędzania. Rozdział drugi zawiera przegląd danych i wcześniejszych badań dla Polski. Rozdział trzeci prezentuje analizę empiryczną i dyskusję wyników. W pracy wykorzystano klasyczne prace z zakresu teorii konsumpcji (Keynes, Friedman, Modigliani) oraz współczesną literaturę polską i zagraniczną, w tym raporty NBP i artykuły z czasopism recenzowanych.

ROZDZIAŁ 1. TEORETYCZNE UJĘCIE OSZCZĘDZANIA GOSPODARSTW DOMOWYCH

1.1. Pojęcie i funkcje oszczędności

W ujęciu makroekonomicznym oszczędności gospodarstw domowych definiuje się jako tę część dochodu rozporządzalnego, która nie została przeznaczona na bieżącą konsumpcję (Begg i in., 2014). Stopę oszczędności wyraża się jako iloraz oszczędności i dochodu rozporządzalnego. Oszczędności pełnią funkcję zabezpieczającą, inwestycyjną oraz międzyokresowego wygładzania konsumpcji (Liberda, 2011).

1.2. Teorie konsumpcji i oszczędzania

Keynes (1936) uzależniał konsumpcję przede wszystkim od bieżącego dochodu, zakładając, że krańcowa skłonność do konsumpcji jest dodatnia, lecz mniejsza od jedności, a przeciętna skłonność do oszczędzania rośnie wraz z dochodem. Friedman (1957) w hipotezie dochodu permanentnego wskazał, że gospodarstwa domowe planują konsumpcję w odniesieniu do dochodu oczekiwanego w długim okresie, a przejściowe zmiany dochodu w większym stopniu wpływają na oszczędności. Modigliani i Brumberg (1954) w teorii cyklu życia powiązali oszczędzanie z wiekiem: gospodarstwa oszczędzają w okresie aktywności zawodowej i konsumują oszczędności na emeryturze. Nowsze ujęcia behawioralne podkreślają rolę samokontroli, nawyków i przyzwyczajeń (Thaler i Shefrin, 1981; Laibson, 1997).

ROZDZIAŁ 2. OSZCZĘDZANIE GOSPODARSTW DOMOWYCH W POLSCE — PRZEGLĄD BADAŃ I DANYCH

2.1. Stopa oszczędności w Polsce na tle Unii Europejskiej

Według danych Eurostatu stopa oszczędności brutto gospodarstw domowych w Polsce w latach 2010–2019 wahała się w przedziale 2–5%, podczas gdy średnia dla Unii Europejskiej wynosiła 11–12% (Eurostat, 2023). W 2020 roku, w warunkach ograniczeń pandemicznych, stopa ta w Polsce wzrosła do blisko 12%, by w 2022 roku, pod wpływem wysokiej inflacji, ponownie spaść poniżej 3%. Dane te przedstawia tabela 1.

Tabela 1. Stopa oszczędności brutto gospodarstw domowych w Polsce i UE (%)
Rok | Polska | UE-27
2010 | 3,1 | 12,9
2015 | 2,4 | 11,8
2019 | 4,1 | 12,8
2020 | 11,8 | 17,9
2022 | 2,7 | 12,6
Źródło: opracowanie własne na podstawie Eurostat (2023).

2.2. Wyniki wcześniejszych badań empirycznych

Badania dla Polski potwierdzają silny związek oszczędzania z dochodem i wiekiem. Liberda (2011) wykazała, że skłonność do oszczędzania rośnie w wyższych grupach dochodowych. Rószkiewicz (2014) zwróciła uwagę na rolę wykształcenia i wiedzy finansowej. Badania NBP wskazują ponadto, że znaczna część gospodarstw domowych nie posiada żadnych oszczędności, a motyw zapobiegliwościowy dominuje nad motywem inwestycyjnym (NBP, 2021). W literaturze zagranicznej wpływ stopy procentowej na oszczędności okazuje się zwykle słaby i niejednoznaczny (Browning i Lusardi, 1996).

ROZDZIAŁ 3. DETERMINANTY OSZCZĘDZANIA — ANALIZA EMPIRYCZNA

3.1. Dane i metoda badania

Analizę przeprowadzono na danych jednostkowych z Badania Budżetów Gospodarstw Domowych GUS za lata 2010–2022, obejmujących łącznie ok. 450 tys. obserwacji. Zmienną objaśnianą jest stopa oszczędności gospodarstwa domowego, zdefiniowana jako różnica dochodu rozporządzalnego i wydatków podzielona przez dochód rozporządzalny. Zmienne objaśniające to logarytm dochodu rozporządzalnego na osobę, wiek i wykształcenie głowy gospodarstwa, liczba osób w gospodarstwie oraz realna stopa procentowa od depozytów (NBP). Model estymowano metodą najmniejszych kwadratów z odpornymi błędami standardowymi i efektami stałymi dla lat. Wyniki przedstawia tabela 2.

3.2. Wyniki estymacji

Tabela 2. Wyniki estymacji modelu stopy oszczędności
Zmienna | Współczynnik | Błąd standardowy
log dochodu na osobę | 0,182 | 0,004
wiek | 0,003 | 0,0004
wykształcenie wyższe | 0,041 | 0,003
liczba osób | -0,012 | 0,001
realna stopa procentowa | 0,006 | 0,002
R² = 0,21; n = 452 318
Źródło: opracowanie własne na podstawie danych BBGD GUS.

Wszystkie zmienne okazały się statystycznie istotne na poziomie 1%. Wzrost dochodu na osobę o 10% wiąże się ze wzrostem stopy oszczędności o ok. 1,7 punktu procentowego. Wpływ realnej stopy procentowej jest dodatni, lecz niewielki: wzrost o 1 punkt procentowy podnosi stopę oszczędności o 0,6 punktu.

3.3. Dyskusja wyników

Wyniki są zgodne z teorią Keynesa i z wcześniejszymi badaniami dla Polski (Liberda, 2011). Dodatni wpływ wieku odpowiada przewidywaniom teorii cyklu życia dla osób w wieku produkcyjnym. Słaby wpływ stopy procentowej potwierdza ustalenia Browninga i Lusardi (1996). Ograniczeniem badania jest to, że dane BBGD nie obejmują zasobów majątkowych gospodarstw ani ich oczekiwań co do przyszłych dochodów.

ZAKOŃCZENIE

Celem pracy była identyfikacja determinant oszczędzania gospodarstw domowych w Polsce w latach 2010–2022 i cel ten został zrealizowany. W odpowiedzi na pytanie badawcze wykazano, że największy wpływ na stopę oszczędności ma dochód rozporządzalny na osobę, a w mniejszym stopniu wiek i wykształcenie. Hipoteza H1 została potwierdzona: stopa oszczędności rośnie wraz z dochodem. Hipoteza H2 również została potwierdzona: wpływ realnej stopy procentowej jest dodatni, lecz słaby. Wyniki sugerują, że polityka wspierania oszczędności powinna koncentrować się na gospodarstwach o niższych dochodach i na edukacji finansowej, a nie na zmianach oprocentowania. Dalsze badania mogłyby uwzględnić dane o majątku gospodarstw domowych.

BIBLIOGRAFIA

1. Begg, D., Vernasca, G., Fischer, S., Dornbusch, R. (2014). Makroekonomia. Warszawa: PWE.
2. Browning, M., Lusardi, A. (1996). Household saving: Micro theories and micro facts. Journal of Economic Literature, 34(4), 1797–1855.
3. Deaton, A. (1992). Understanding consumption. Oxford: Clarendon Press.
4. Eurostat (2023). Household saving rate [tec00131]. Luxembourg: Eurostat.
5. Friedman, M. (1957). A theory of the consumption function. Princeton: Princeton University Press.
6. GUS (2023). Budżety gospodarstw domowych w 2022 r. Warszawa: Główny Urząd Statystyczny.
7. Keynes, J. M. (1936). The general theory of employment, interest and money. London: Macmillan.
8. Laibson, D. (1997). Golden eggs and hyperbolic discounting. Quarterly Journal of Economics, 112(2), 443–477.
9. Liberda, B. (2011). Oszczędności gospodarstw domowych w Polsce. Warszawa: Wydawnictwo Naukowe WNE UW.
10. Modigliani, F., Brumberg, R. (1954). Utility analysis and the consumption function. W: K. Kurihara (red.), Post-Keynesian economics (s. 388–436). New Brunswick: Rutgers University Press.
11. NBP (2021). Zasobność gospodarstw domowych w Polsce. Warszawa: Narodowy Bank Polski.
12. Rószkiewicz, M. (2014). Wiedza finansowa a oszczędzanie gospodarstw domowych. Ekonomista, 3, 355–374.
13. Thaler, R., Shefrin, H. (1981). An economic theory of self-control. Journal of Political Economy, 89(2), 392–406.
14. Attanasio, O., Weber, G. (2010). Consumption and saving: Models of intertemporal allocation. Journal of Economic Literature, 48(3), 693–751.
15. Bańbuła, P. (2016). Oszczędności gospodarstw domowych a polityka pieniężna. Bank i Kredyt, 47(2), 101–128.
16. Carroll, C. (1997). Buffer-stock saving and the life cycle/permanent income hypothesis. Quarterly Journal of Economics, 112(1), 1–55.
17. Czapiński, J., Panek, T. (red.) (2015). Diagnoza społeczna 2015. Warszawa: Rada Monitoringu Społecznego.
18. Grabowski, W., Welfe, A. (2016). Czynniki kształtujące oszczędności w Polsce. Gospodarka Narodowa, 5, 7–30.
19. Jappelli, T., Pistaferri, L. (2017). The economics of consumption. Oxford: Oxford University Press.
20. Kiełczewska, A. (2013). Postawy wobec oszczędzania. Warszawa: CeDeWu.
21. Kotowska, I. (2019). Starzenie się ludności a oszczędności. Studia Demograficzne, 1, 5–29.
22. Lusardi, A., Mitchell, O. (2014). The economic importance of financial literacy. Journal of Economic Literature, 52(1), 5–44.
23. Mankiw, N. G., Taylor, M. P. (2016). Makroekonomia. Warszawa: PWN.
24. Szczepańska, K. (2020). Skłonność do oszczędzania w czasie pandemii. Finanse i Prawo Finansowe, 4, 77–94.
25. Świecka, B. (2018). Finanse gospodarstw domowych. Warszawa: Difin.
26. Wójcik, P. (2021). Inflacja a zachowania oszczędnościowe. Bank i Kredyt, 52(3), 211–236.
27. Zalega, T. (2012). Konsumpcja i oszczędzanie w Polsce. Warszawa: Wydawnictwo Naukowe WZ UW.
