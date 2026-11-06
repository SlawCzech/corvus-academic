/**
 * Regulamin Corvusa, z umową powierzenia przetwarzania danych (§ 5).
 *
 * Powierzenie idzie za klauzulami standardowymi Komisji Europejskiej między
 * administratorem a podmiotem przetwarzającym (decyzja wykonawcza 2021/915),
 * przyciętymi do umowy zawieranej kliknięciem. Liczby w § 6 i w załącznikach
 * opisują to, co robi kod: zmiana retencji, podwykonawców albo zabezpieczeń
 * to zmiana tego tekstu i nowa wersja w `version.ts`.
 */
import Link from "next/link"

import { Bullets, Items, Section } from "@/components/legal/Prose"
import type { Operator } from "@/content/legal/operator"
import { TERMS_DATE } from "@/content/legal/version"

export default function Terms({ operator }: { operator: Operator }) {
  return (
    <article>
      <h1 className="text-[24px] font-semibold text-foreground">Regulamin Corvusa</h1>
      <p className="mt-1 text-[13px] text-muted">Wersja z {TERMS_DATE}</p>

      <Section title="§ 1. Postanowienia ogólne">
        <Items>
          <li>
            Corvus to narzędzie wspierające promotorów i recenzentów prac dyplomowych, dostępne
            pod adresem tej strony (dalej: <strong>Serwis</strong>).
          </li>
          <li>
            Serwis prowadzi {operator.name}, kontakt: {operator.email} (dalej:{" "}
            <strong>Usługodawca</strong>).
          </li>
          <li>
            Serwis jest bezpłatny i prywatny. Konta zakłada Usługodawca; Serwis nie jest
            świadczony w ramach działalności gospodarczej.
          </li>
          <li>
            <strong>Użytkownik</strong> to osoba z kontem promotora, która zaakceptowała
            Regulamin. <strong>Dane studentów</strong> to dane osobowe, które Użytkownik wprowadza
            do Serwisu w związku z opieką nad pracą dyplomową albo jej recenzją: dane studentów i
            osób wymienionych w pracach i notatkach.
          </li>
        </Items>
      </Section>

      <Section title="§ 2. Konto">
        <Items>
          <li>Konto zakłada Usługodawca na prośbę zainteresowanej osoby.</li>
          <li>
            Użytkownik chroni swoje hasło i nie udostępnia konta innym osobom. O podejrzeniu
            przejęcia konta niezwłocznie informuje Usługodawcę.
          </li>
          <li>
            Użytkownik może w każdej chwili zażądać usunięcia konta, pisząc na adres z § 1.
            Usunięcie konta usuwa Dane studentów wprowadzone przez Użytkownika.
          </li>
          <li>
            Usługodawca może zablokować albo usunąć konto, gdy Użytkownik narusza Regulamin, a
            także zakończyć prowadzenie Serwisu, uprzedzając o tym Użytkowników z co najmniej
            30-dniowym wyprzedzeniem, z wyjątkiem sytuacji, w których wymaga tego bezpieczeństwo
            danych.
          </li>
        </Items>
      </Section>

      <Section title="§ 3. Zasady korzystania">
        <Items>
          <li>
            Użytkownik wprowadza Dane studentów wyłącznie w związku z opieką nad pracą dyplomową
            albo jej recenzją i oświadcza, że ma do tego podstawę prawną i umocowanie, w tym wobec
            uczelni, w imieniu której działa.
          </li>
          <li>
            Użytkownik nie wprowadza danych szczególnych kategorii (art. 9 RODO), w szczególności
            danych o zdrowiu, ani danych o wyrokach skazujących — również w notatkach ze spotkań.
          </li>
          <li>
            Wyniki akcji AI są szkicami. Ocena pracy, treść recenzji i decyzje wobec studenta
            należą do Użytkownika, który odpowiada też za zgodność korzystania z narzędzi AI z
            zasadami swojej uczelni.
          </li>
          <li>Zabronione jest wprowadzanie treści bezprawnych i próby obejścia zabezpieczeń.</li>
        </Items>
      </Section>

      <Section title="§ 4. Dostawca modelu">
        <Items>
          <li>
            Akcje AI działają na kluczu API Użytkownika u wybranego przez niego dostawcy modelu
            (Anthropic albo OpenAI). Umowę z dostawcą zawiera Użytkownik i on ponosi jej koszty.
          </li>
          <li>
            Przekazanie danych dostawcy następuje na polecenie Użytkownika, przy każdej
            uruchomionej akcji, w ramach jego umowy z dostawcą. Dostawca nie jest podwykonawcą
            Usługodawcy.
          </li>
          <li>
            Przed wysłaniem Serwis zamienia imię i nazwisko autora i promotora, numer albumu i
            adresy e-mail na znaczniki. Pozostała treść pracy, notatek i ustaleń trafia do
            dostawcy bez zmian.
          </li>
          <li>
            Przy weryfikacji bibliografii do Crossref, Biblioteki Narodowej i Open Library trafiają
            wyłącznie opisy bibliograficzne, nigdy tekst pracy.
          </li>
        </Items>
      </Section>

      <Section title="§ 5. Powierzenie przetwarzania danych">
        <Items>
          <li>
            Akceptując Regulamin, Użytkownik — jako administrator Danych studentów albo w imieniu
            administratora, w szczególności uczelni — powierza Usługodawcy ich przetwarzanie na
            zasadach z art. 28 RODO. Ten paragraf i załączniki stanowią umowę powierzenia.
          </li>
          <li>
            <strong>Przedmiot i czas.</strong> Dane studentów wprowadzone do Serwisu, przez czas
            korzystania z konta, z zastrzeżeniem § 6.
          </li>
          <li>
            <strong>Charakter i cel.</strong> Przechowywanie, porządkowanie i analiza tekstu prac,
            notatek i wyników akcji AI, wyłącznie po to, by świadczyć Użytkownikowi usługę opisaną
            w Regulaminie.
          </li>
          <li>
            <strong>Kategorie osób.</strong> Studenci (autorzy prac) oraz osoby wymienione w pracach
            i notatkach, np. promotorzy i recenzenci.
          </li>
          <li>
            <strong>Rodzaje danych.</strong> Imię i nazwisko, kierunek, typ i temat pracy, obszar i
            cel badań, treść wersji i fragmentów pracy (ze stroną tytułową i danymi, które na niej
            są), notatki ze spotkań, wyniki akcji AI i daty kolejnych etapów pracy.
          </li>
          <li>
            Usługodawca:
            <Bullets>
              <li>
                przetwarza Dane studentów wyłącznie na udokumentowane polecenie Użytkownika —
                poleceniami są Regulamin i działania Użytkownika w Serwisie — chyba że obowiązek
                przetwarzania nakłada na niego prawo; o takim obowiązku informuje Użytkownika, o ile
                prawo tego nie zabrania;
              </li>
              <li>nie wykorzystuje Danych studentów do własnych celów;</li>
              <li>
                zapewnia, że osoby upoważnione do przetwarzania zobowiązały się do zachowania
                poufności;
              </li>
              <li>stosuje środki bezpieczeństwa opisane w Załączniku 1;</li>
              <li>
                pomaga Użytkownikowi odpowiadać na żądania osób, których dane dotyczą, i wywiązywać
                się z obowiązków z art. 32–36 RODO, w zakresie wynikającym z charakteru
                przetwarzania;
              </li>
              <li>
                zawiadamia Użytkownika o naruszeniu ochrony Danych studentów bez zbędnej zwłoki, nie
                później niż w ciągu 48 godzin od jego stwierdzenia, z informacjami, których
                Użytkownik potrzebuje do zgłoszenia naruszenia;
              </li>
              <li>
                udostępnia Użytkownikowi informacje niezbędne do wykazania zgodności z art. 28 RODO,
                w pierwszej kolejności przez odpowiedzi na pytania na piśmie, i umożliwia audyt w
                uzgodnionym, rozsądnym zakresie;
              </li>
              <li>
                po usunięciu konta albo zakończeniu prowadzenia Serwisu usuwa Dane studentów, z
                zastrzeżeniem kopii zapasowych opisanych w § 6.
              </li>
            </Bullets>
          </li>
          <li>
            <strong>Podwykonawcy.</strong> Użytkownik wyraża ogólną zgodę na korzystanie z
            podwykonawców wymienionych w Załączniku 2. O planowanej zmianie Usługodawca informuje z
            co najmniej 14-dniowym wyprzedzeniem; Użytkownik, który się nie zgadza, może usunąć
            konto. Usługodawca nakłada na podwykonawców obowiązki ochrony danych nie mniejsze niż
            własne.
          </li>
          <li>
            <strong>Miejsce przetwarzania.</strong> Serwer stoi w Kanadzie, objętej decyzją Komisji
            Europejskiej stwierdzającą odpowiedni stopień ochrony danych (decyzja 2002/2/WE).
            Zaszyfrowane kopie zapasowe są przechowywane zgodnie z Załącznikiem 2.
          </li>
          <li>
            Usługodawca odpowiada wobec osób, których dane dotyczą, na zasadach art. 82 RODO.
          </li>
        </Items>
      </Section>

      <Section title="§ 6. Przechowywanie i usuwanie">
        <Items>
          <li>
            Pliki i tekst wersji pracy innych niż zaakceptowana jako finalna są usuwane 14 dni po
            akceptacji wersji finalnej.
          </li>
          <li>
            Pliki i tekst wszystkich wersji i fragmentów pracy są usuwane 30 dni po zakończeniu
            opieki (status „Obroniony” albo „Archiwalny”), a w jednorazowej recenzji — 30 dni po
            jej utworzeniu. Zostaje ślad: numer wersji, data, nazwa pliku i liczba znaków.
          </li>
          <li>
            Notatki ze spotkań i wyniki akcji AI zostają do usunięcia studenta albo konta przez
            Użytkownika. Usunięcie studenta jest natychmiastowe i obejmuje wyniki zapisane po
            stronie modułu AI.
          </li>
          <li>
            Codzienne kopie zapasowe bazy są szyfrowane i przechowywane do 60 dni. Dane usunięte z
            Serwisu znikają z kopii najpóźniej po tym czasie.
          </li>
        </Items>
      </Section>

      <Section title="§ 7. Odpowiedzialność">
        <Items>
          <li>
            Serwis jest bezpłatny i udostępniany w takim stanie, w jakim jest. Usługodawca nie
            gwarantuje jego ciągłej dostępności ani poprawności wyników akcji AI.
          </li>
          <li>
            W najszerszym zakresie dopuszczalnym przez prawo Usługodawca nie odpowiada za szkody
            wynikłe z korzystania z wyników akcji AI, z przerw w działaniu Serwisu ani z utraty
            danych, z wyjątkiem szkód wyrządzonych umyślnie. Nie ogranicza to odpowiedzialności
            wobec osób, których dane dotyczą, z art. 82 RODO.
          </li>
          <li>
            Za podstawę prawną wprowadzenia Danych studentów i za zgodność korzystania z Serwisu z
            zasadami uczelni odpowiada Użytkownik.
          </li>
        </Items>
      </Section>

      <Section title="§ 8. Zmiany Regulaminu">
        <Items>
          <li>
            Nowa wersja Regulaminu obowiązuje od jej akceptacji. Do tego czasu Użytkownik nie ma
            dostępu do Danych studentów, ale może zażądać usunięcia konta.
          </li>
          <li>Serwis zapisuje, kto i kiedy zaakceptował którą wersję Regulaminu.</li>
        </Items>
      </Section>

      <Section title="§ 9. Postanowienia końcowe">
        <Items>
          <li>Regulamin podlega prawu polskiemu.</li>
          <li>
            Zasady przetwarzania danych Użytkowników opisuje{" "}
            <Link href="/privacy" className="text-accent underline underline-offset-4">
              polityka prywatności
            </Link>
            .
          </li>
        </Items>
      </Section>

      <Section title="Załącznik 1. Środki bezpieczeństwa">
        <Bullets>
          <li>
            Połączenia wyłącznie przez HTTPS. Na serwerze otwarte są tylko porty SSH, HTTP i HTTPS;
            baza danych i kolejka zadań nie są dostępne z internetu, a do serwera loguje się
            wyłącznie kluczem SSH.
          </li>
          <li>
            Hasła przechowywane jako skróty bcrypt; krótkie, odwoływalne sesje; limit prób
            logowania; zmiana hasła kończy wszystkie sesje.
          </li>
          <li>
            Klucze API Użytkowników szyfrowane w bazie, w kolejce zadań zaszyfrowane osobnym
            kluczem; nie trafiają do logów ani odpowiedzi.
          </li>
          <li>
            Rozdział ról: administrator Serwisu nie widzi studentów ani prac; każdy promotor widzi
            wyłącznie własnych studentów.
          </li>
          <li>Zamiana nazwisk na znaczniki przed wysłaniem tekstu do dostawcy modelu.</li>
          <li>
            Przesłane pliki są odczytywane w osobnym procesie z limitem czasu i pamięci.
          </li>
          <li>Automatyczne usuwanie plików i tekstu prac według § 6.</li>
          <li>
            Codzienna, szyfrowana kopia zapasowa poza serwerem, z przetestowanym odtwarzaniem;
            monitoring działania Serwisu i kopii.
          </li>
          <li>Regularne aktualizacje zależności i automatyczne testy przed każdym wdrożeniem.</li>
          <li>
            Usługodawca nie przegląda Danych studentów; z bazy danych korzysta wyłącznie na
            potrzeby utrzymania Serwisu.
          </li>
        </Bullets>
      </Section>

      <Section title="Załącznik 2. Podwykonawcy">
        <Bullets>
          <li>
            <strong>OVHcloud</strong> — serwer (VPS), centrum danych w Beauharnois, Kanada.
          </li>
          <li>
            <strong>Cloudflare, Inc.</strong> — przechowywanie zaszyfrowanych kopii zapasowych
            (Cloudflare R2, Europa Zachodnia). Cloudflare nie ma klucza do ich odszyfrowania.
          </li>
        </Bullets>
      </Section>
    </article>
  )
}
