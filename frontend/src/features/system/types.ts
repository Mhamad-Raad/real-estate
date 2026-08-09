export interface Health {
  status: string;
  /**
   * The server's build. `app_version`/`build`, never `version` — that name is the optimistic-lock
   * counter on every other resource in this API (§7.2).
   */
  app_version: string;
  build: number;
}
