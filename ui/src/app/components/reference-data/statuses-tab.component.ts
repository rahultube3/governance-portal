import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { ReferenceService } from '../../services/reference.service';
import { RequestStatusService } from '../../services/request-status.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { RequestStatus } from '../../models/request.model';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { apiError } from './api-error';

// The Lifecycle Statuses tab. Built-in statuses carry the review route: their text is editable and the optional
// outcomes can be deactivated. Admin-added statuses are pause steps a reviewer can move a request into from
// In Review, Scheduled or Chief Architecture Review, and back out of.
@Component({
  selector: 'app-statuses-tab',
  standalone: true,
  imports: [CommonModule, FormsModule, AuditStampComponent],
  templateUrl: './statuses-tab.component.html',
  styleUrls: ['../admin/admin.component.css', './list.css'],
})
export class StatusesTabComponent {
  draft = { label: '', meaning: '', whoActs: 'Reviewer' };
  editingCode: string | null = null;
  edit = { label: '', meaning: '', whoActs: '' };
  confirmCode: string | null = null;
  busy = false;
  error = '';

  constructor(private svc: ReferenceService, public statuses: RequestStatusService, dir: UserDirectoryService) {
    statuses.ensureLoaded();
    dir.ensureLoaded();
  }

  canAdd(): boolean {
    return !this.busy && !!this.draft.label.trim() && !!this.draft.meaning.trim() && !!this.draft.whoActs.trim();
  }

  add(): void {
    const body = { label: this.draft.label.trim(), meaning: this.draft.meaning.trim(), whoActs: this.draft.whoActs.trim() };
    this.run(this.svc.addStatus(body), s => {
      this.statuses.add(s);
      this.draft = { label: '', meaning: '', whoActs: 'Reviewer' };
    });
  }

  startEdit(s: RequestStatus): void {
    this.editingCode = s.code;
    this.edit = { label: s.label, meaning: s.meaning, whoActs: s.whoActs };
    this.confirmCode = null;
  }

  save(s: RequestStatus): void {
    const patch = { label: this.edit.label.trim(), meaning: this.edit.meaning.trim(), whoActs: this.edit.whoActs.trim() };
    this.run(this.svc.updateStatus(s.code, patch), u => { this.editingCode = null; this.statuses.replace(u); });
  }

  toggle(s: RequestStatus): void {
    this.run(this.svc.updateStatus(s.code, { active: !s.active }), u => this.statuses.replace(u));
  }

  remove(s: RequestStatus): void {
    this.run(this.svc.removeStatus(s.code), () => { this.confirmCode = null; this.statuses.remove(s.code); });
  }

  private run<T>(call: Observable<T>, done: (value: T) => void): void {
    this.busy = true;
    this.error = '';
    call.subscribe({
      next: value => { this.busy = false; done(value); },
      error: e => { this.busy = false; this.error = apiError(e); },
    });
  }
}
