import Link from "next/link";

const POINTS = [
  {
    title: "Praca bez nazwisk",
    text: "Zanim tekst pracy trafi do dostawcy, Corvus zamienia imię i nazwisko studenta, promotora, numer albumu i adresy email na znaczniki — na stronie tytułowej, w oświadczeniu, w treści i w notatkach. Do katalogów bibliotek idą tylko opisy pozycji.",
  },
  {
    title: "Twój klucz",
    text: "Akcje działają na kluczu promotora do Claude albo OpenAI, wybieranym przy każdej akcji. Corvus nie ma własnego modelu.",
  },
  {
    title: "Przechowywanie",
    text: "Klucz jest zaszyfrowany i nie trafia do logów ani odpowiedzi API. Pliki prac usuwa retencja.",
  },
  {
    title: "Akceptacja",
    text: "Wynik akcji to szkic. Do akt studenta trafia dopiero po akceptacji promotora.",
  },
];

export default function DataAndKeys() {
  return (
    <section
      id="dane"
      className="mx-auto max-w-[1280px] scroll-mt-6 px-4 pb-20 sm:px-8 lg:px-16"
    >
      <div className="flex flex-col gap-10 rounded-[20px] border border-line bg-surface-alt p-8 sm:p-12 lg:flex-row">
        <div className="flex-1">
          <h2 className="font-serif text-[26px] font-semibold text-foreground">
            Dane i klucze
          </h2>
          <p className="mt-4 max-w-[460px] text-[15px] leading-relaxed text-muted-strong">
            Corvus to prywatne narzędzie, używane przez kilka osób. Konta
            zakłada administrator. Jeśli prowadzisz albo recenzujesz prace
            dyplomowe i chcesz z niego korzystać,{" "}
            <Link
              href="/login?tab=request"
              className="text-accent underline underline-offset-4 hover:text-accent-hover"
            >
              zostaw adres email
            </Link>
            .
          </p>
        </div>
        <div className="grid flex-[1.3] grid-cols-1 gap-x-8 gap-y-6 sm:grid-cols-2">
          {POINTS.map((p) => (
            <div key={p.title}>
              <p className="mb-1.5 text-[14px] font-semibold text-foreground">
                {p.title}
              </p>
              <p className="text-[13.5px] leading-relaxed text-muted-strong">
                {p.text}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
