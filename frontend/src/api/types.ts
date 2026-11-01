export interface User {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  display_name: string;
  role: "client" | "therapist";
  npi_status: "" | "verified" | "needs_review" | "rejected";
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
  note_format: "soap" | "dap";
}

export interface Conversation {
  id: number;
  title: string;
  therapy_type: string;
  shared_with_care_team: boolean;
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
  care_summary: string;
}

export interface SendMessageResponse {
  conversation: Conversation;
  messages: Message[];
  care_team_notified?: boolean;
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
  outlook_url?: string;
  office365_url?: string;
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

// --- Therapist practice --------------------------------------------------------

export interface RelationshipSummary {
  id: number;
  status: "invited" | "active" | "ended";
  invited_at: string;
  consented_at: string | null;
  ended_at: string | null;
  share_checkins: boolean;
  share_chat_summaries: boolean;
  share_raw_chat: boolean;
}

export interface PracticeClient {
  id: number;
  display_name: string;
  email: string;
  has_account: boolean;
  created_at: string;
  relationship: RelationshipSummary | null;
}

export type DocType = "client_upload" | "progress_note" | "transcript" | "intake" | "client_summary" | "other";

export interface DocumentSummary {
  id: number;
  title: string;
  doc_type: DocType;
  status: "draft" | "final";
  session: number | null;
  session_date: string | null;
  signed_at: string | null;
  imported_from: string;
  created_at: string;
}

/** A document suggested by an import, reviewed by the therapist before it's saved. */
export interface ImportedDocument {
  title: string;
  doc_type: Exclude<DocType, "client_upload" | "client_summary">;
  session_date: string | null;
  text: string;
}

export interface ImportPreview {
  files: { filename: string; error?: string; documents: ImportedDocument[] }[];
}

export interface ClinicalDocument extends DocumentSummary {
  text: string;
  author_name: string;
  signed_by_name: string;
  amends: number | null;
  summary_of: number | null;
  editable: boolean;
  updated_at: string;
}

export type Modality = "cbt" | "dbt" | "act" | "integrative";

export const MODALITIES: { value: Modality; label: string }[] = [
  { value: "cbt", label: "CBT" },
  { value: "dbt", label: "DBT" },
  { value: "act", label: "ACT" },
  { value: "integrative", label: "Integrative / other" },
];

export type SessionStatus = "scheduled" | "completed" | "cancelled";

export interface SessionInfo {
  id: number;
  date: string;
  start_time: string | null; // "HH:MM:SS", the therapist's local time
  duration_minutes: number;
  modality: Modality;
  status: SessionStatus;
}

export interface SessionWithDocuments extends SessionInfo {
  documents: DocumentSummary[];
}

/** A session on the therapist's schedule, across clients. */
export interface ScheduledSession extends SessionInfo {
  client_id: number;
  client_name: string;
}

export interface Timeline {
  sessions: SessionWithDocuments[];
  other_documents: DocumentSummary[];
}

export interface Citation {
  label: string;
  document_id: number | null;
  session_id: number | null;
  session_date: string | null;
  doc_type: DocType | "chat_summary";
  snippet: string;
}

export interface CitedItem {
  text: string;
  sources: string[];
}

export interface ScreeningTrend {
  key: string;
  instrument: string;
  latest_total: number;
  latest_severity: string;
  latest_date: string;
  previous_total: number | null;
  previous_date: string | null;
  change: number | null;
  max_total: number;
}

export interface ClientFacts {
  sessions_completed: number;
  last_session_date: string | null;
  last_session_modality: string | null;
  next_session_date: string | null;
  draft_notes: number;
  client_shares_checkins: boolean;
  homework: { plan: string; step: string; frequency: string; done_last_14_days?: number; due_last_14_days?: number }[];
  screenings: ScreeningTrend[];
  open_risk_flags: number;
}

export interface SessionPrep {
  facts: ClientFacts;
  summary: string;
  last_session: CitedItem[];
  open_threads: CitedItem[];
  suggested_focus: CitedItem[];
  sources: Citation[];
  dropped_claims: number;
  warnings: string[];
}

export interface RecordAnswer {
  answer: string;
  sources: Citation[];
}

export interface TreatmentObjective {
  text: string;
  measure: string;
  interventions: string[];
}

export interface TreatmentGoal {
  text: string;
  evidence: Citation[];
  objectives: TreatmentObjective[];
}

export interface TreatmentPlan {
  id: number;
  modality: Modality;
  status: "draft" | "active" | "archived";
  problem_summary: string;
  ai_generated: boolean;
  signed_at: string | null;
  share_with_client: boolean;
  goals: TreatmentGoal[];
  created_at: string;
}

export interface Screening {
  id: number;
  instrument: string; // "phq9", "gad7" or "t<template id>"
  instrument_name: string;
  responses: number[];
  total: number;
  severity: string;
  administered_on: string;
  source: "clinician" | "self_report";
}

export interface AnswerOption {
  value: number;
  label: string;
}

export interface Instrument {
  key: string;
  name: string;
  prompt: string;
  items: string[];
  options: AnswerOption[];
  max_total: number;
  custom: boolean;
  bands: { min: number; label: string }[];
  risk_item: number | null;
}

/** A practice's own questionnaire. */
export interface ScreeningTemplate {
  id: number;
  key: string;
  name: string;
  prompt: string;
  items: string[];
  options: AnswerOption[];
  bands: { min: number; label: string }[];
  risk_item: number | null;
  risk_min: number;
  archived: boolean;
  results: number;
  updated_at: string;
}

export interface RiskFlag {
  id: number;
  client_id: number;
  client_name: string;
  level: "elevated" | "imminent";
  source_type: "screening" | "chat";
  reason: string;
  created_at: string;
  acknowledged_at: string | null;
}

export interface CareTeamMember {
  id: number;
  therapist_name: string;
  practice_name: string;
  status: "active" | "ended";
  consented_at: string | null;
  ended_at: string | null;
  share_checkins: boolean;
  share_chat_summaries: boolean;
  share_raw_chat: boolean;
  next_session: string | null;
  next_session_time: string | null;
}

export interface InvitePreview {
  therapist_name: string;
  practice_name: string;
  invited_email: string;
  always_shared: string;
  defaults: { share_checkins: boolean; share_chat_summaries: boolean; share_raw_chat: boolean };
}

export interface SharedConversation {
  id: number;
  title: string;
  updated_at: string;
  message_count: number;
  flagged: boolean;
  summary: string | null;
  messages: { role: "user" | "assistant"; content: string; created_at: string }[] | null;
}

export interface BetweenSessions {
  since: string;
  sharing: { share_checkins: boolean; share_chat_summaries: boolean; share_raw_chat: boolean };
  conversations: SharedConversation[];
  chat_flags: number;
}

export interface DraftSummary {
  id: number;
  client_id: number;
  client_name: string;
  title: string;
  session_date: string | null;
  updated_at: string;
}

/** The therapist's day: today's sessions and what needs attention across clients in their care. */
export interface PracticeOverview {
  today: ScheduledSession[];
  to_close: ScheduledSession[];
  needs_note: ScheduledSession[];
  drafts: DraftSummary[];
  recently_signed: DraftSummary[];
  unscheduled: { id: number; display_name: string }[];
  open_flags: number;
  active_clients: number;
}

/** A session as the client sees it, with their therapist's name. */
export interface ClientSession {
  id: number;
  date: string;
  start_time: string | null;
  duration_minutes: number;
  status: "scheduled" | "cancelled";
  therapist_name: string;
}

/** A session summary the therapist wrote for the client and shared. */
export interface SharedSummary {
  id: number;
  session_date: string | null;
  shared_at: string;
  text: string;
  therapist_name: string;
}
