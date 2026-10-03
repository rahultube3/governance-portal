export type LifecycleStatus =
  | 'PENDING'
  | 'APPROVED FB'
  | 'APPROVED EA'
  | 'FOLLOW UP'
  | 'REWORK';

export interface StatusHistoryEntry {
  from_status: string | null;
  to_status: string;
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
  comments?: string;
  createdBy?: number | null;
  updatedBy?: number | null;
  createdAt?: string;
  updatedAt?: string;
  history?: StatusHistoryEntry[];
}

export interface Meta {
  artifactTypes: string[];
  lifecycle: LifecycleStatus[];
  pdlcCheckpoints: string[];
}

export interface Stats {
  total: number;
  byStatus: Record<string, number>;
  byType: Record<string, number>;
}
