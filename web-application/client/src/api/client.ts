import { authApiFetch } from "@/lib/authApi";

export async function apiPost<TBody, TResponse>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  return authApiFetch<TResponse>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function apiGet<TResponse>(path: string): Promise<TResponse> {
  return authApiFetch<TResponse>(path);
}

export async function apiDelete(path: string): Promise<void> {
  await authApiFetch<void>(path, { method: "DELETE" });
}

export async function apiPatch<TBody, TResponse>(
  path: string,
  body: TBody,
): Promise<TResponse> {
  return authApiFetch<TResponse>(path, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}