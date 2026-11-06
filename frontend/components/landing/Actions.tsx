import {
  IconBooks,
  IconBulb,
  IconClipboardCheck,
  IconFileCheck,
  IconFileText,
  IconFileUpload,
  IconFlask,
  IconMail,
  IconMessageQuestion,
  IconNotes,
  IconTrendingUp,
} from "@tabler/icons-react";
import type { FC } from "react";

interface Tile {
  Icon: FC<{ size?: number; stroke?: number; "aria-hidden"?: boolean }>;
  title: string;
  description: string;
}

const REVIEW: Tile[] = [
  {
    Icon: IconFileCheck,
    title: "Recenzja finalna",
    description:
      "Szkic oceny zaakceptowanej wersji, z punktacją według rubryki uczelni, do wklejenia w system.",
  },
  {
    Icon: IconClipboardCheck,
    title: "Recenzja próbna",
    description:
      "Ta sama analiza najnowszej wersji, ale z listą tego, co poprawić przed złożeniem.",
  },
  {
    Icon: IconFlask,
    title: "Ocena metodologii",
    description:
      "Uwagi do metody, próby i źródeł. Uwaga bez cytatu z pracy nie przechodzi.",
  },
  {
    Icon: IconBooks,
    title: "Sprawdzenie bibliografii",
    description:
      "Czy pozycje istnieją: Crossref, Biblioteka Narodowa, Open Library. Na zewnątrz idą tylko opisy.",
  },
  {
    Icon: IconFileUpload,
    title: "Jednorazowa recenzja",
    description:
      "Praca, którą tylko recenzujesz: wgrywasz plik, bez zakładania studenta.",
  },
];

const MENTORING: Tile[] = [
  {
    Icon: IconBulb,
    title: "Propozycja tematu",
    description:
      "Kilka tematów z kierunku studiów i notatek z pierwszych spotkań.",
  },
  {
    Icon: IconNotes,
    title: "Notatka ze spotkania",
    description: "Skrótowe punkty rozwinięte w notatkę do akt studenta.",
  },
  {
    Icon: IconFileText,
    title: "Feedback do fragmentu",
    description:
      "Łagodne uwagi do rozdziału w trakcie pisania, bez punktów. Kolejna runda pamięta poprzednią.",
  },
  {
    Icon: IconTrendingUp,
    title: "Sprawdzenie postępu",
    description:
      "Co się zmieniło między dwiema wersjami, na tle notatek ze spotkań.",
  },
  {
    Icon: IconMail,
    title: "Mail do studenta",
    description:
      "Lista poprawek z recenzji próbnej, do skopiowania. Corvus niczego nie wysyła.",
  },
  {
    Icon: IconMessageQuestion,
    title: "Pytania na obronę",
    description: "Krótkie, ogólne pytania do zadania na egzaminie.",
  },
];

function Group({
  id,
  title,
  lead,
  tiles,
}: {
  id: string;
  title: string;
  lead: string;
  tiles: Tile[];
}) {
  return (
    <section
      id={id}
      className="mx-auto max-w-[1280px] scroll-mt-6 px-4 pb-20 sm:px-8 lg:px-16"
    >
      <h2 className="font-serif text-[26px] font-semibold text-foreground">
        {title}
      </h2>
      <p className="mt-2 max-w-[640px] text-[15px] leading-relaxed text-muted-strong">
        {lead}
      </p>
      <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {tiles.map(({ Icon, title: name, description }) => (
          <div
            key={name}
            className="rounded-xl border border-line bg-surface p-6"
          >
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-[10px] bg-accent-soft text-accent">
              <Icon size={20} stroke={1.75} aria-hidden />
            </div>
            <p className="mb-1.5 text-[16px] font-semibold text-foreground">
              {name}
            </p>
            <p className="text-[13.5px] leading-[1.55] text-muted-strong">
              {description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Actions() {
  return (
    <>
      <Group
        id="recenzja"
        title="Recenzja"
        lead="Analiza struktury, metodologii, zgodności z wymogami i spójności wniosków, rozdział po rozdziale. Progi liczbowe z wytycznych sprawdza kod, a nie model."
        tiles={REVIEW}
      />
      <Group
        id="prowadzenie"
        title="Prowadzenie pracy"
        lead="Lista studentów, notatki ze spotkań, fragmenty i kolejne wersje pracy na jednej osi czasu. Akcje piszą szkice na tym materiale."
        tiles={MENTORING}
      />
    </>
  );
}
