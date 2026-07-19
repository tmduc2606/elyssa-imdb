import { useQuery, type DefaultError, type QueryKey } from "@tanstack/react-query";
import { goldClient } from "@/lib/urql";

interface UseGoldQueryOptions {
  query: string;
  variables?: Record<string, unknown>;
  queryKey: QueryKey;
  staleTime?: number;
  enabled?: boolean;
}

export function useGoldQuery<TData = unknown>({
  query,
  variables,
  queryKey,
  staleTime,
  enabled = true,
}: UseGoldQueryOptions) {
  return useQuery<TData, DefaultError>({
    queryKey,
    staleTime,
    enabled,
    queryFn: async () => {
      const result = await goldClient.query(query, variables ?? {}).toPromise();
      if (result.error) {
        throw new Error(result.error.message);
      }
      return result.data as TData;
    },
  });
}
