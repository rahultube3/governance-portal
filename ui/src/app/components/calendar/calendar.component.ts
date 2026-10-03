import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { RequestStatusService } from '../../services/request-status.service';
import { GovRequest, STATUS_COLOR } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';

interface Day {
  date: string;
  day: number;
  inMonth: boolean;
  isToday: boolean;
  meetings: GovRequest[];
}

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'];

// Dates are compared as local YYYY-MM-DD strings so meetings never shift a day across time zones.
const iso = (y: number, m: number, d: number) =>
  `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;

@Component({
  selector: 'app-calendar',
  standalone: true,
  imports: [CommonModule, RouterLink, StatusBadgeComponent],
  templateUrl: './calendar.component.html',
  styleUrls: ['./calendar.component.css'],
})
export class CalendarComponent implements OnInit {
  readonly weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
  readonly statusColor = STATUS_COLOR;

  loading = signal(true);
  requests = signal<GovRequest[]>([]);
  year = signal(new Date().getFullYear());
  month = signal(new Date().getMonth());

  monthLabel = computed(() => `${MONTHS[this.month()]} ${this.year()}`);

  private byDate = computed(() => {
    const map = new Map<string, GovRequest[]>();
    for (const r of this.requests()) {
      if (!r.meetingDate) continue;
      map.set(r.meetingDate, [...(map.get(r.meetingDate) ?? []), r]);
    }
    // Timed meetings first, in time order; untimed ones after.
    for (const list of map.values()) {
      list.sort((a, b) => (a.meetingTime ?? '99:99').localeCompare(b.meetingTime ?? '99:99'));
    }
    return map;
  });

  weeks = computed<Day[][]>(() => {
    const y = this.year();
    const m = this.month();
    const now = new Date();
    const today = iso(now.getFullYear(), now.getMonth(), now.getDate());
    // Monday-first grid: step back to the Monday on or before the 1st.
    const start = new Date(y, m, 1 - ((new Date(y, m, 1).getDay() + 6) % 7));
    const weeks: Day[][] = [];
    for (let w = 0; w < 6; w++) {
      const week: Day[] = [];
      for (let d = 0; d < 7; d++) {
        const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7 + d);
        const date = iso(cur.getFullYear(), cur.getMonth(), cur.getDate());
        week.push({
          date, day: cur.getDate(), inMonth: cur.getMonth() === m, isToday: date === today,
          meetings: this.byDate().get(date) ?? [],
        });
      }
      if (w > 3 && !week.some(day => day.inMonth)) break;
      weeks.push(week);
    }
    return weeks;
  });

  agenda = computed(() => {
    const prefix = iso(this.year(), this.month(), 1).slice(0, 8);
    return [...this.byDate().entries()]
      .filter(([date]) => date.startsWith(prefix))
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, meetings]) => ({ date, meetings }));
  });

  monthCount = computed(() => this.agenda().reduce((n, d) => n + d.meetings.length, 0));

  constructor(private svc: GovernanceService, public statuses: RequestStatusService) {
    statuses.ensureLoaded();
  }

  ngOnInit(): void {
    this.svc.list().subscribe(list => {
      this.requests.set(list);
      this.loading.set(false);
    });
  }

  shift(months: number): void {
    const d = new Date(this.year(), this.month() + months, 1);
    this.year.set(d.getFullYear());
    this.month.set(d.getMonth());
  }

  goToday(): void {
    const now = new Date();
    this.year.set(now.getFullYear());
    this.month.set(now.getMonth());
  }
}
