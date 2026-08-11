import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi } from "vitest";
import { CastList } from "@/components/features/title/CastList";
import type { TitlePrincipal } from "@/lib/types";

vi.mock("@/hooks/usePreloadOnHover", () => ({
  usePreloadOnHover: () => ({
    preload: vi.fn(),
    cancelPreload: vi.fn(),
  }),
}));

function renderCast(cast: TitlePrincipal[], crew: TitlePrincipal[] = []) {
  return render(
    <MemoryRouter>
      <CastList cast={cast} crew={crew} />
    </MemoryRouter>,
  );
}

function person(id: string, name: string | null) {
  return { id, primaryName: name, headshotUrl: null, posterUrl: null };
}

const actor = (id: string, name: string | null): TitlePrincipal => ({
  person: person(`nm-${id}`, name),
  character: "Some Role",
  ordering: null,
  category: "actor",
  job: null,
});

const director = (id: string, name: string | null): TitlePrincipal => ({
  person: person(`nm-${id}`, name),
  character: null,
  ordering: null,
  category: "director",
  job: null,
});

describe("CastList", () => {
  it("renders known actors as cards with their character", () => {
    renderCast([actor("a1", "Keanu Reeves")]);
    expect(screen.getByText("Keanu Reeves")).toBeInTheDocument();
    expect(screen.getByText("Some Role")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Keanu Reeves" })).toHaveAttribute(
      "href",
      "/person/nm-a1",
    );
  });

  it("hides unknown actors entirely (Q1)", () => {
    renderCast([actor("known", "Keanu Reeves"), actor("unknown", null)]);
    expect(screen.getByText("Keanu Reeves")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Keanu Reeves" })).toBeInTheDocument();
    expect(screen.queryByText("Details coming soon")).not.toBeInTheDocument();
  });

  it("keeps unknown crew with a placeholder (Q1)", () => {
    renderCast([], [director("d1", "The Wachowskis"), director("d2", null)]);
    const directors = screen.getByRole("region", { name: "Directors" });
    expect(within(directors).getByText("The Wachowskis")).toBeInTheDocument();
    expect(within(directors).getByText("Details coming soon")).toBeInTheDocument();
  });

  it("collapses cast beyond the preview and expands on demand", async () => {
    const cast = Array.from({ length: 7 }, (_, i) => actor(`a${i}`, `Actor ${i + 1}`));
    renderCast(cast);

    expect(screen.queryByText("Actor 7")).not.toBeInTheDocument();
    const toggle = screen.getByRole("button", { name: /view all 7 cast members/i });
    await userEvent.click(toggle);

    expect(screen.getByText("Actor 7")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show less/i })).toBeInTheDocument();
  });

  it("renders nothing when there is no cast and no crew", () => {
    const { container } = renderCast([]);
    expect(container).toBeEmptyDOMElement();
  });
});
