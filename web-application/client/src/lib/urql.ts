import {
  createClient,
  cacheExchange,
  fetchExchange,
  makeOperation,
  type Operation,
  type Exchange,
  type CombinedError,
} from "urql";
import { pipe, mergeMap, fromPromise, fromArray, take, fromValue } from "wonka";
import { API_URL } from "./constants";
import { refreshAccessToken } from "./authApi";

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

function getAuthHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

function isUnauthenticated(error: CombinedError): boolean {
  return error.graphQLErrors.some(
    (e) => (e.extensions?.code as string) === "UNAUTHENTICATED",
  );
}

interface RetriedContext {
  retriedOnce?: boolean;
}

/**
 * On UNAUTHENTICATED responses, refresh the session once (single-flight in
 * authApi) and replay the failed operation. Each operation retries at most
 * once (tracked in its context), so a genuinely dead session still surfaces
 * the GraphQL error instead of looping.
 */
function authRetryExchange(): Exchange {
  return ({ forward }) =>
    (ops$) =>
      pipe(
        ops$,
        mergeMap((op: Operation) => {
          if (
            (op.context as RetriedContext).retriedOnce ||
            (op.kind !== "query" && op.kind !== "mutation")
          ) {
            return forward(fromArray([op]));
          }
          return pipe(
            forward(fromArray([op])),
            take(1),
            mergeMap((result) => {
              if (result.error && isUnauthenticated(result.error)) {
                const retriedOp = makeOperation(op.kind, op, {
                  ...op.context,
                  retriedOnce: true,
                });
                return pipe(
                  fromPromise(refreshAccessToken()),
                  mergeMap((ok) => (ok ? forward(fromArray([retriedOp])) : fromValue(result))),
                  take(1),
                );
              }
              return fromValue(result);
            }),
          );
        }),
      );
}

export const goldClient = createClient({
  url: API_URL,
  fetchOptions: () => ({
    headers: getAuthHeaders(),
  }),
  exchanges: [cacheExchange, authRetryExchange(), fetchExchange],
});