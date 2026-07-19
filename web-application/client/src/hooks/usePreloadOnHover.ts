import { useCallback, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { goldClient } from "@/lib/urql";
import { TITLE_DETAIL_QUERY } from "@/api/gold";

export function usePreloadOnHover() {
  const queryClient = useQueryClient();
  const timerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const preload = useCallback(
    (tconst: string) => {
      timerRef.current = setTimeout(() => {
        queryClient.prefetchQuery({
          queryKey: ["title", tconst],
          queryFn: async () => {
            const result = await goldClient
              .query(TITLE_DETAIL_QUERY, { tconst })
              .toPromise();
            return result.data;
          },
          staleTime: 1000 * 60,
        });
      }, 200);
    },
    [queryClient],
  );

  const cancelPreload = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
  }, []);

  return { preload, cancelPreload };
}
