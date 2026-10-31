import type { Frequency, PlanStep } from "../../api/types";

export const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export const FREQUENCIES: { value: Frequency; label: string }[] = [
  { value: "daily", label: "Every day" },
  { value: "weekdays", label: "Weekdays" },
  { value: "weekly", label: "Once a week" },
  { value: "once", label: "Just once" },
];

/** Local-time ISO date (YYYY-MM-DD), so check-ins land on the user's own calendar day. */
export const isoDate = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export const addDays = (d: Date, n: number) => {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
};

/** 0 = Monday, matching the API. */
const weekdayOf = (d: Date) => (d.getDay() + 6) % 7;

export const isDueOn = (step: PlanStep, day: Date) => {
  switch (step.frequency) {
    case "daily":
      return true;
    case "weekdays":
      return weekdayOf(day) < 5;
    case "weekly":
      return weekdayOf(day) === step.weekday;
    case "once":
      // A one-off step stays on the list until it's done, then shows only on the day it was done
      return (step.check_ins ?? []).length === 0 || (step.check_ins ?? []).includes(isoDate(day));
  }
};

export const isDoneOn = (step: PlanStep, day: Date) => (step.check_ins ?? []).includes(isoDate(day));

/** Consecutive due days completed, counting back from today (today may still be pending). */
export const streak = (step: PlanStep, today = new Date()) => {
  if (step.frequency === "once") return 0;
  let count = 0;
  let day = isDoneOn(step, today) ? today : addDays(today, -1);
  for (let i = 0; i < 60; i++, day = addDays(day, -1)) {
    if (!isDueOn(step, day)) continue;
    if (!isDoneOn(step, day)) break;
    count++;
  }
  return count;
};

export const describeSchedule = (step: PlanStep) => {
  const when =
    step.frequency === "weekly" && step.weekday != null
      ? `Every ${WEEKDAYS[step.weekday]}`
      : (FREQUENCIES.find((f) => f.value === step.frequency)?.label ?? "");
  if (!step.time_of_day) return when;
  const [h, m] = step.time_of_day.split(":").map(Number);
  const time = new Date(2000, 0, 1, h, m).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  return `${when} at ${time}`;
};
