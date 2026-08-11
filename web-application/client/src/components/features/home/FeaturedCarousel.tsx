import { useRef } from "react";
import { Link } from "react-router";
import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

import { RatingBadge } from "@/components/composites/RatingBadge";
import type { TitleSummary } from "@/lib/types";

gsap.registerPlugin(ScrollTrigger);

interface FeaturedCarouselProps {
  titles: TitleSummary[];
}

export function FeaturedCarousel({ titles }: FeaturedCarouselProps) {
  const sectionRef = useRef<HTMLElement>(null);

  useGSAP(() => {
    const cards = sectionRef.current?.querySelectorAll("[data-animate]");
    if (!cards?.length) return;
    gsap.fromTo(
      cards,
      { opacity: 0, y: 40 },
      {
        opacity: 1,
        y: 0,
        duration: 0.6,
        stagger: 0.1,
        ease: "power2.out",
        scrollTrigger: {
          trigger: sectionRef.current,
          start: "top 85%",
          toggleActions: "play none none reverse",
        },
      },
    );
  }, [titles]);

  if (titles.length === 0) return null;

  return (
    <section
      ref={sectionRef}
      aria-label="Featured titles"
      aria-roledescription="carousel"
      className="relative overflow-hidden rounded-xl bg-surface"
    >
      <div
        role="list"
        className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-4 pt-4"
      >
        {titles.map((title, index) => (
          <Link
            key={title.id}
            to={`/title/${title.id}`}
            role="listitem"
            aria-roledescription="slide"
            aria-label={`Slide ${index + 1}: ${title.primaryTitle}`}
            data-animate
            className="group relative w-36 shrink-0 sm:w-44 md:w-52 overflow-hidden rounded-lg border border-border"
          >
            <div className="aspect-[2/3] bg-muted relative">
              {title.posterUrl ? (
                <img
                  src={title.posterUrl}
                  alt={title.primaryTitle}
                  loading="lazy"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                  className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
                />
              ) : (
                <div className="flex size-full items-center justify-center bg-surface p-3">
                  <span className="text-center text-xs text-muted">{title.primaryTitle}</span>
                </div>
              )}
            </div>
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            <div className="absolute bottom-0 left-0 right-0 p-3 text-white">
              <h3 className="truncate text-sm font-semibold">{title.primaryTitle}</h3>
              <div className="mt-1 flex items-center gap-2">
                {title.averageRating != null && (
                  <RatingBadge rating={title.averageRating} />
                )}
                {title.startYear && (
                  <span className="text-xs text-white/80">{title.startYear}</span>
                )}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
