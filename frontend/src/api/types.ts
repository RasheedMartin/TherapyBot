export interface User {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  display_name: string;
  date_joined: string;
}

export type SessionFormat = "any" | "in_person" | "telehealth";

export interface Profile {
  username: string;
  email: string;
  date_joined: string;
  has_password: boolean;
  display_name: string;
  goals: string;
  zip_code: string;
  insurance: string;
  session_format: SessionFormat;
  timezone: string;
  reminders_enabled: boolean;
  reminder_time: string; // "HH:MM:SS"
}

export interface Conversation {
  id: number;
  title: string;
  therapy_type: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
  is_crisis: boolean;
  risk_level?: "none" | "elevated" | "imminent";
  suggested_action?: "" | "find_care" | "plan" | "notes";
  sources?: { title: string; url: string; source: string }[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface SendMessageResponse {
  conversation: Conversation;
  messages: Message[];
}

export const THERAPY_TYPES = [
  "General Therapy",
  "Cognitive Behavioural Therapy (CBT)",
  "Dialectical Behaviour Therapy (DBT)",
  "Anxiety Support",
  "Family Therapy",
  "Teen Counseling",
] as const;

// --- Find care ---------------------------------------------------------------

export const PROVIDER_TYPES = [
  { key: "psychologist", label: "Psychologists" },
  { key: "counselor", label: "Counselors" },
  { key: "social_worker", label: "Clinical social workers" },
  { key: "marriage_family", label: "Marriage & family" },
  { key: "psychiatrist", label: "Psychiatrists" },
  { key: "substance_use", label: "Substance use" },
] as const;

export type ProviderType = (typeof PROVIDER_TYPES)[number]["key"];

export interface Provider {
  npi: string;
  name: string;
  credential: string;
  is_organization: boolean;
  type: ProviderType;
  type_label: string;
  specialty: string;
  license_state: string;
  street: string;
  city: string;
  state: string;
  zip: string;
  phone: string;
  lat: number | null;
  lng: number | null;
}

export interface ProviderSearchResult {
  zip: string;
  widened: boolean;
  center: { lat: number; lng: number } | null;
  providers: Provider[];
}

export type OutreachStatus = "saved" | "contacted" | "waitlist" | "scheduled" | "not_a_fit";

export const OUTREACH_STATUSES: { value: OutreachStatus; label: string }[] = [
  { value: "saved", label: "Saved" },
  { value: "contacted", label: "Contacted" },
  { value: "waitlist", label: "On waitlist" },
  { value: "scheduled", label: "Appointment scheduled" },
  { value: "not_a_fit", label: "Not a fit" },
];

export interface SavedProvider {
  id: number;
  npi: string;
  details: Omit<Provider, "npi">;
  status: OutreachStatus;
  notes: string;
  created_at: string;
  updated_at: string;
}

// --- Plans -------------------------------------------------------------------

export type Frequency = "once" | "daily" | "weekdays" | "weekly";

export interface PlanStep {
  id?: number;
  title: string;
  details: string;
  frequency: Frequency;
  weekday: number | null; // 0 = Monday
  time_of_day: string | null; // "HH:MM" or "HH:MM:SS"
  action?: "" | "find_care";
  check_ins?: string[]; // ISO dates
}

export interface Plan {
  id: number;
  title: string;
  summary: string;
  conversation: number | null;
  archived: boolean;
  steps: PlanStep[];
  created_at: string;
  updated_at: string;
}

export interface CalendarFeed {
  enabled: boolean;
  discreet: boolean;
  url?: string;
  webcal_url?: string;
  google_url?: string;
}

export type PlanDraft = Pick<Plan, "title" | "summary" | "conversation" | "steps">;

// --- Session notes -----------------------------------------------------------

export interface NoteExplanation {
  summary: string;
  key_points: string[];
  terms: { term: string; meaning: string }[];
  homework: PlanStep[];
  questions: string[];
}

export interface SessionNoteSummary {
  id: number;
  title: string;
  session_date: string | null;
  created_at: string;
}

export interface SessionNote extends SessionNoteSummary {
  original_text: string;
  explanation: NoteExplanation;
}
