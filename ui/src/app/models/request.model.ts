import { Audited } from './audit.model';

// Codes of the `request_statuses` lookup; labels and order come from GET /api/v1/request-statuses.
export type BuiltinStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'IN_REVIEW'
  | 'CHANGES_REQUESTED'
  | 'SCHEDULED'
  | 'CHIEF_ARCHITECTURE_REVIEW'
  | 'APPROVED'
  | 'APPROVED_WITH_CONDITIONS'
  | 'REJECTED'
  | 'WITHDRAWN';

// A built-in code, or one an admin added on the Reference Data page (a pause step).
export type LifecycleStatus = BuiltinStatus | (string & {});

// `builtin` statuses carry the review route; `deactivatable` says whether admins may switch one off;
// `inUse` counts requests currently in it.
export interface RequestStatus extends Audited {
  code: LifecycleStatus;
  label: string;
  meaning: string;
  whoActs: string;
  position: number;
  active: boolean;
  builtin: boolean;
  deactivatable: boolean;
  inUse: number;
}

export const STATUS_COLOR: Record<BuiltinStatus, string> = {
  DRAFT: 'var(--mute-2)',
  SUBMITTED: 'var(--st-pending)',
  IN_REVIEW: 'var(--st-fb)',
  CHANGES_REQUESTED: 'var(--st-follow)',
  SCHEDULED: 'var(--st-fb)',
  CHIEF_ARCHITECTURE_REVIEW: 'var(--st-follow)',
  APPROVED: 'var(--st-ea)',
  APPROVED_WITH_CONDITIONS: 'var(--st-ea)',
  REJECTED: 'var(--st-rework)',
  WITHDRAWN: 'var(--mute-2)',
};

// Admin-added pause steps show in amber.
export function statusColor(code: LifecycleStatus | null | undefined): string {
  return (code && STATUS_COLOR[code as BuiltinStatus]) || 'var(--st-follow)';
}

export function meetingLabel(r: GovRequest): string | undefined {
  if (!r.meetingDate) return undefined;
  return r.meetingTime ? `${r.meetingDate} ${r.meetingTime}` : r.meetingDate;
}

export const APPROVED_STATUSES: LifecycleStatus[] = ['APPROVED', 'APPROVED_WITH_CONDITIONS'];

export interface StatusHistoryEntry {
  from_status: LifecycleStatus | null;
  to_status: LifecycleStatus;
  note: string | null;
  created_at: string;
  created_by: number | null;
}

// 1 Low, 2 Medium, 3 High, 4 Critical. The labels and routes come from GET /api/v1/meta.
export type RiskTier = 1 | 2 | 3 | 4;

export interface RiskTierInfo {
  tier: RiskTier;
  label: string;
  route: string;
}

// An Architecture Reference Link; `code` is one of `Meta.artifactNames`, `link` is free text. The API adds `label`.
export interface Artifact {
  code: string;
  label?: string;
  link: string;
}

// A reference dropdown choice; `requiredFor` lists the review types that must carry it before submission.
// Inactive names are kept on requests that already use them but can't be picked again.
export interface ArtifactName {
  code: string;
  label: string;
  requiredFor: string[];
  active: boolean;
}

// Admin views of the Reference Data lists add audit fields and `inUse`, how many requests use the entry
// (an entry in use can be deactivated but not removed).
export interface ManagedArtifactName extends ArtifactName, Audited {
  position: number;
  inUse: number;
}

// A Review Type or PDLC Checkpoint; inactive ones are kept on requests that already use them.
export interface NamedOption {
  id: number;
  name: string;
  active: boolean;
}

export interface ManagedOption extends NamedOption, Audited {
  inUse: number;
  position?: number;
}

export type ReviewerRoleCode = 'BU' | 'FAE' | 'ECS';
export type ReviewerField = 'buGovReviewers' | 'eaGovReviewers' | 'ecsReviewers';

// A reviewer checklist on the intake form: which role it lists and which request field holds the picked names.
export interface ReviewerRole {
  code: ReviewerRoleCode;
  label: string;
  field: ReviewerField;
}

// Inactive reviewers are kept on requests that already name them but can't be picked again.
export interface Reviewer {
  id: number;
  name: string;
  role: ReviewerRoleCode;
  active: boolean;
}

export type ManagedReviewer = Reviewer & Audited & { inUse: number };

// Free-text references are only rendered as links when they are web addresses.
export function isWebLink(value: string | null | undefined): boolean {
  return !!value && /^https?:\/\//i.test(value);
}

// The validation agent's verdict on a Low-risk request.
export interface AgentReview {
  passed: boolean;
  summary: string;
  findings: string[];
  checkedAt: string;
}

// A review move from the current status; `blocked` says why the caller can't make it.
export interface NextStep {
  status: LifecycleStatus;
  blocked: string | null;
}

export interface GovRequest {
  id?: number;
  arbTitle: string;
  summary?: string;
  artifacts?: Artifact[];
  intelEaCapabilityLink?: string | null;
  solutionId?: string | null;
  pr?: string;
  appId?: string;
  appName?: string;
  trackitId?: string;
  solutionArchitect?: string;
  saContributors?: string;
  artifactType: string;
  pdlcCheckpoint?: string;
  dateSubmitted?: string;
  dateReviewed?: string;
  buGovReviewers?: string[];
  eaGovReviewers?: string[];
  ecsReviewers?: string[];
  status: LifecycleStatus;
  approvalDate?: string;
  meetingDate?: string | null;
  meetingTime?: string | null;
  comments?: string;
  riskTier?: RiskTier | null;
  agentReview?: AgentReview | null;
  createdBy?: number | null;
  updatedBy?: number | null;
  createdAt?: string;
  updatedAt?: string;
  history?: StatusHistoryEntry[];
  nextSteps?: NextStep[];
}

export interface Meta {
  artifactTypes: NamedOption[];
  artifactNames: ArtifactName[];
  maxArtifacts: number;
  reviewerRoles: ReviewerRole[];
  reviewers: Reviewer[];
  pdlcCheckpoints: NamedOption[];
  riskTiers: RiskTierInfo[];
  finalStatuses: LifecycleStatus[];
}

export interface Stats {
  total: number;
  byStatus: Record<string, number>;
  byType: Record<string, number>;
}
