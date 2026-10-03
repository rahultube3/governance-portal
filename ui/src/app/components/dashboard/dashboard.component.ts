import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import { Stats, GovRequest, LifecycleStatus } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css'],
})
export class DashboardComponent implements OnInit {
  stats?: Stats;
  recent: GovRequest[] = [];
  loading = true;

  lifecycle: LifecycleStatus[] = ['PENDING', 'APPROVED FB', 'APPROVED EA', 'FOLLOW UP', 'REWORK'];

  stageKey: Record<string, string> = {
    'PENDING': 'pending', 'APPROVED FB': 'fb', 'APPROVED EA': 'ea',
    'FOLLOW UP': 'follow', 'REWORK': 'rework',
  };

  constructor(private svc: GovernanceService, public auth: AuthService) {}

  ngOnInit(): void {
    this.svc.getStats().subscribe(s => (this.stats = s));
    this.svc.list().subscribe(r => {
      this.recent = r.slice(0, 6);
      this.loading = false;
    });
  }

  count(status: string): number {
    return this.stats?.byStatus?.[status] ?? 0;
  }

  typeEntries(): { name: string; count: number }[] {
    if (!this.stats) return [];
    return Object.entries(this.stats.byType).map(([name, count]) => ({ name, count }));
  }

  shortType(t: string): string {
    const m = t.match(/\(([^)]+)\)/);
    if (m) return m[1];
    return t.replace(/ (Intake Request|Submission)$/,'').trim();
  }
}
