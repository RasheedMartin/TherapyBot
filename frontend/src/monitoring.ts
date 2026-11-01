import * as Sentry from "@sentry/react";

/**
 * Error monitoring, without sending what people write. Off unless VITE_SENTRY_DSN is set at build time.
 * No session replay, no user identity, no console breadcrumbs, and URLs lose their query strings
 * (invite and calendar tokens live there).
 */
const stripQuery = (url?: string) => (url ? url.split("?")[0] : url);

const dsn = import.meta.env.VITE_SENTRY_DSN as string | undefined;

if (dsn) {
  Sentry.init({
    dsn,
    environment: import.meta.env.MODE,
    sendDefaultPii: false,
    integrations: (defaults) => defaults.filter((i) => i.name !== "Replay"),
    tracesSampleRate: 0,
    beforeBreadcrumb(crumb) {
      if (crumb.category === "console") return null; // could echo user content
      if (crumb.data?.url) crumb.data.url = stripQuery(crumb.data.url as string);
      if (crumb.data?.from) crumb.data.from = stripQuery(crumb.data.from as string);
      if (crumb.data?.to) crumb.data.to = stripQuery(crumb.data.to as string);
      return crumb;
    },
    beforeSend(event) {
      delete event.user;
      if (event.request) {
        event.request.url = stripQuery(event.request.url);
        delete event.request.query_string;
        delete event.request.cookies;
        delete event.request.data;
      }
      return event;
    },
  });
}
