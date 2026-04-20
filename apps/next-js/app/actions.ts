// Shared types — MOSS logic now runs client-side via @moss-dev/moss-web

export type DocInput = {
  id: string;
  text: string;
  metadata?: Record<string, string>;
};
