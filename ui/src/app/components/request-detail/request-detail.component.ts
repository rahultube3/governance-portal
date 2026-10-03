import { Component, OnInit, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import { GovRequest, LifecycleStatus, RequestStatus, STATUS_COLOR, meetingLabel } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { UserDirectoryService } from '../../services/user-directory.service';
import { RequestStatusService } from '../../services/request-status.service';

@Component({
  selector: 'app-request-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent, AuditStampComponent],
  templateUrl: './request-detail.component.html',
  styleUrls: ['./request-detail.component.css'],
})
export class RequestDetailComponent implements OnInit {
  req?: GovRequest;
  loading = true;
  id!: number;

  newStatus: LifecycleStatus = 'SUBMITTED';
  statusNote = '';
  meetingDate = '';
  meetingTime = '';
  updating = false;
  confirmDelete = false;
  confirmWithdraw = false;
  readonly statusColor = STATUS_COLOR;
  // Drafts belong to the requestor; Scheduled needs request:schedule, every other move request:review.
  reviewStatuses = computed(() => this.statuses.statuses().filter(s => s.code !== 'DRAFT'
    && this.auth.can(s.code === 'SCHEDULED' ? 'request:schedule' : 'request:review')));
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
    this.reload();
  }

  reload(): void {
    this.loading = true;
    this.svc.get(this.id).subscribe({
      next: r => { this.req = r; this.newStatus = r.status; this.meetingDate = r.meetingDate ?? ''; this.meetingTime = r.meetingTime ?? ''; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  // Re-applying Scheduled with a different date reschedules the meeting.
  canApply(): boolean {
    if (!this.req || this.updating) return false;
    if (this.newStatus !== 'SCHEDULED') return this.newStatus !== this.req.status;
    return !!this.meetingDate && !!this.meetingTime && (this.req.status !== 'SCHEDULED'
      || this.meetingDate !== this.req.meetingDate || this.meetingTime !== (this.req.meetingTime ?? ''));
  }

  applyStatus(): void {
    if (!this.canApply()) return;
    const meeting = { meetingDate: this.meetingDate, meetingTime: this.meetingTime };
    this.transition(this.newStatus, this.newStatus === 'SCHEDULED' ? meeting : undefined);
  }

  statusInfo(code: LifecycleStatus): RequestStatus | undefined {
    return this.statuses.statuses().find(s => s.code === code);
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

  fields(): { label: string; value?: string; mono?: boolean; link?: boolean }[] {
    const r = this.req!;
    return [
      { label: 'App ID', value: r.appId, mono: true },
      { label: 'App Name', value: r.appName, mono: true },
      { label: 'TrackIT ID', value: r.trackitId, mono: true },
      { label: 'PR', value: r.pr, mono: true },
      { label: 'Artifact Link', value: r.artifactLink, link: true },
      { label: 'PDLC Checkpoint', value: r.pdlcCheckpoint },
      { label: 'Solution Architect', value: r.solutionArchitect },
      { label: 'Contributors', value: r.saContributors },
      { label: 'BU Governance Reviewer', value: r.buGovReviewer },
      { label: 'Enterprise Reviewer', value: r.eaGovReviewer },
      { label: 'Date Submitted', value: r.dateSubmitted, mono: true },
      { label: 'Date Reviewed', value: r.dateReviewed, mono: true },
      { label: 'Approval Date', value: r.approvalDate, mono: true },
      { label: 'ARB Meeting', value: meetingLabel(r), mono: true },
    ];
  }
}
