import { forwardRef } from "react";
import { Button, Link as MuiLink, type ButtonProps, type LinkProps as MuiLinkProps } from "@mui/material";
import { createLink } from "@tanstack/react-router";

const MuiLinkBase = forwardRef<HTMLAnchorElement, MuiLinkProps>((props, ref) => (
  <MuiLink ref={ref} underline="hover" fontWeight={600} {...props} />
));

const MuiButtonBase = forwardRef<HTMLAnchorElement, ButtonProps<"a">>((props, ref) => (
  <Button ref={ref} component="a" {...props} />
));

/** MUI-styled link that navigates with the TanStack router. */
export const RouterLink = createLink(MuiLinkBase);

/** MUI button that navigates with the TanStack router, with typed `to` / `search`. */
export const LinkButton = createLink(MuiButtonBase);
