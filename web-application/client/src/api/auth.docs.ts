/**
 * Auth API Contract — Elyssa Frontend
 *
 * Endpoint: VITE_AUTH_URL (default: http://localhost:4000/auth)
 * Auth mechanism: httpOnly JWT cookie (set by server on login/register)
 *
 * ─── Endpoints ───────────────────────────────────────────────────────────
 *
 * POST /auth/register
 *   Body: { email: string, password: string, displayName: string }
 *   Response: { accessToken: string }
 *   Sets httpOnly cookie with refresh token.
 *
 * POST /auth/login
 *   Body: { email: string, password: string }
 *   Response: { accessToken: string }
 *   Sets httpOnly cookie with refresh token.
 *
 * POST /auth/logout
 *   Headers: Cookie (httpOnly refresh token)
 *   Response: 204 No Content
 *   Clears httpOnly cookie.
 *
 * GET /auth/me
 *   Headers: Authorization: Bearer <accessToken>
 *   Response: { id: string, email: string, displayName: string }
 *
 * ─── Protected Endpoints (require Authorization header) ──────────────────
 *
 * GET  /auth/watchlist        → WatchlistItem[]
 * POST /auth/watchlist        → { tconst: string }          → WatchlistItem
 * DELETE /auth/watchlist/:id  → 204 No Content
 *
 * ─── Error Responses ─────────────────────────────────────────────────────
 * 400: { message: string }
 * 401: { message: "Unauthorized" }
 * 409: { message: "Email already registered" }
 *
 * ─── Token Flow ──────────────────────────────────────────────────────────
 * 1. Login/Register returns short-lived accessToken (15 min)
 * 2. AccessToken stored in memory (AuthContext) — NOT localStorage
 * 3. httpOnly refreshToken cookie (7 day expiry) set by server
 * 4. On 401, client attempts silent refresh via cookie
 * 5. If refresh fails → logout, redirect to /auth/login
 *
 * ─── Backend Requirements ────────────────────────────────────────────────
 * - POST /auth/register
 * - POST /auth/login
 * - POST /auth/logout
 * - GET  /auth/me
 * - Token refresh via httpOnly cookie (transparent to client)
 * - CORS: origin http://localhost:5173, credentials: true
 */
export {};
