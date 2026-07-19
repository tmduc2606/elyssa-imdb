import { Link } from "react-router";

const footerLinks = [
  {
    heading: "Browse",
    links: [
      { label: "Movies", to: "/browse?type=movie" },
      { label: "TV Series", to: "/browse?type=tvSeries" },
      { label: "Top Rated", to: "/browse/top-rated" },
    ],
  },
  {
    heading: "Connect",
    links: [
      { label: "GitHub", to: "https://github.com/anomalyco/elyssa-frontend" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="border-t border-border bg-surface">
      <div className="mx-auto max-w-7xl px-4 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {footerLinks.map((group) => (
            <div key={group.heading}>
              <p className="mb-3 text-sm font-medium text-foreground">
                {group.heading}
              </p>
              <ul className="flex flex-col gap-2" aria-label={group.heading}>
                {group.links.map((link) => (
                  <li key={link.label}>
                    {link.to.startsWith("http") ? (
                      <a
                        href={link.to}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-muted transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </a>
                    ) : (
                      <Link
                        to={link.to}
                        className="text-sm text-muted transition-colors hover:text-foreground"
                      >
                        {link.label}
                      </Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <div className="mt-10 border-t border-border pt-6 text-center text-xs text-muted">
          <p>Data sourced from IMDb. Not affiliated with IMDb.</p>
        </div>
      </div>
    </footer>
  );
}
