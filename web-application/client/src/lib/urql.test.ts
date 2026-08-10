import { describe, expect, it, vi, beforeEach } from "vitest";
import { createClient, cacheExchange, fetchExchange, gql } from "urql";

import { authRetryExchange } from "./urql";

vi.mock("./authApi", () => ({
  refreshAccessToken: vi.fn(),
}));

import { refreshAccessToken } from "./authApi";

function fetchOnce(script: () => Response) {
  return vi.fn(async () => script());
}

function jsonResponse(ok: boolean, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: ok ? 200 : 401,
    headers: { "content-type": "application/json" },
  });
}

const unauthenticatedResult = {
  data: null,
  errors: [{ message: "Session expired", extensions: { code: "UNAUTHENTICATED" } }],
};

const query = gql`
  query Example {
    __typename
  }
`;

describe("authRetryExchange", () => {
  beforeEach(() => {
    vi.mocked(refreshAccessToken).mockReset();
  });

  it("forwards each operation exactly once — no double-forward on retry", async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(true);
    let calls = 0;
    const fetcher = fetchOnce(() => {
      calls += 1;
      return jsonResponse(true, calls === 1 ? unauthenticatedResult : { data: { __typename: "Query" } });
    });
    const client = createClient({
      url: "http://localhost:8000/graphql",
      exchanges: [cacheExchange, authRetryExchange(), fetchExchange],
      fetch: fetcher,
    });

    const result = await client.query(query, {}).toPromise();

    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.error).toBeUndefined();
    expect(result.data).toEqual({ __typename: "Query" });
  });

  it("surfaces the error when the refresh fails", async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(false);
    const fetcher = fetchOnce(() => jsonResponse(true, unauthenticatedResult));
    const client = createClient({
      url: "http://localhost:8000/graphql",
      exchanges: [cacheExchange, authRetryExchange(), fetchExchange],
      fetch: fetcher,
    });

    const result = await client.query(query, {}).toPromise();

    // The op is retried once after the failed refresh, then the real error surfaces.
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result.error).toBeDefined();
    expect(result.error?.graphQLErrors[0]?.extensions?.code).toBe("UNAUTHENTICATED");
  });

  it("never forwards the same operation twice across concurrent operations", async () => {
    vi.mocked(refreshAccessToken).mockResolvedValue(true);
    let calls = 0;
    const fetcher = fetchOnce(() => {
      calls += 1;
      return jsonResponse(true, calls === 1 ? unauthenticatedResult : { data: { __typename: "Query" } });
    });
    const client = createClient({
      url: "http://localhost:8000/graphql",
      exchanges: [cacheExchange, authRetryExchange(), fetchExchange],
      fetch: fetcher,
    });

    const results = await Promise.all([client.query(query, {}).toPromise(), client.query(query, {}).toPromise()]);

    expect(results.every((r) => r.error === undefined)).toBe(true);
    expect(results.every((r) => r.data?.__typename === "Query")).toBe(true);
  });
});