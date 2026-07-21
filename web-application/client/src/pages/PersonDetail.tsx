import { useParams } from "react-router";
import { BreadcrumbNav } from "@/components/composites/BreadcrumbNav";
import { PersonBio } from "@/components/features/person/PersonBio";
import { KnownForGrid } from "@/components/features/person/KnownForGrid";
import { FilmographyList } from "@/components/features/person/FilmographyList";
import { CareerTimeline } from "@/components/features/person/CareerTimeline";
import { CollaborationNetwork } from "@/components/features/person/CollaborationNetwork";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { usePersonDetail } from "@/api/gold";

export function PersonDetail() {
  const { nconst } = useParams();
  const { data, isLoading } = usePersonDetail(nconst ?? "");

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <SkeletonGrid count={6} />
      </div>
    );
  }

  if (!data?.person) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <p className="text-muted">Person not found.</p>
      </div>
    );
  }

  const person = data.person;
  const knownFor = person.knownForTitles ?? [];
  const filmography = person.filmography ?? [];
  const collaborators = person.collaborators ?? [];
  const timeline = person.careerTimeline ?? [];

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
