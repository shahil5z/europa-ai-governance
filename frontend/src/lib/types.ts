// Hand-maintained mirror of backend/europa/schemas.py (the API contract).

export type Level = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Severity = Level;
export type AgentName =
  | "ORCHESTRATOR"
  | "RISK"
  | "DATA_GOVERNANCE"
  | "SECURITY"
  | "HUMAN_OVERSIGHT"
  | "GOVERNANCE"
  | "CRITIC";
export type AgentStatus = "WAITING" | "RUNNING" | "COMPLETE" | "FAILED" | "REASSESSING" | "SKIPPED";
export type ReportStatus = "COMPLETE" | "PARTIAL" | "FAILED";
export type DisagreementStatus = "OPEN" | "RESOLVED" | "UNRESOLVED";
export type DisagreementKind =
  | "LEVEL_SPREAD"
  | "SECURITY_OUTLIER"
  | "CRITIC_CONTRADICTION"
  | "CRITIC_INCONSISTENT_LEVEL";

export type AuditEventType =
  | "ASSESSMENT_STARTED"
  | "ORCHESTRATION_COMPLETED"
  | "ROUTING_DECIDED"
  | "AGENT_STARTED"
  | "AGENT_RETRY"
  | "AGENT_COMPLETED"
  | "AGENT_FAILED"
  | "CRITIC_TRIGGERED"
  | "DISAGREEMENT_DETECTED"
  | "DISAGREEMENT_RESOLVED"
  | "REASSESSMENT_TRIGGERED"
  | "CONSENSUS_COMPUTED"
  | "SUMMARY_WRITTEN"
  | "REPORT_GENERATED";

export interface AuditEvent {
  seq: number;
  ts: string;
  type: AuditEventType;
  message: string;
  agent: AgentName | null;
  status: AgentStatus | null;
  round: number;
  data: Record<string, unknown>;
}

export interface Scenario {
  id: string;
  title: string;
  category: string;
  description: string;
}

export interface Finding {
  title: string;
  severity: Severity;
  confidence: number;
  explanation: string;
  evidence: string;
  recommendation: string;
}

export interface SpecialistAssessment {
  summary: string;
  level: Level;
  confidence: number;
  findings: Finding[];
  assumptions_and_gaps: string[];
  // Domain specific extras (all optional on the client)
  likelihood?: Level;
  impact?: Level;
  potential_harms?: string[];
  data_categories?: string[];
  special_category_data_likely?: boolean;
  lawful_basis_considerations?: string[];
  minimisation_and_retention?: string;
  threat_categories?: string[];
  attack_surface_notes?: string;
  oversight_model?: string;
  oversight_gaps?: string[];
  contestability_described?: boolean;
  accountability_owner_described?: boolean;
  potential_ai_act_tier?: string;
  tier_rationale?: string;
  frameworks?: { name: string; relevance: string; note: string }[];
  requires_legal_review?: boolean;
}

export interface AgentResult {
  agent: AgentName;
  assessment: SpecialistAssessment;
  revision: number;
  level_history: Level[];
  adjusted_confidence: number;
}

export interface AgentRunStatus {
  agent: AgentName;
  status: AgentStatus;
  attempts: number;
  revisions: number;
  duration_ms: number;
  level: Level | null;
  confidence: number | null;
  error_code: string | null;
  note: string | null;
}

export interface Disagreement {
  id: string;
  kind: DisagreementKind;
  source: "DETERMINISTIC" | "CRITIC";
  agents: AgentName[];
  description: string;
  levels: Partial<Record<AgentName, Level>>;
  status: DisagreementStatus;
  round_detected: number;
  resolution_note: string | null;
}

export interface ConsensusEntry {
  agent: AgentName;
  level: Level;
  confidence: number;
  adjusted_confidence: number;
  base_weight: number;
  effective_weight: number;
  note: string | null;
}

export interface Consensus {
  overall_level: Level;
  overall_confidence: number;
  weighted_score: number;
  entries: ConsensusEntry[];
  rules_applied: string[];
  unresolved_disagreements: number;
  method: string;
}

export interface Recommendation {
  agent: AgentName;
  title: string;
  text: string;
  severity: Severity;
  confidence: number;
  priority_rank: number;
}

export interface CriticAssessment {
  summary: string;
  confidence: number;
  issues: { kind: string; description: string; agents: AgentName[]; severity: Severity }[];
  missing_risks: string[];
}

export interface SystemProfile {
  domain: string;
  purpose_summary: string;
  decision_impact: Level;
  data_types: string[];
  autonomy_level: string;
  affected_people: string[];
  uses_external_tools: boolean;
  user_facing: boolean;
  missing_information: string[];
}

export interface RoutingPlan {
  decisions: { agent: AgentName; run: boolean; focus: string; justification: string }[];
  overrides: { agent: AgentName; reason: string }[];
  signals: string[];
  source: string;
}

export interface GovernanceReport {
  report_id: string;
  status: ReportStatus;
  created_at: string;
  profile: SystemProfile | null;
  routing: RoutingPlan | null;
  results: AgentResult[];
  critic: CriticAssessment | null;
  disagreements: Disagreement[];
  consensus: Consensus | null;
  executive_summary: { text: string; key_points: string[] } | null;
  recommendations: Recommendation[];
  priority_actions: Recommendation[];
  agent_statuses: AgentRunStatus[];
  audit_trail: AuditEvent[];
  limitations: string[];
  disclaimer: string;
  meta: {
    model: string;
    critic_model: string;
    max_reassessment_rounds: number;
    reassessment_rounds_used: number;
    duration_ms: number;
    description_chars: number;
    scenario_id: string | null;
    summary_mode: string;
  };
}

export type StreamEvent =
  | { type: "audit"; event: AuditEvent }
  | { type: "report"; report: GovernanceReport }
  | { type: "error"; error: { code: string; message: string } }
  | { type: "ping" };

export const AGENT_ORDER: AgentName[] = [
  "ORCHESTRATOR",
  "RISK",
  "DATA_GOVERNANCE",
  "SECURITY",
  "HUMAN_OVERSIGHT",
  "GOVERNANCE",
  "CRITIC",
];

export const AGENT_LABEL: Record<AgentName, string> = {
  ORCHESTRATOR: "Orchestrator",
  RISK: "Risk",
  DATA_GOVERNANCE: "Data Governance",
  SECURITY: "Security",
  HUMAN_OVERSIGHT: "Human Oversight",
  GOVERNANCE: "Governance",
  CRITIC: "Critic",
};

export const AGENT_ROLE: Record<AgentName, string> = {
  ORCHESTRATOR: "Profiles the system and routes work",
  RISK: "Harms, likelihood and impact",
  DATA_GOVERNANCE: "Personal data and GDPR concepts",
  SECURITY: "Threats, abuse and exposure",
  HUMAN_OVERSIGHT: "Review, override and accountability",
  GOVERNANCE: "EU AI Act and framework mapping",
  CRITIC: "Audits the other agents",
};

export const DISCLAIMER =
  "This tool provides AI-assisted governance analysis for informational purposes and does not constitute legal advice, regulatory certification, or a formal compliance determination.";
