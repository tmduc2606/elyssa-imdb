import { PageHeader } from "@/components/composites/PageHeader";
import { FeaturedCarousel } from "@/components/features/home/FeaturedCarousel";
import { TrendingRow } from "@/components/features/home/TrendingRow";
import { TopRatedRow } from "@/components/features/home/TopRatedRow";
import { GenreQuickLinks } from "@/components/features/home/GenreQuickLinks";
import type { TitleSummary } from "@/lib/types";

const placeholderTitles: TitleSummary[] = [];
const placeholderFeatured: TitleSummary[] = [];

export function Home() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader
        title="Discover"
        description="Explore the world of cinema through data."
      />
      <div className="mt-8 flex flex-col gap-12">
        <FeaturedCarousel titles={placeholderFeatured} />
        <TrendingRow titles={placeholderTitles} />
        <TopRatedRow titles={placeholderTitles} />
        <GenreQuickLinks />
      </div>
    </div>
  );
}
