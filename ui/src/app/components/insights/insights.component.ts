import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import { GovRequest, APPROVED_STATUSES } from '../../models/request.model';

type Grain = 'monthly' | 'quarterly' | 'yearly';

interface PeriodRow {
  key: string;
  label: string;
  sublabel: string;
  intake: number;
  completed: number;
  inFlight: number;
  completionRate: number;
}

interface TypeRow {
  name: string;
  shortName: string;
  intake: number;
  completed: number;
  completionRate: number;
}

const COMPLETED_STATUSES = new Set<string>(APPROVED_STATUSES);
const MONTHS_SHORT = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

@Component({
  selector: 'app-insights',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './insights.component.html',
  styleUrls: ['./insights.component.css'],
})
export class InsightsComponent implements OnInit {
  loading = signal(true);
  requests = signal<GovRequest[]>([]);

  grain = signal<Grain>('monthly');
  year = signal<number>(new Date().getFullYear());

  years = computed<number[]>(() => {
    const list = this.requests();
    if (!list.length) return [new Date().getFullYear()];
    const set = new Set<number>();
    list.forEach(r => {
      const d = r.dateSubmitted; if (d) set.add(+d.slice(0, 4));
      const a = r.approvalDate;  if (a) set.add(+a.slice(0, 4));
    });
    return Array.from(set).sort((a, b) => b - a);
  });

  periods = computed<PeriodRow[]>(() => {
    const g = this.grain();
    const y = this.year();
    const list = this.requests();

    if (g === 'monthly')   return this.buildMonthly(list, y);
    if (g === 'quarterly') return this.buildQuarterly(list, y);
    return this.buildYearly(list);
  });

  totals = computed(() => {
    const rows = this.periods();
    const intake = rows.reduce((s, r) => s + r.intake, 0);
    const completed = rows.reduce((s, r) => s + r.completed, 0);
    const inFlight = rows.reduce((s, r) => s + r.inFlight, 0);
    return {
      intake, completed, inFlight,
      completionRate: intake ? Math.round((completed / intake) * 100) : 0,
    };
  });

  scaleMax = computed(() => {
    const rows = this.periods();
    return Math.max(1, ...rows.map(r => Math.max(r.intake, r.completed)));
  });

  typeBreakdown = computed<TypeRow[]>(() => {
    const list = this.requests();
    const g = this.grain();
    const y = this.year();

    const inScope = (dateStr?: string) => {
      if (!dateStr) return false;
      if (g === 'yearly') return true;
      return +dateStr.slice(0, 4) === y;
    };

    const map = new Map<string, TypeRow>();
    for (const r of list) {
      const t = r.artifactType;
      if (!map.has(t)) {
        map.set(t, { name: t, shortName: this.shortType(t), intake: 0, completed: 0, completionRate: 0 });
      }
      const row = map.get(t)!;
      if (inScope(r.dateSubmitted)) row.intake++;
      if (COMPLETED_STATUSES.has(r.status) && inScope(r.approvalDate)) row.completed++;
    }
    const rows = Array.from(map.values());
    rows.forEach(r => r.completionRate = r.intake ? Math.round((r.completed / r.intake) * 100) : 0);
    rows.sort((a, b) => b.intake - a.intake);
    return rows;
  });

  constructor(private svc: GovernanceService, public auth: AuthService) {}

  ngOnInit(): void {
    this.svc.list().subscribe(list => {
      this.requests.set(list);
      this.loading.set(false);
      const ys = this.years();
      if (ys.length && !ys.includes(this.year())) this.year.set(ys[0]);
    });
  }

  setGrain(g: Grain) { this.grain.set(g); }
  setYear(y: number) { this.year.set(+y); }

  chartBars() {
    const rows = this.periods();
    const max = this.scaleMax();
    return rows.map(r => ({
      label: r.sublabel,
      intake: r.intake,
      completed: r.completed,
      intakeH: Math.round((r.intake / max) * 100),
      completedH: Math.round((r.completed / max) * 100),
      completionRate: r.completionRate,
    }));
  }

