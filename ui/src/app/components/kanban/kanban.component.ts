import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { GovRequest, LifecycleStatus } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';

interface Column {
  label: string;
  color: string;
  statuses: LifecycleStatus[];
}

interface Lane extends Column {
  requests: GovRequest[];
}

const COLUMNS: Column[] = [
  { label: 'Pending', color: 'var(--st-pending)', statuses: ['PENDING'] },
  { label: 'Pending Chief Architecture Review', color: 'var(--st-follow)', statuses: ['FOLLOW UP'] },
  { label: 'Approved', color: 'var(--st-ea)', statuses: ['APPROVED FB', 'APPROVED EA'] },
  { label: 'Rejected', color: 'var(--st-rework)', statuses: ['REWORK'] },
];

@Component({
  selector: 'app-kanban',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent, AuditStampComponent],
  templateUrl: './kanban.component.html',
  styleUrls: ['../board/board.component.css', './kanban.component.css'],
})
export class KanbanComponent implements OnInit {
  loading = signal(true);
  requests = signal<GovRequest[]>([]);
  preview = signal<GovRequest | null>(null);

  constructor(private svc: GovernanceService) {}

  ngOnInit(): void {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.svc.list().subscribe(list => {
      this.requests.set(list);
      this.loading.set(false);
    });
  }

  lanes = computed<Lane[]>(() =>
    COLUMNS.map(col => ({
      ...col,
      requests: this.requests().filter(r => col.statuses.includes(r.status)),
    })));

  openPreview(r: GovRequest) {
    this.preview.set(r);
  }

  closePreview() {
    this.preview.set(null);
  }

  previewFields(r: GovRequest): { label: string; value: string }[] {
    const fields: [string, string | undefined][] = [
      ['Artifact type', r.artifactType],
      ['PDLC checkpoint', r.pdlcCheckpoint],
      ['Application', [r.appName, r.appId].filter(Boolean).join(' · ')],
      ['Solution architect', r.solutionArchitect],
      ['SA contributors', r.saContributors],
      ['TrackIt ID', r.trackitId],
      ['PR', r.pr],
      ['BU gov reviewer', r.buGovReviewer],
      ['EA gov reviewer', r.eaGovReviewer],
      ['Submitted', r.dateSubmitted],
      ['Reviewed', r.dateReviewed],
      ['Approved', r.approvalDate],
    ];
    return fields
      .filter((f): f is [string, string] => !!f[1])
      .map(([label, value]) => ({ label, value }));
  }

  trackLane =(_: number, l: Lane) => l.label;
  trackRequest = (_: number, r: GovRequest) => r.id;
}
