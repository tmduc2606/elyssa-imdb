import { useParams } from "react-router";
import { BreadcrumbNav } from "@/components/composites/BreadcrumbNav";
import { TitleHero } from "@/components/features/title/TitleHero";
import { CastList } from "@/components/features/title/CastList";
import { EpisodeTable } from "@/components/features/title/EpisodeTable";
import { SimilarTitlesRow } from "@/components/features/title/SimilarTitlesRow";
import { RatingTimelineChart } from "@/components/features/title/RatingTimelineChart";
import { TitleStatsPanel } from "@/components/features/title/TitleStatsPanel";
import type { Title, TitlePrincipal, RatingSnapshot, TitleSummary, EpisodeContent } from "@/lib/types";

const placeholderTitle: Title = {
  id: "",
  primaryTitle: "",
  originalTitle: null,
  titleType: "movie",
  startYear: null,
  endYear: null,
  runtimeMinutes: null,
  genres: [],
  averageRating: null,
  numVotes: null,
  posterUrl: null,
  parentTconst: null,
  seriesTitle: null,
  seasonNumber: null,
  episodeNumber: null,
};

export function TitleDetail() {
  const { tconst } = useParams();
  const title = placeholderTitle;
  const cast: TitlePrincipal[] = [];
  const episodes: EpisodeContent[] = [];
  const similar: TitleSummary[] = [];
  const ratings: RatingSnapshot[] = [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <BreadcrumbNav
        items={[
          { label: "Home", to: "/" },
          { label: "Title", to: "/browse" },
          { label: tconst ?? "" },
        ]}
      />
      <div className="mt-6 flex flex-col gap-12">
        <TitleHero title={title} />
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <CastList cast={cast} />
          </div>
          <div>
            <TitleStatsPanel title={title} />
          </div>
        </div>
        <EpisodeTable episodes={episodes} />
        <RatingTimelineChart snapshots={ratings} />
        <SimilarTitlesRow titles={similar} />
      </div>
    </div>
  );
}
