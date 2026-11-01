import { useRouterState } from "@tanstack/react-router";

const AUTH_PAGES = ["/login", "/register"];

/** A same-site path to return to after signing in. Rejects "//host" (protocol-relative) and absolute URLs. */
export const safeRedirect = (value: unknown): string | undefined =>
  typeof value === "string" && value.startsWith("/") && !value.startsWith("//") ? value : undefined;

/**
 * Search params for a sign-in or sign-up link, so the person comes back here afterwards (path and query,
 * e.g. an invite link's token). On the auth pages themselves, pass along wherever they were headed.
 */
export const useReturnHere = (): { redirect?: string } => {
  const location = useRouterState({ select: (s) => s.location });
  if (AUTH_PAGES.includes(location.pathname)) {
    return { redirect: safeRedirect((location.search as { redirect?: unknown }).redirect) };
  }
  return location.pathname === "/" ? {} : { redirect: location.href };
};
