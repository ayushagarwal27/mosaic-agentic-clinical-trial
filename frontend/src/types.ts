// Mirrors api/schemas.py and the raw dict shapes the routers return.
// Anything typed loosely here is loose in the backend too.

export interface AnalysisRequest {
  task: string;
  nct_ids: string[];
  max_studies: number;
}

export interface AnalysisResponse {
  run_id: string;
  task: string;
  final_brief: string;
  total_signals: number;
  signals_requiring_review: number;
  agents_activated: string[];
  duration_seconds: number;
}

export interface Signal {
  signal_id: string;
  // null for sponsor-level and cross-study signals.
  nct_id: string | null;
  agent: string;
  signal_type: string;
  summary: string;
  confidence: number;
  status: string;
  created_at: string;
  // Only present on GET /signals/{id} — the list query omits it.
  evidence?: string[] | string | null;
}

export interface ReviewQueueItem {
  review_id: string;
  signal_id: string;
  agent: string;
  signal_type: string;
  summary: string;
  confidence: number;
  nct_id: string | null;
  decision: string;
}

export interface ReviewQueueResponse {
  queue: ReviewQueueItem[];
  total_pending: number;
  total_approved: number;
  total_rejected: number;
}

export interface ReviewDecisionRequest {
  decision: "approve" | "reject" | "edit";
  reviewer: string;
  rejection_reason: string;
  edit_summary: string;
}

export interface ReviewDecisionResponse {
  success: boolean;
  decision: string;
  signal_id: string;
  queue_id: string;
  memory_updated: boolean;
  message: string;
}

export interface Episode {
  episode_id: string;
  agent_name: string;
  nct_id: string | null;
  content: string;
  outcome: string | null;
  similarity?: number | null;
  created_at: string;
}

export interface EpisodesResponse {
  episodes: Episode[];
  count: number;
  query: string | null;
}

export interface Procedure {
  procedure_id: string;
  agent_name: string;
  rule_text: string;
  rule_type: string;
  source: string;
  created_at: string;
}

export interface ProceduresResponse {
  agent_name: string;
  procedures: Procedure[];
  total_rules: number;
  default_rules: number;
  learned_rules: number;
}

export interface SponsorProfile {
  sponsor: string;
  credibility_score: number;
  total_studies: number;
  results_posted: number;
  results_missing: number;
  broken_promises: number;
  avg_delay_days: number;
  last_updated: string;
}

export interface SponsorsResponse {
  sponsors: SponsorProfile[];
  count: number;
}

export interface Health {
  status: string;
  app: string;
  version: string;
  database: string;
  details: {
    signals_in_db: number;
    pending_reviews: number;
    episodes_count: number;
    queue_depth: number;
  };
}

// The six specialists, in the order graph_builder fans them out.
export const AGENTS = [
  "broken_promises_agent",
  "missing_results_agent",
  "track_record_agent",
  "pattern_finder_agent",
  "side_effect_agent",
  "timeline_agent",
] as const;

export const SIGNAL_TYPES = [
  "broken_promise",
  "missing_results",
  "low_credibility",
  "cross_study_pattern",
  "safety_gap",
  "timeline_delay",
] as const;

export const AGENT_LABELS: Record<string, string> = {
  broken_promises_agent: "Broken Promises",
  missing_results_agent: "Missing Results",
  track_record_agent: "Track Record",
  pattern_finder_agent: "Pattern Finder",
  side_effect_agent: "Side Effects",
  timeline_agent: "Timeline",
};

export const SIGNAL_TYPE_LABELS: Record<string, string> = {
  broken_promise: "Broken Promise",
  missing_results: "Missing Results",
  low_credibility: "Low Credibility",
  cross_study_pattern: "Cross-Study Pattern",
  safety_gap: "Safety Gap",
  timeline_delay: "Timeline Delay",
};
