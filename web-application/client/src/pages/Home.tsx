import { PageHeader } from "@/components/composites/PageHeader";
import { FeaturedCarousel } from "@/components/features/home/FeaturedCarousel";
import { TrendingRow } from "@/components/features/home/TrendingRow";
import { TopRatedRow } from "@/components/features/home/TopRatedRow";
import { GenreQuickLinks } from "@/components/features/home/GenreQuickLinks";
import { SkeletonGrid } from "@/components/composites/SkeletonGrid";
import { useHomePage } from "@/api/gold";

export function Home() {
  const { data, isLoading } = useHomePage();

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <PageHeader
        title="Discover"
        description="Explore the world of cinema through data."
      />
      <div className="mt-8 flex flex-col gap-12">
        {isLoading ? (
          <SkeletonGrid count={10} />
        ) : (
          <>
            <FeaturedCarousel titles={data?.featured ?? []} />
            <TrendingRow titles={data?.trending ?? []} />
            <TopRatedRow titles={data?.topRated ?? []} />
          </>
        )}
        <GenreQuickLinks />
      </div>
    </div>
  );
}
