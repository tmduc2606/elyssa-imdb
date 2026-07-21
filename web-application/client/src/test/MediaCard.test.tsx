import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, it, expect, vi } from "vitest";
import { MediaCard } from "@/components/composites/MediaCard";

vi.mock("@/hooks/usePreloadOnHover", () => ({
  usePreloadOnHover: () => ({
    preload: vi.fn(),
    cancelPreload: vi.fn(),
  }),
}));

function renderWithRouter(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("MediaCard", () => {
  const baseProps = {
    id: "tt0133093",
    title: "The Matrix",
  };

  it("renders the title in the heading", () => {
    renderWithRouter(<MediaCard {...baseProps} />);
    expect(screen.getByRole("heading", { name: "The Matrix" })).toBeInTheDocument();
  });

  it("links to the title detail page", () => {
    renderWithRouter(<MediaCard {...baseProps} />);
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/title/tt0133093");
  });

  it("renders year when provided", () => {
    renderWithRouter(<MediaCard {...baseProps} year={1999} />);
    expect(screen.getByText("1999")).toBeInTheDocument();
  });

  it("does not render year when not provided", () => {
    renderWithRouter(<MediaCard {...baseProps} />);
    expect(screen.queryByText("1999")).not.toBeInTheDocument();
  });

  it("renders rating badge when rating is provided", () => {
    renderWithRouter(<MediaCard {...baseProps} rating={8.7} />);
    expect(screen.getByText("8.7")).toBeInTheDocument();
  });

  it("does not render rating badge when rating is null", () => {
    renderWithRouter(<MediaCard {...baseProps} rating={null} />);
    expect(screen.queryByText(/^\d\.\d$/)).not.toBeInTheDocument();
  });

  it("renders genre tags when genres are provided", () => {
    renderWithRouter(<MediaCard {...baseProps} genres={["Action", "Sci-Fi"]} />);
    expect(screen.getByText("Action")).toBeInTheDocument();
  });

  it("does not render genre tags when genres are empty", () => {
    renderWithRouter(<MediaCard {...baseProps} genres={[]} />);
    expect(screen.queryByText("Action")).not.toBeInTheDocument();
  });

  it("renders a placeholder when no poster", () => {
    renderWithRouter(<MediaCard {...baseProps} />);
    const texts = screen.getAllByText("The Matrix");
    expect(texts.length).toBe(2); // placeholder span + h3 heading
  });

  it("renders poster image when posterUrl is provided", () => {
    renderWithRouter(
      <MediaCard {...baseProps} posterUrl="https://example.com/poster.jpg" />,
    );
    const img = screen.getByAltText("The Matrix") as HTMLImageElement;
    expect(img).toBeInTheDocument();
    expect(img.src).toBe("https://example.com/poster.jpg");
  });

  it("applies additional className", () => {
    renderWithRouter(
      <MediaCard {...baseProps} className="custom-class" />,
    );
    const link = screen.getByRole("link");
    expect(link.className).toContain("custom-class");
  });

  it("has accessible label", () => {
    renderWithRouter(<MediaCard {...baseProps} />);
    expect(screen.getByLabelText("View details for The Matrix")).toBeInTheDocument();
  });
});
