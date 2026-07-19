import { useParams } from "react-router";
import { BreadcrumbNav } from "@/components/composites/BreadcrumbNav";
import { PersonBio } from "@/components/features/person/PersonBio";
import { KnownForGrid } from "@/components/features/person/KnownForGrid";
import { FilmographyList } from "@/components/features/person/FilmographyList";
import { CareerTimeline } from "@/components/features/person/CareerTimeline";
import { CollaborationNetwork } from "@/components/features/person/CollaborationNetwork";
import type { Person, TitleSummary, FilmographyEntry, Collaborator, CareerYear } from "@/lib/types";

const placeholderPerson: Person = {
  id: "",
  primaryName: "",
  birthYear: null,
  deathYear: null,
  primaryProfession: [],
  knownForTitles: [],
  posterUrl: null,
};

export function PersonDetail() {
  const { nconst } = useParams();
  const person = placeholderPerson;
  const knownFor: TitleSummary[] = [];
  const filmography: FilmographyEntry[] = [];
  const collaborators: Collaborator[] = [];
  const timeline: CareerYear[] = [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <BreadcrumbNav
        items={[
          { label: "Home", to: "/" },
          { label: "Person" },
          { label: nconst ?? "" },
        ]}
      />
      <div className="mt-6 flex flex-col gap-12">
        <PersonBio person={person} />
        <KnownForGrid titles={knownFor} />
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-2">
          <FilmographyList entries={filmography} />
          <div className="flex flex-col gap-12">
            <CareerTimeline timeline={timeline} />
            <CollaborationNetwork collaborators={collaborators} />
          </div>
        </div>
      </div>
    </div>
  );
}
