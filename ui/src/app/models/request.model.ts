import { Audited } from './audit.model';

// Codes of the `request_statuses` lookup; labels and order come from GET /api/v1/request-statuses.
export type LifecycleStatus =
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

export interface RequestStatus extends Audited {
  code: LifecycleStatus;
  label: string;
  meaning: string;
  whoActs: string;
  position: number;
}

export const STATUS_COLOR: Record<LifecycleStatus, string> = {
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

export interface GovRequest {
  id?: number;
  arbTitle: string;
  summary?: string;
  artifactLink?: string;
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
  buGovReviewer?: string;
  eaGovReviewer?: string;
  status: LifecycleStatus;
  approvalDate?: string;
  meetingDate?: string | null;
  meetingTime?: string | null;
  comments?: string;
  createdBy?: number | null;
  updatedBy?: number | null;
  createdAt?: string;
  updatedAt?: string;
  history?: StatusHistoryEntry[];
}

export interface Meta {
  artifactTypes: string[];
  pdlcCheckpoints: string[];
}

export interface Stats {
  total: number;
  byStatus: Record<string, number>;
  byType: Record<string, number>;
}
