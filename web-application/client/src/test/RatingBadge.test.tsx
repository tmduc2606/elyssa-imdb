import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RatingBadge } from "@/components/composites/RatingBadge";

describe("RatingBadge", () => {
  it("renders null when rating is null", () => {
    const { container } = render(<RatingBadge rating={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders null when rating is undefined", () => {
    const { container } = render(<RatingBadge rating={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it("renders the rating value formatted to 1 decimal", () => {
    render(<RatingBadge rating={8.73} />);
    expect(screen.getByText("8.7")).toBeInTheDocument();
  });

  it("renders the rating value with integer input", () => {
    render(<RatingBadge rating={9} />);
    expect(screen.getByText("9.0")).toBeInTheDocument();
  });

  it("sets aria-label with rating value", () => {
    render(<RatingBadge rating={7.5} />);
    expect(screen.getByLabelText("Rating: 7.5 out of 10")).toBeInTheDocument();
  });

  it("applies green color class for rating >= 8", () => {
    render(<RatingBadge rating={9.2} />);
    const badge = screen.getByLabelText(/Rating:/);
    expect(badge.className).toContain("green");
  });

  it("applies yellow color class for rating 6-7.9", () => {
    render(<RatingBadge rating={7.1} />);
    const badge = screen.getByLabelText(/Rating:/);
    expect(badge.className).toContain("yellow");
  });

  it("applies red color class for rating < 6", () => {
    render(<RatingBadge rating={4.5} />);
    const badge = screen.getByLabelText(/Rating:/);
    expect(badge.className).toContain("red");
  });

  it("applies sm size classes by default", () => {
    render(<RatingBadge rating={8.0} />);
    const badge = screen.getByLabelText(/Rating:/);
    expect(badge.className).toContain("text-[11px]");
  });

  it("applies md size classes when size=md", () => {
    render(<RatingBadge rating={8.0} size="md" />);
    const badge = screen.getByLabelText(/Rating:/);
    expect(badge.className).toContain("text-xs");
  });

  it("renders a star icon", () => {
    render(<RatingBadge rating={8.0} />);
    const star = document.querySelector("svg");
    expect(star).toBeInTheDocument();
  });
});
