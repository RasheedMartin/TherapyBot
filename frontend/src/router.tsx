import { createRouter, RootRoute, Route } from "@tanstack/react-router";
import Home from "./pages/Home";
import { Login } from "./components/Login";
import App from "./App";
import { GettingStarted } from "./pages/GettingStarted";
import { RegisterPage } from "./components/Register";
import { ForgotPasswordPage } from "./components/ForgotPasswordPage";
import { ResetPasswordPage } from "./components/ResetPasswordPage";

const rootRoute = new RootRoute({
  component: App,
});

export const homeRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Home,
});

export const loginRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "login",
  component: Login,
});

export const forgotPasswordRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "forgot-password",
  component: ForgotPasswordPage,
});

export const resetPasswordRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "reset-password",
  validateSearch: (search: Record<string, unknown>) => ({
    token: String(search.token || ""),
    uid: String(search.uid || null),
  }),
  component: ResetPasswordPage,
});

export const gettingStartedRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "get-started",
  component: GettingStarted,
});

export const registerRoute = new Route({
  getParentRoute: () => rootRoute,
  path: "register",
  component: RegisterPage,
});

// Create the router
export const router = createRouter({
  routeTree: rootRoute.addChildren([
    homeRoute,
    loginRoute,
    registerRoute,
    gettingStartedRoute,
    forgotPasswordRoute,
    resetPasswordRoute,
  ]),
});
