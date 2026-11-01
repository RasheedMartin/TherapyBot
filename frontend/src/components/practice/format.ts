/** "Oct 24, 2026" from an ISO date or datetime; "Undated" for null. */
export const formatDate = (iso: string | null) =>
  iso
    ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })
    : "Undated";

/** "2:00 PM" from "14:00:00"; "No time set" for null. */
export const formatTime = (t: string | null) =>
  t ? new Date(`2000-01-01T${t}`).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "No time set";
