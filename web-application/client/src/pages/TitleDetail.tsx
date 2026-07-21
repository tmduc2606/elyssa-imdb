import { useParams } from "react-router";
import { BreadcrumbNav } from "@/components/composites/BreadcrumbNav";
import { TitleHero } from "@/components/features/title/TitleHero";
import { CastList } from "@/components/features/title/CastList";
import { EpisodeTable } from "@/components/features/title/EpisodeTable";
import { SimilarTitlesRow } from "@/components/features/title/SimilarTitlesRow";
import { RatingTimelineChart } from "@/components/features/title/RatingTimelineChart";
import { TitleStatsPanel } from "@/components/features/title/TitleStatsPanel";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { useTitleDetail, useTitleRatings } from "@/api/gold";

export function TitleDetail() {
  const { tconst } = useParams();
  const { data, isLoading } = useTitleDetail(tconst ?? "");
  const { data: ratingsData } = useTitleRatings(tconst ?? "");

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <SkeletonGrid count={6} />
      </div>
    );
  }

  if (!data?.title) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-8">
        <p className="text-muted">Title not found.</p>
      </div>
    );
  }

  const title = data.title;
  const cast = title.cast ?? [];
  const episodes = title.episodes ?? [];
  const similar = title.similar ?? [];
  const ratings = ratingsData?.titleRatings ?? [];

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
