import {
  createClient,
  cacheExchange,
  fetchExchange,
  mapExchange,
} from "urql";
import { API_URL } from "./constants";

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

export const goldClient = createClient({
  url: API_URL,
  fetchOptions: () => ({
    headers: getAuthHeaders(),
  }),
  exchanges: [
    cacheExchange,
    mapExchange({
      onError(error) {
        const isAuthError = error.graphQLErrors.some(
          (e) => (e.extensions?.code as string) === "UNAUTHENTICATED",
        );
        if (isAuthError) {
          setAccessToken(null);
        }
      },
    }),
    fetchExchange,
  ],
});
