import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LifecycleStatus } from '../../models/request.model';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule],
  template: `<span class="badge" [attr.data-st]="key">{{ status }}</span>`,
  styles: [`
    .badge {
      font-family: var(--ff-mono);
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.08em;
      padding: 4px 10px;
      border-radius: 100px;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .badge[data-st="pending"] { color: var(--st-pending); border-color: color-mix(in srgb, var(--st-pending) 40%, transparent); background: color-mix(in srgb, var(--st-pending) 12%, transparent); }
    .badge[data-st="fb"]      { color: var(--st-fb);      border-color: color-mix(in srgb, var(--st-fb) 45%, transparent);      background: color-mix(in srgb, var(--st-fb) 12%, transparent); }
    .badge[data-st="ea"]      { color: var(--st-ea);      border-color: color-mix(in srgb, var(--st-ea) 45%, transparent);      background: color-mix(in srgb, var(--st-ea) 12%, transparent); }
    .badge[data-st="follow"]  { color: var(--st-follow);  border-color: color-mix(in srgb, var(--st-follow) 45%, transparent);  background: color-mix(in srgb, var(--st-follow) 12%, transparent); }
    .badge[data-st="rework"]  { color: var(--st-rework);  border-color: color-mix(in srgb, var(--st-rework) 45%, transparent);  background: color-mix(in srgb, var(--st-rework) 12%, transparent); }
  `],
})
export class StatusBadgeComponent {
  @Input() status: LifecycleStatus = 'PENDING';

  get key(): string {
    switch (this.status) {
      case 'APPROVED FB': return 'fb';
      case 'APPROVED EA': return 'ea';
      case 'FOLLOW UP': return 'follow';
      case 'REWORK': return 'rework';
      default: return 'pending';
    }
  }
}
