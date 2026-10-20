// ── Auth (POST /auth/login, /auth/signup, GET /auth/me) ─────────────────

export interface AnalystProfile {
  username: string;
  display_name: string;
  role: "l1_analyst" | "l2_analyst" | "supervisor";
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  analyst: AnalystProfile;
}
