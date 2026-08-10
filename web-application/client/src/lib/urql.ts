import {
  createClient,
  cacheExchange,
  fetchExchange,
  makeOperation,
  type Operation,
  type Exchange,
  type CombinedError,
} from "urql";
import {
  pipe,
  mergeMap,
  merge,
  fromValue,
  empty,
  makeSubject,
} from "wonka";
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
 * authApi) and replay the failed operations through this exchange itself.
 *
 * Two constraints drive the design:
 *
 * 1. urql composes exchanges once per client and throws "forward() must only
 *    be called once in each Exchange" if any exchange invokes its `forward`
 *    more than once — ever. `forward` is therefore wired ONCE over a stream
 *    that merges the client's operations with a local retry subject.
 * 2. `client.reexecuteOperation` silently drops operations whose key is no
 *    longer in its internal `active` map, which (race-prone) makes it
 *    unsuitable for result-driven retries. The retried operation is instead
 *    pushed into the retry subject and flows through the same single
 *    pipeline like a normal operation.
 *
 * The UNAUTHENTICATED result is suppressed while a refresh is in flight;
 * failed operations are queued and re-dispatched once (marked
 * `retriedOnce`), so a genuinely dead session surfaces the real GraphQL
 * error without looping or flashing errors mid-refresh.
 */
export function authRetryExchange(): Exchange {
  return ({ forward }) => {
    const retries = makeSubject<Operation>();
    let retryQueue = new Map<number, Operation>();
    let refreshing: Promise<unknown> | null = null;

    function flushRetries() {
      refreshing = null;
      const queue = retryQueue;
      retryQueue = new Map();
      queue.forEach(retries.next);
    }

    return (ops$) => {
      const opsWithRetries$ = merge([retries.source, ops$]);
      return pipe(
        forward(opsWithRetries$),
        mergeMap((result) => {
          const op = result.operation;
          if (
            (op.kind !== "query" && op.kind !== "mutation") ||
            !result.error ||
            !isUnauthenticated(result.error) ||
            (op.context as RetriedContext).retriedOnce
          ) {
            return fromValue(result);
          }
          const retriedOp = makeOperation(op.kind, op, {
            ...op.context,
            retriedOnce: true,
          });
          retryQueue.set(op.key, retriedOp);
          if (!refreshing) {
            refreshing = refreshAccessToken().then(flushRetries).catch(flushRetries);
          }
          return empty;
        }),
      );
    };
  };
}

export const goldClient = createClient({
  url: API_URL,
  fetchOptions: () => ({
    headers: getAuthHeaders(),
  }),
  exchanges: [cacheExchange, authRetryExchange(), fetchExchange],
});