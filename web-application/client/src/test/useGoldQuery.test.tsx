import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { useGoldQuery } from "@/hooks/useGoldQuery";
import type { ReactNode } from "react";

const mockQuery = vi.fn();

vi.mock("@/lib/urql", () => ({
  goldClient: {
    query: (...args: unknown[]) => ({
      toPromise: () => mockQuery(...args),
    }),
  },
}));

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  };
}

describe("useGoldQuery", () => {
  beforeEach(() => {
    mockQuery.mockReset();
  });

  it("returns data on successful query", async () => {
    mockQuery.mockResolvedValue({
      data: { title: { id: "tt0133093", primaryTitle: "The Matrix" } },
      error: undefined,
    });

    const { result } = renderHook(
      () =>
        useGoldQuery({
          query: "{ title(tconst: \"tt0133093\") { id primaryTitle } }",
          queryKey: ["title", "tt0133093"],
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      title: { id: "tt0133093", primaryTitle: "The Matrix" },
    });
  });

  it("throws error on failed query", async () => {
    mockQuery.mockResolvedValue({
      data: null,
      error: { message: "Network error" },
    });

    const { result } = renderHook(
      () =>
        useGoldQuery({
          query: "{ title(tconst: \"bad\") { id } }",
          queryKey: ["title", "bad"],
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toBe("Network error");
  });

  it("passes variables to the query", async () => {
    mockQuery.mockImplementation((_query: string, _vars: unknown) => {
      return Promise.resolve({
        data: { search: { items: [] } },
        error: undefined,
      });
    });

    renderHook(
      () =>
        useGoldQuery({
          query: "query Search($q: String!) { search(query: $q) { items { id } } }",
          variables: { q: "Matrix" },
          queryKey: ["search", "Matrix"],
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(mockQuery).toHaveBeenCalledWith(
        expect.any(String),
        { q: "Matrix" },
      );
    });
  });

  it("respects enabled option", () => {
    const { result } = renderHook(
      () =>
        useGoldQuery({
          query: "{ title(tconst: \"tt0133093\") { id } }",
          queryKey: ["title", "disabled"],
          enabled: false,
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.isFetching).toBe(false);
  });
});
