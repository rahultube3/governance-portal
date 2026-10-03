import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { GovRequest, LifecycleStatus, STATUS_COLOR, meetingLabel } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';

interface Column {
  label: string;
  color: string;
  statuses: LifecycleStatus[];
}

type Grain = 'all' | 'monthly' | 'quarterly' | 'yearly';

interface Lane extends Column {
  requests: GovRequest[];
}

// Drafts and withdrawn requests aren't in review, so they have no lane.
const COLUMNS: Column[] = [
  { label: 'Submitted', color: STATUS_COLOR.SUBMITTED, statuses: ['SUBMITTED'] },
  { label: 'In Review', color: STATUS_COLOR.IN_REVIEW, statuses: ['IN_REVIEW', 'SCHEDULED'] },
  { label: 'Changes Requested', color: STATUS_COLOR.CHANGES_REQUESTED, statuses: ['CHANGES_REQUESTED'] },
  { label: 'Chief Architecture Review', color: STATUS_COLOR.CHIEF_ARCHITECTURE_REVIEW, statuses: ['CHIEF_ARCHITECTURE_REVIEW'] },
  { label: 'Approved', color: STATUS_COLOR.APPROVED, statuses: ['APPROVED', 'APPROVED_WITH_CONDITIONS'] },
  { label: 'Rejected', color: STATUS_COLOR.REJECTED, statuses: ['REJECTED'] },
];

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];
const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'];

@Component({
  selector: 'app-kanban',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent, AuditStampComponent],
  templateUrl: './kanban.component.html',
  styleUrls: ['../board/board.component.css', './kanban.component.css'],
})
export class KanbanComponent implements OnInit {
  loading = signal(true);
  requests = signal<GovRequest[]>([]);
  preview = signal<GovRequest | null>(null);

  readonly months = MONTHS;
  readonly quarters = QUARTERS;
  grain = signal<Grain>('all');
  year = signal(new Date().getFullYear());
  month = signal(new Date().getMonth());
  quarter = signal(Math.floor(new Date().getMonth() / 3));

  years = computed<number[]>(() => {
    const set = new Set(this.requests()
      .filter(r => r.dateSubmitted)
      .map(r => +r.dateSubmitted!.slice(0, 4)));
    if (!set.size) set.add(new Date().getFullYear());
    return Array.from(set).sort((a, b) => b - a);
  });

  periodLabel = computed(() => {
    const g = this.grain();
    if (g === 'monthly') return `${MONTHS[this.month()]} ${this.year()}`;
    if (g === 'quarterly') return `${QUARTERS[this.quarter()]} ${this.year()}`;
    return String(this.year());
  });

  filtered = computed<GovRequest[]>(() => {
    const g = this.grain();
    const y = this.year();
    const m = this.month();
    const q = this.quarter();
    if (g === 'all') return this.requests();
    return this.requests().filter(r => {
      const d = r.dateSubmitted;
      if (!d || +d.slice(0, 4) !== y) return false;
      const month = +d.slice(5, 7) - 1;
      if (g === 'monthly') return month === m;
      if (g === 'quarterly') return Math.floor(month / 3) === q;
      return true;
    });
  });

  constructor(private svc: GovernanceService) {}

  ngOnInit(): void {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.svc.list().subscribe(list => {
      this.requests.set(list);
      this.loading.set(false);
      const ys = this.years();
      if (!ys.includes(this.year())) this.year.set(ys[0]);
    });
  }

  lanes = computed<Lane[]>(() =>
    COLUMNS.map(col => ({
      ...col,
      requests: this.filtered().filter(r => col.statuses.includes(r.status)),
    })));

  openPreview(r: GovRequest) {
    this.preview.set(r);
  }

  closePreview() {
    this.preview.set(null);
  }

  previewFields(r: GovRequest): { label: string; value: string }[] {
    const fields: [string, string | undefined][] = [
      ['Review type', r.artifactType],
      ['PDLC checkpoint', r.pdlcCheckpoint],
      ['ARB meeting', meetingLabel(r)],
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
