import { Component, Input } from '@angular/core';
import { DatePipe, NgIf } from '@angular/common';
import { Audited } from '../../models/audit.model';
import { UserDirectoryService } from '../../services/user-directory.service';

@Component({
  selector: 'app-audit-stamp',
  standalone: true,
  imports: [NgIf, DatePipe],
  template: `
    <span class="stamp" *ngIf="!compact && record.createdAt" [title]="record.createdAt">
      Created by <b>{{ dir.name(record.createdBy) }}</b> · {{ record.createdAt | date: 'd MMM y, HH:mm' }}
    </span>
    <span class="stamp" *ngIf="record.updatedAt && (compact || edited)" [title]="record.updatedAt">
      {{ compact ? '' : 'Updated by' }} <b>{{ dir.name(record.updatedBy) }}</b> · {{ record.updatedAt | date: 'd MMM y, HH:mm' }}
    </span>
  `,
  styles: [`
    :host { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--mute); }
    .stamp b { color: var(--paper); font-weight: 500; }
  `],
})
export class AuditStampComponent {
  @Input({ required: true }) record!: Audited;
  @Input() compact = false;

  constructor(public dir: UserDirectoryService) {
    dir.ensureLoaded();
  }

  get edited(): boolean {
    return this.record.updatedAt !== this.record.createdAt;
  }
}
