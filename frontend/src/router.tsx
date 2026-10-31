import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import App from "./App";
import Home from "./pages/Home";
import { ChatPage } from "./pages/Chat";
import { NotFound } from "./pages/NotFound";
import { ProfilePage } from "./pages/Profile";
import { PrivacyPage, TermsPage } from "./pages/Legal";
import { FindCarePage } from "./pages/FindCare";
import { PlansPage } from "./pages/Plans";
import { VerifyEmailPage } from "./pages/VerifyEmail";
import { QuickCheckInPage, RemindersOffPage } from "./pages/EmailActions";
import { NoteDetailPage, NotesPage } from "./pages/Notes";
import { Login } from "./components/Login";
import { RegisterPage } from "./components/Register";
import { ForgotPasswordPage } from "./components/ForgotPasswordPage";
import { ResetPasswordPage } from "./components/ResetPasswordPage";
import { RequireAuth, RequireGuest } from "./components/RouteGuards";

const rootRoute = createRootRoute({
  component: App,
  notFoundComponent: NotFound,
});

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Home,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "login",
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => ({
    redirect: typeof search.redirect === "string" && search.redirect.startsWith("/") ? search.redirect : undefined,
  }),
  component: () => (
    <RequireGuest>
      <Login />
    </RequireGuest>
  ),
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "register",
  component: () => (
    <RequireGuest>
      <RegisterPage />
    </RequireGuest>
  ),
});

const forgotPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "forgot-password",
  component: ForgotPasswordPage,
});

const resetPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "reset-password",
  validateSearch: (search: Record<string, unknown>) => ({
    uid: typeof search.uid === "string" ? search.uid : "",
    token: typeof search.token === "string" ? search.token : "",
  }),
  component: ResetPasswordPage,
});

const chatRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "chat",
  validateSearch: (search: Record<string, unknown>): { c?: number } => {
    const id = Number(search.c);
    return Number.isInteger(id) && id > 0 ? { c: id } : {};
  },
  component: () => (
    <RequireAuth verified>
      <ChatPage />
    </RequireAuth>
  ),
});

const profileRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "profile",
  component: () => (
    <RequireAuth>
      <ProfilePage />
    </RequireAuth>
  ),
});

const findCareRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "find-care",
  validateSearch: (search: Record<string, unknown>): { tab?: "shortlist" } =>
    search.tab === "shortlist" ? { tab: "shortlist" } : {},
  component: () => (
    <RequireAuth verified>
      <FindCarePage />
    </RequireAuth>
  ),
});

const plansRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "plans",
  component: () => (
    <RequireAuth verified>
      <PlansPage />
    </RequireAuth>
  ),
});

const verifyEmailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "verify-email",
  validateSearch: (search: Record<string, unknown>) => ({
    uid: typeof search.uid === "string" ? search.uid : "",
    token: typeof search.token === "string" ? search.token : "",
  }),
  component: VerifyEmailPage,
});

const notesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "notes",
  component: () => (
    <RequireAuth verified>
      <NotesPage />
    </RequireAuth>
  ),
});

const noteDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "notes/$noteId",
  component: () => (
    <RequireAuth verified>
      <NoteDetailPage />
    </RequireAuth>
  ),
});

const tokenSearch = (search: Record<string, unknown>) => ({ t: typeof search.t === "string" ? search.t : "" });

const checkInRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "check-in",
  validateSearch: tokenSearch,
  component: QuickCheckInPage,
});

const remindersOffRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "reminders/off",
  validateSearch: tokenSearch,
  component: RemindersOffPage,
});

const termsRoute = createRoute({ getParentRoute: () => rootRoute, path: "terms", component: TermsPage });
const privacyRoute = createRoute({ getParentRoute: () => rootRoute, path: "privacy", component: PrivacyPage });

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    homeRoute,
    loginRoute,
    registerRoute,
    forgotPasswordRoute,
    resetPasswordRoute,
    chatRoute,
    profileRoute,
    findCareRoute,
    plansRoute,
    verifyEmailRoute,
    notesRoute,
    noteDetailRoute,
    checkInRoute,
    remindersOffRoute,
    termsRoute,
    privacyRoute,
  ]),
  defaultPreload: "intent",
  scrollRestoration: true,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
