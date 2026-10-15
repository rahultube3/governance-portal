import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { ReferenceService } from '../../services/reference.service';
import { GovernanceService } from '../../services/governance.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { ManagedReviewer, ReviewerRole, ReviewerRoleCode } from '../../models/request.model';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { apiError } from './api-error';

// The Reviewers tab: one table per role (BU, FAE, ECS), each sorted by name.
@Component({
  selector: 'app-reviewers-tab',
  standalone: true,
  imports: [CommonModule, FormsModule, AuditStampComponent],
  templateUrl: './reviewers-tab.component.html',
  styleUrls: ['../admin/admin.component.css', './list.css'],
})
export class ReviewersTabComponent implements OnInit {
  roles = signal<ReviewerRole[]>([]);
  reviewers = signal<ManagedReviewer[]>([]);
  loading = signal(true);
  busy = signal(false);
  error = signal('');
  draft: { name: string; role: ReviewerRoleCode } = { name: '', role: 'BU' };
  editingId: number | null = null;
  editName = '';
  confirmId: number | null = null;

  groups = computed(() => this.roles().map(role => ({
    role,
    reviewers: this.reviewers().filter(r => r.role === role.code)
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })),
  })));

  constructor(private svc: ReferenceService, private gov: GovernanceService, dir: UserDirectoryService) {
    dir.ensureLoaded();
  }

  ngOnInit(): void {
    this.gov.getMeta().subscribe({ next: m => this.roles.set(m.reviewerRoles), error: e => this.error.set(apiError(e)) });
    this.run(this.svc.reviewers(), list => this.reviewers.set(list));
  }

  add(): void {
    this.run(this.svc.addReviewer({ ...this.draft, name: this.draft.name.trim() }), r => {
      this.reviewers.update(list => [...list, r]);
      this.draft = { ...this.draft, name: '' };
    });
  }

  startEdit(r: ManagedReviewer): void {
    this.editingId = r.id;
    this.editName = r.name;
    this.confirmId = null;
  }

  saveEdit(r: ManagedReviewer): void {
    this.run(this.svc.updateReviewer(r.id, { name: this.editName.trim() }), u => { this.editingId = null; this.replace(u); });
  }

  toggle(r: ManagedReviewer): void {
    this.run(this.svc.updateReviewer(r.id, { active: !r.active }), u => this.replace(u));
  }

  remove(r: ManagedReviewer): void {
    this.run(this.svc.removeReviewer(r.id), () => {
      this.confirmId = null;
      this.reviewers.update(list => list.filter(x => x.id !== r.id));
    });
  }

  private replace(updated: ManagedReviewer): void {
    this.reviewers.update(list => list.map(x => (x.id === updated.id ? updated : x)));
  }

  private run<T>(call: Observable<T>, done: (value: T) => void): void {
    this.error.set('');
    this.busy.set(true);
    call.subscribe({
      next: value => { this.busy.set(false); this.loading.set(false); done(value); },
      error: e => { this.busy.set(false); this.loading.set(false); this.error.set(apiError(e)); },
    });
  }
}
