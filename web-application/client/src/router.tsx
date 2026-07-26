import { lazy, Suspense } from "react";
import { createBrowserRouter } from "react-router";
import { RootLayout } from "@/components/layout/RootLayout";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { ErrorBoundary } from "@/components/composites/ErrorBoundary";
import { ErrorFallback } from "@/components/composites/ErrorFallback";

function PageFallback() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
        {Array.from({ length: 12 }).map((_, i) => (
          <div key={i} className="flex animate-pulse flex-col gap-2">
            <div className="aspect-[2/3] w-full rounded-lg bg-muted" />
            <div className="h-4 w-3/4 rounded bg-muted" />
            <div className="h-3 w-1/2 rounded bg-muted" />
          </div>
        ))}
      </div>
    </div>
  );
}

function suspenseWrapper(Component: React.LazyExoticComponent<React.ComponentType>) {
  return (
    <ErrorBoundary fallback={<ErrorFallback message="Something went wrong loading this page." />}>
      <Suspense fallback={<PageFallback />}>
        <Component />
      </Suspense>
    </ErrorBoundary>
  );
}

const Home = lazy(() => import("@/pages/Home").then((m) => ({ default: m.Home })));
const Search = lazy(() => import("@/pages/Search").then((m) => ({ default: m.Search })));
const TitleDetail = lazy(() => import("@/pages/TitleDetail").then((m) => ({ default: m.TitleDetail })));
const PersonDetail = lazy(() => import("@/pages/PersonDetail").then((m) => ({ default: m.PersonDetail })));
const Browse = lazy(() => import("@/pages/Browse").then((m) => ({ default: m.Browse })));
const Watchlist = lazy(() => import("@/pages/Watchlist").then((m) => ({ default: m.Watchlist })));
const Account = lazy(() => import("@/pages/Account").then((m) => ({ default: m.Account })));
const Login = lazy(() => import("@/pages/Login").then((m) => ({ default: m.Login })));
const Register = lazy(() => import("@/pages/Register").then((m) => ({ default: m.Register })));
const NotFound = lazy(() => import("@/pages/NotFound").then((m) => ({ default: m.NotFound })));

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { index: true, element: suspenseWrapper(Home) },
      { path: "search", element: suspenseWrapper(Search) },
      { path: "title/:tconst", element: suspenseWrapper(TitleDetail) },
      { path: "person/:nconst", element: suspenseWrapper(PersonDetail) },
      { path: "browse", element: suspenseWrapper(Browse) },
      { path: "browse/genre/:slug", element: suspenseWrapper(Browse) },
      { path: "browse/decade/:year", element: suspenseWrapper(Browse) },
      { path: "browse/top-rated", element: suspenseWrapper(Browse) },
      {
        element: <RequireAuth />,
        children: [
          { path: "watchlist", element: suspenseWrapper(Watchlist) },
          { path: "account", element: suspenseWrapper(Account) },
        ],
      },
      { path: "auth/login", element: suspenseWrapper(Login) },
      { path: "auth/register", element: suspenseWrapper(Register) },
      { path: "*", element: suspenseWrapper(NotFound) },
    ],
  },
]);
