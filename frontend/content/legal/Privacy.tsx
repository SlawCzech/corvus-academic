/**
 * Polityka prywatności: dane promotorów i osób proszących o konto, których
 * administratorem jest Usługodawca. Dane studentów opisuje regulamin (§ 5),
 * bo tam Usługodawca jest tylko podmiotem przetwarzającym.
 *
 * Okresy przechowywania opisują to, co robi kod: logi logowań 90 dni
 * (`identity/infrastructure/repositories.py`), kopie 60 dni (bucket R2).
 */
import Link from "next/link"

import { Bullets, Items, Section } from "@/components/legal/Prose"
import type { Operator } from "@/content/legal/operator"
import { TERMS_DATE } from "@/content/legal/version"

export default function Privacy({ operator }: { operator: Operator }) {
  return (
    <article>
      <h1 className="text-[24px] font-semibold text-foreground">Polityka prywatności</h1>
      <p className="mt-1 text-[13px] text-muted">Wersja z {TERMS_DATE}</p>

      <Section title="1. Administrator">
        <p>
          Administratorem danych opisanych poniżej jest {operator.name}, kontakt: {operator.email}.
        </p>
      </Section>

      <Section title="2. Jakie dane i po co">
        <Items>
          <li>
            <strong>Konto:</strong> adres e-mail, rola, skrót hasła, data założenia i zaakceptowane
            wersje regulaminu — aby prowadzić konto i świadczyć usługę (art. 6 ust. 1 lit. b RODO)
            oraz mieć dowód zawarcia umowy powierzenia (art. 6 ust. 1 lit. f).
          </li>
          <li>
            <strong>Logowania:</strong> adres e-mail, adres IP, przeglądarka, czas i wynik próby —
            aby chronić konta przed włamaniem i nadużyciami (art. 6 ust. 1 lit. f).
          </li>
          <li>
            <strong>Klucze API</strong> do dostawców modeli — zaszyfrowane, aby uruchamiać akcje na
            Twoje polecenie (art. 6 ust. 1 lit. b).
          </li>
          <li>
            <strong>Prośba o konto:</strong> adres e-mail podany w formularzu — aby ją rozpatrzyć
            (art. 6 ust. 1 lit. b, działania przed zawarciem umowy).
          </li>
          <li>
            <strong>Logi techniczne serwera:</strong> adres i wynik żądania, bez jego treści — aby
            utrzymać i naprawiać Serwis (art. 6 ust. 1 lit. f).
          </li>
        </Items>
      </Section>

      <Section title="3. Jak długo">
        <Bullets>
          <li>Dane konta — do jego usunięcia.</li>
          <li>Logi logowań — 90 dni.</li>
          <li>Prośba o konto — do jej rozpatrzenia.</li>
          <li>
            Kopie zapasowe bazy — do 60 dni, zaszyfrowane; dane usunięte z Serwisu znikają z kopii
            najpóźniej po tym czasie.
          </li>
        </Bullets>
      </Section>

      <Section title="4. Komu przekazujemy dane">
        <p>
          Dane przetwarzają w naszym imieniu: OVHcloud (serwer w Kanadzie, kraju z decyzją Komisji
          Europejskiej o odpowiednim stopniu ochrony danych) i Cloudflare (zaszyfrowane kopie
          zapasowe). Twój klucz API trafia do wybranego przez Ciebie dostawcy modelu (Anthropic albo
          OpenAI), gdy go zapisujesz i gdy uruchamiasz akcję — na podstawie Twojej umowy z tym
          dostawcą. Nie sprzedajemy danych ani nie używamy ich do reklamy.
        </p>
      </Section>

      <Section title="5. Twoje prawa">
        <p>
          Masz prawo dostępu do swoich danych, ich sprostowania, usunięcia, ograniczenia
          przetwarzania, przeniesienia oraz sprzeciwu wobec przetwarzania opartego na prawnie
          uzasadnionym interesie. Napisz na adres z punktu 1. Możesz też złożyć skargę do Prezesa
          Urzędu Ochrony Danych Osobowych.
        </p>
      </Section>

      <Section title="6. Ciasteczka i pamięć przeglądarki">
        <p>
          Serwis używa wyłącznie niezbędnych ciasteczek sesji (zalogowanie) i zapisuje w pamięci
          przeglądarki ustawienia interfejsu: motyw i domyślne ustawienia akcji. Nie ma analityki
          ani ciasteczek reklamowych.
        </p>
      </Section>

      <Section title="7. Dane studentów">
        <p>
          Dane studentów, które promotor wprowadza do Serwisu, przetwarzamy jako podmiot
          przetwarzający, na polecenie promotora — zasady opisuje{" "}
          <Link href="/terms" className="text-accent underline underline-offset-4">
            regulamin
          </Link>{" "}
          (§ 5 i § 6). Student, który chce skorzystać ze swoich praw, kieruje żądanie do promotora
          albo uczelni; pomagamy im je zrealizować.
        </p>
      </Section>
    </article>
  )
}
