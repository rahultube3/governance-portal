import { Component, Input } from '@angular/core';
import { LifecycleStatus, STATUS_COLOR } from '../../models/request.model';
import { RequestStatusService } from '../../services/request-status.service';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  template: `<span class="badge" [style.--st]="color" [title]="status">{{ statuses.label(status) }}</span>`,
  styles: [`
    .badge {
      font-family: var(--ff-mono);
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      padding: 4px 10px;
      border-radius: 100px;
      white-space: nowrap;
      color: var(--st);
      border: 1px solid color-mix(in srgb, var(--st) 45%, transparent);
      background: color-mix(in srgb, var(--st) 12%, transparent);
    }
  `],
})
export class StatusBadgeComponent {
  @Input({ required: true }) status!: LifecycleStatus;

  constructor(public statuses: RequestStatusService) {
    statuses.ensureLoaded();
  }

  get color(): string {
    return STATUS_COLOR[this.status];
  }
}
