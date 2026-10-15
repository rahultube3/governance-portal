import { Component, Input } from '@angular/core';
import { RiskTier } from '../../models/request.model';

const TIER_COLOR: Record<RiskTier, string> = { 1: 'var(--st-ea)', 2: 'var(--st-fb)', 3: 'var(--st-follow)', 4: 'var(--st-rework)' };
const TIER_LABEL: Record<RiskTier, string> = { 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical' };

@Component({
  selector: 'app-tier-badge',
  standalone: true,
  template: `<span class="tier" [style.--st]="tier ? color[tier] : 'var(--mute-2)'">{{ tier ? label[tier] : 'No tier' }}</span>`,
  styles: [`
    .tier {
      font-family: var(--ff-mono);
      font-size: 11px;
      font-weight: 500;
      letter-spacing: 0.06em;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      white-space: nowrap;
      color: var(--st);
      border: 1px solid color-mix(in srgb, var(--st) 45%, transparent);
    }
  `],
})
export class TierBadgeComponent {
  @Input() tier?: RiskTier | null;
  readonly color = TIER_COLOR;
  readonly label = TIER_LABEL;
}
