import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { GovRequest, Meta, LifecycleStatus } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';

@Component({
  selector: 'app-request-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent],
  templateUrl: './request-detail.component.html',
  styleUrls: ['./request-detail.component.css'],
})
export class RequestDetailComponent implements OnInit {
  req?: GovRequest;
  meta?: Meta;
  loading = true;
  id!: number;

  newStatus: LifecycleStatus = 'PENDING';
  statusNote = '';
  updating = false;
  confirmDelete = false;

  constructor(
    private svc: GovernanceService,
    private route: ActivatedRoute,
    private router: Router,
  ) {}

  ngOnInit(): void {
    this.svc.getMeta().subscribe(m => (this.meta = m));
    this.id = +this.route.snapshot.paramMap.get('id')!;
    this.reload();
  }

  reload(): void {
    this.loading = true;
    this.svc.get(this.id).subscribe({
      next: r => { this.req = r; this.newStatus = r.status; this.loading = false; },
      error: () => { this.loading = false; },
    });
  }

  applyStatus(): void {
    if (!this.req || this.newStatus === this.req.status) return;
    this.updating = true;
    this.svc.changeStatus(this.id, this.newStatus, this.statusNote).subscribe({
      next: () => { this.statusNote = ''; this.updating = false; this.reload(); },
      error: () => { this.updating = false; },
    });
  }

  del(): void {
    this.svc.remove(this.id).subscribe(() => this.router.navigate(['/requests']));
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
    ];
  }
}
