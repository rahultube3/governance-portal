import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import {
  GovRequest, LifecycleStatus, Meta, RequestStatus, RiskTier, RiskTierInfo, statusColor, isWebLink, meetingLabel,
} from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { TierBadgeComponent } from '../tier-badge/tier-badge.component';
import { UserDirectoryService } from '../../services/user-directory.service';
import { RequestStatusService } from '../../services/request-status.service';

@Component({
  selector: 'app-request-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent, AuditStampComponent, TierBadgeComponent],
  templateUrl: './request-detail.component.html',
  styleUrls: ['./request-detail.component.css'],
})
export class RequestDetailComponent implements OnInit {
  req?: GovRequest;
  meta?: Meta;
  loading = true;
  id!: number;

  newStatus: LifecycleStatus | '' = '';
  statusNote = '';
  meetingDate = '';
  meetingTime = '';
  updating = false;
  confirmDelete = false;
  confirmWithdraw = false;
  editingTier = false;
  newTier: RiskTier = 4;
  tierReason = '';
  readonly statusColor = statusColor;
  readonly isWebLink = isWebLink;
  actionError = '';

  constructor(
    private svc: GovernanceService,
    private route: ActivatedRoute,
    private router: Router,
    public auth: AuthService,
    public dir: UserDirectoryService,
    public statuses: RequestStatusService,
  ) {
    dir.ensureLoaded();
    statuses.ensureLoaded();
  }

  ngOnInit(): void {
    this.id = +this.route.snapshot.paramMap.get('id')!;
    this.svc.getMeta().subscribe(m => (this.meta = m));
    this.reload();
  }

  reload(): void {
    this.loading = true;
    this.svc.get(this.id).subscribe({
      next: r => { this.req = r; this.newStatus = ''; this.meetingDate = r.meetingDate ?? ''; this.meetingTime = r.meetingTime ?? ''; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  // Re-applying Scheduled with a different date reschedules the meeting.
  canApply(): boolean {
    if (!this.req || this.updating || !this.newStatus) return false;
    if (this.newStatus !== 'SCHEDULED') return true;
    return !!this.meetingDate && !!this.meetingTime && (this.req.status !== 'SCHEDULED'
      || this.meetingDate !== this.req.meetingDate || this.meetingTime !== (this.req.meetingTime ?? ''));
  }

  applyStatus(): void {
    if (!this.canApply() || !this.newStatus) return;
    const meeting = { meetingDate: this.meetingDate, meetingTime: this.meetingTime };
    this.transition(this.newStatus, this.newStatus === 'SCHEDULED' ? meeting : undefined);
  }

  statusInfo(code: LifecycleStatus | ''): RequestStatus | undefined {
    return this.statuses.statuses().find(s => s.code === code);
  }

  // Blocked next steps grouped by reason, e.g. every Critical decision needs the Chief Architect.
  blockedSteps(): { statuses: string; reason: string }[] {
    const byReason = new Map<string, string[]>();
    for (const s of this.req?.nextSteps ?? []) {
      if (s.blocked) byReason.set(s.blocked, [...(byReason.get(s.blocked) ?? []), this.statuses.label(s.status)]);
    }
    return [...byReason].map(([reason, labels]) => ({ statuses: labels.join(', '), reason }));
  }

  tierInfo(tier: RiskTier | null | undefined): RiskTierInfo | undefined {
    return this.meta?.riskTiers.find(t => t.tier === tier);
  }

  canSetTier(): boolean {
    const r = this.req;
    return !!r && !!this.meta && this.auth.can('request:review') && !this.auth.owns(r)
      && r.status !== 'DRAFT' && !this.meta.finalStatuses.includes(r.status);
  }

  startTierEdit(): void {
    this.newTier = this.req?.riskTier ?? 4;
    this.tierReason = '';
    this.editingTier = true;
  }

  saveTier(tier: RiskTier): void {
    this.updating = true;
    this.actionError = '';
    this.svc.setTier(this.id, tier, this.tierReason).subscribe({
      next: () => { this.updating = false; this.editingTier = false; this.reload(); },
      error: e => { this.updating = false; this.actionError = this.errorText(e); },
    });
  }

  // Hidden while an admin has deactivated the Withdrawn status.
  canWithdraw(): boolean {
    return !!this.req && this.auth.canWithdraw(this.req) && this.statuses.isActive('WITHDRAWN');
  }

  submit(): void {
    this.transition('SUBMITTED');
  }

  withdraw(): void {
    this.confirmWithdraw = false;
    this.transition('WITHDRAWN');
  }

  del(): void {
    this.actionError = '';
    this.svc.remove(this.id).subscribe({
      next: () => this.router.navigate(['/requests']),
      error: e => { this.confirmDelete = false; this.actionError = this.errorText(e); },
    });
  }

  private transition(status: LifecycleStatus, meeting?: { meetingDate: string; meetingTime: string }): void {
    this.updating = true;
    this.actionError = '';
    this.svc.changeStatus(this.id, status, this.statusNote, meeting).subscribe({
      next: () => { this.statusNote = ''; this.updating = false; this.reload(); },
      error: e => { this.updating = false; this.actionError = this.errorText(e); },
    });
  }

  private errorText(e: unknown): string {
    const msg = e instanceof HttpErrorResponse ? e.error?.error : null;
    return typeof msg === 'string' ? msg : 'The action failed. Try again.';
  }

  fields(): { label: string; value?: string | null; mono?: boolean }[] {
    const r = this.req!;
    return [
      { label: 'App ID', value: r.appId, mono: true },
      { label: 'App Name', value: r.appName, mono: true },
      { label: 'TrackIT ID', value: r.trackitId, mono: true },
      { label: 'Solution ID', value: r.solutionId, mono: true },
      { label: 'IntelEA Capability Link', value: r.intelEaCapabilityLink },
      { label: 'PR', value: r.pr, mono: true },
      { label: 'PDLC Checkpoint', value: r.pdlcCheckpoint },
      { label: 'Solution Architect', value: r.solutionArchitect },
      { label: 'Contributors', value: r.saContributors },
      { label: 'BU Governance Reviewer', value: r.buGovReviewers?.join(', ') },
      { label: 'FAE Governance Reviewer', value: r.eaGovReviewers?.join(', ') },
      { label: 'ECS (Security) Reviewer', value: r.ecsReviewers?.join(', ') },
      { label: 'Date Submitted', value: r.dateSubmitted, mono: true },
      { label: 'Date Reviewed', value: r.dateReviewed, mono: true },
      { label: 'Approval Date', value: r.approvalDate, mono: true },
      { label: 'ARB Meeting', value: meetingLabel(r), mono: true },
    ];
  }
}
