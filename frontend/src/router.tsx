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
import { RequireAuth, RequireGuest, RequireTherapist } from "./components/RouteGuards";
import { safeRedirect } from "./components/returnTo";
import { AcceptInvitePage } from "./pages/AcceptInvite";
import { ClientDetail } from "./pages/practice/ClientDetail";
import { DocumentPage } from "./pages/practice/DocumentPage";
import { ClientsPage } from "./pages/practice/ClientsPage";
import { NotesQueue } from "./pages/practice/NotesQueue";
import { PracticeOverview } from "./pages/practice/PracticeOverview";
import { SchedulePage } from "./pages/practice/SchedulePage";
import { TemplatesPage } from "./pages/practice/TemplatesPage";
import { TherapistSignup } from "./pages/practice/TherapistSignup";

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
  validateSearch: (search: Record<string, unknown>): { redirect?: string } => ({ redirect: safeRedirect(search.redirect) }),
  component: () => (
    <RequireGuest>
      <Login />
    </RequireGuest>
  ),
});

const redirectSearch = (search: Record<string, unknown>): { redirect?: string } => ({
  redirect: safeRedirect(search.redirect),
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "register",
  validateSearch: redirectSearch,
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

const therapistSignupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "therapists/register",
  component: () => (
    <RequireGuest>
      <TherapistSignup />
    </RequireGuest>
  ),
});

const therapistPage = <TPath extends string>(path: TPath, Page: () => React.ReactNode) =>
  createRoute({
    getParentRoute: () => rootRoute,
    path,
    component: () => (
      <RequireTherapist>
        <Page />
      </RequireTherapist>
    ),
  });

const practiceRoute = therapistPage("practice", PracticeOverview);
const practiceClientsRoute = therapistPage("practice/clients", ClientsPage);
const practiceScheduleRoute = therapistPage("practice/schedule", SchedulePage);
const practiceNotesRoute = therapistPage("practice/notes", NotesQueue);
const practiceTemplatesRoute = therapistPage("practice/templates", TemplatesPage);

const practiceClientRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "practice/clients/$clientId",
  component: () => (
    <RequireTherapist>
      <ClientDetail />
    </RequireTherapist>
  ),
});

const practiceDocumentRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "practice/clients/$clientId/documents/$docId",
  component: () => (
    <RequireTherapist>
      <DocumentPage />
    </RequireTherapist>
  ),
});

const acceptInviteRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "care-team/invite",
  validateSearch: (search: Record<string, unknown>) => ({ t: typeof search.t === "string" ? search.t : "" }),
  component: AcceptInvitePage,
});

export const router = createRouter({
  routeTree: rootRoute.addChildren([
    homeRoute,
    therapistSignupRoute,
    practiceRoute,
    practiceClientsRoute,
    practiceScheduleRoute,
    practiceNotesRoute,
    practiceTemplatesRoute,
    practiceClientRoute,
    practiceDocumentRoute,
    acceptInviteRoute,
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
