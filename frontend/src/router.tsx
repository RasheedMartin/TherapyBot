import { createRouter, RootRoute, Route } from "@tanstack/react-router";
import Home from "./pages/Home";
import { Login } from "./components/Login";
import App from "./App";
import { GettingStarted } from "./pages/GettingStarted";
import { RegisterPage } from "./components/Register";

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
  ]),
});