  shortType(t: string): string {
    const m = t.match(/\(([^)]+)\)/);
    if (m) return m[1];
    return t.replace(/ (Intake Request|Submission)$/,'').trim();
  }

  exportCsv() {
    const rows = this.periods();
    const header = ['Period', 'Intake', 'Completed', 'In-Flight', 'Completion %'];
    const body = rows.map(r => [r.label, r.intake, r.completed, r.inFlight, `${r.completionRate}%`]);
    const csv = [header, ...body].map(cols =>
      cols.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')
    ).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `governance-insights-${this.grain()}-${this.year()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ---------- builders ----------
  private buildMonthly(list: GovRequest[], year: number): PeriodRow[] {
    const rows: PeriodRow[] = MONTHS_SHORT.map((m, i) => ({
      key: `${year}-${String(i + 1).padStart(2, '0')}`,
      label: `${m} ${year}`,
      sublabel: m,
      intake: 0, completed: 0, inFlight: 0, completionRate: 0,
    }));
    for (const r of list) {
      if (r.dateSubmitted && r.dateSubmitted.startsWith(String(year))) {
        const m = +r.dateSubmitted.slice(5, 7) - 1;
        if (m >= 0 && m < 12) rows[m].intake++;
      }
      if (COMPLETED_STATUSES.has(r.status) && r.approvalDate && r.approvalDate.startsWith(String(year))) {
        const m = +r.approvalDate.slice(5, 7) - 1;
        if (m >= 0 && m < 12) rows[m].completed++;
      }
    }
    return this.finalize(rows);
  }

  private buildQuarterly(list: GovRequest[], year: number): PeriodRow[] {
    const rows: PeriodRow[] = [0, 1, 2, 3].map(q => ({
      key: `${year}-Q${q + 1}`,
      label: `Q${q + 1} ${year}`,
      sublabel: `Q${q + 1}`,
      intake: 0, completed: 0, inFlight: 0, completionRate: 0,
    }));
    for (const r of list) {
      if (r.dateSubmitted && r.dateSubmitted.startsWith(String(year))) {
        const q = Math.floor((+r.dateSubmitted.slice(5, 7) - 1) / 3);
        if (q >= 0 && q < 4) rows[q].intake++;
      }
      if (COMPLETED_STATUSES.has(r.status) && r.approvalDate && r.approvalDate.startsWith(String(year))) {
        const q = Math.floor((+r.approvalDate.slice(5, 7) - 1) / 3);
        if (q >= 0 && q < 4) rows[q].completed++;
      }
    }
    return this.finalize(rows);
  }

  private buildYearly(list: GovRequest[]): PeriodRow[] {
    const years = new Set<number>();
    list.forEach(r => {
      if (r.dateSubmitted) years.add(+r.dateSubmitted.slice(0, 4));
      if (r.approvalDate)  years.add(+r.approvalDate.slice(0, 4));
    });
    if (!years.size) years.add(new Date().getFullYear());
    const sorted = Array.from(years).sort((a, b) => a - b);
    const rows: PeriodRow[] = sorted.map(y => ({
      key: String(y), label: String(y), sublabel: String(y),
      intake: 0, completed: 0, inFlight: 0, completionRate: 0,
    }));
    const idx = new Map(sorted.map((y, i) => [y, i]));
    for (const r of list) {
      if (r.dateSubmitted) {
        const i = idx.get(+r.dateSubmitted.slice(0, 4)); if (i != null) rows[i].intake++;
      }
      if (COMPLETED_STATUSES.has(r.status) && r.approvalDate) {
        const i = idx.get(+r.approvalDate.slice(0, 4)); if (i != null) rows[i].completed++;
      }
    }
    return this.finalize(rows);
  }

  private finalize(rows: PeriodRow[]): PeriodRow[] {
    rows.forEach(r => {
      r.inFlight = Math.max(0, r.intake - r.completed);
      r.completionRate = r.intake ? Math.round((r.completed / r.intake) * 100) : 0;
    });
    return rows;
  }
}
