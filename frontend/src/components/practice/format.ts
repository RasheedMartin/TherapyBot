/** "Oct 24, 2026" from an ISO date or datetime; "Undated" for null. */
export const formatDate = (iso: string | null) =>
  iso
    ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" })
    : "Undated";
