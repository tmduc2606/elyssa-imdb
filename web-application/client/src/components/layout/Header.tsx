import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router";
import { useTheme } from "next-themes";
import { Search, Menu, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  NavigationMenu,
  NavigationMenuList,
  NavigationMenuItem,
  NavigationMenuLink,
} from "@/components/ui/navigation-menu";
import {
  Sheet,
  SheetTrigger,
  SheetContent,
  SheetTitle,
  SheetHeader,
} from "@/components/ui/sheet";

const navLinks = [
  { label: "Browse", to: "/browse" },
  { label: "Top Rated", to: "/browse/top-rated" },
];

export function Header() {
  const navigate = useNavigate();
  const location = useLocation();
  const { theme, setTheme } = useTheme();
  const [sheetOpen, setSheetOpen] = useState(false);

  const isActive = (to: string) => {
    if (to === "/browse/top-rated") return location.pathname === to;
    return location.pathname.startsWith(to);
  };

  return (
    <header className="sticky top-0 z-50 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex h-14 max-w-7xl items-center gap-4 px-4">
        <Link
          to="/"
          className="font-display text-xl tracking-tight [-webkit-font-smoothing:auto]"
        >
          Elyssa
        </Link>

        <NavigationMenu className="hidden md:flex">
          <NavigationMenuList>
            {navLinks.map((link) => (
              <NavigationMenuItem key={link.to}>
                <NavigationMenuLink
                  href={link.to}
                  aria-current={isActive(link.to) ? "page" : undefined}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(link.to);
                  }}
                >
                  {link.label}
                </NavigationMenuLink>
              </NavigationMenuItem>
            ))}
          </NavigationMenuList>
        </NavigationMenu>

        <div className="flex-1" />

        <form
          role="search"
          className="hidden sm:block"
          onSubmit={(e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            const q = form.get("q") as string;
            if (q?.trim()) navigate(`/search?q=${encodeURIComponent(q.trim())}`);
          }}
        >
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              name="q"
              placeholder="Search titles, people..."
              className="w-56 pl-8 lg:w-72"
            />
          </div>
        </form>

        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          >
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/auth/login")}
            className="hidden sm:inline-flex"
          >
            Sign in
          </Button>

          <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
            <SheetTrigger
              className="inline-flex size-8 items-center justify-center rounded-md md:hidden hover:bg-muted"
              aria-label="Open menu"
            >
              <Menu className="size-5" />
            </SheetTrigger>
            <SheetContent side="right">
              <SheetHeader>
                <SheetTitle className="sr-only">Navigation</SheetTitle>
              </SheetHeader>
              <nav className="mt-8 flex flex-col gap-4">
                {navLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    aria-current={isActive(link.to) ? "page" : undefined}
                    className="text-lg"
                    onClick={() => setSheetOpen(false)}
                  >
                    {link.label}
                  </Link>
                ))}
                <Link
                  to="/auth/login"
                  className="text-lg"
                  onClick={() => setSheetOpen(false)}
                >
                  Sign in
                </Link>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
