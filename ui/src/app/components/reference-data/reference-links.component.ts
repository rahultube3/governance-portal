import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { ReferenceService } from '../../services/reference.service';
import { GovernanceService } from '../../services/governance.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { ManagedArtifactName, NamedOption } from '../../models/request.model';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { apiError } from './api-error';

// The Reference Links tab: the Architecture Reference Link names, which review types require each one,
// and their order on the intake form.
@Component({
  selector: 'app-reference-links',
  standalone: true,
  imports: [CommonModule, FormsModule, AuditStampComponent],
  templateUrl: './reference-links.component.html',
  styleUrls: ['../admin/admin.component.css', './list.css'],
})
export class ReferenceLinksComponent implements OnInit {
  names = signal<ManagedArtifactName[]>([]);
  reviewTypes = signal<NamedOption[]>([]);
  loading = signal(true);
  busy = signal(false);
  error = signal('');
  draft = { label: '', requiredFor: [] as string[] };
  editingCode: string | null = null;
  edit = { label: '', requiredFor: [] as string[] };
  confirmCode: string | null = null;

  constructor(private svc: ReferenceService, private gov: GovernanceService, dir: UserDirectoryService) {
    dir.ensureLoaded();
  }

  ngOnInit(): void {
    this.gov.getMeta().subscribe({ next: m => this.reviewTypes.set(m.artifactTypes), error: e => this.error.set(apiError(e)) });
    this.run(this.svc.referenceNames(), list => this.names.set(list));
  }

  // Active review types, plus inactive ones the entry being edited still requires.
  typeChoices(selected: string[]): NamedOption[] {
    return this.reviewTypes().filter(t => t.active || selected.includes(t.name));
  }

  toggleType(selected: string[], name: string, on: boolean): string[] {
    return on ? [...selected, name] : selected.filter(n => n !== name);
  }

  add(): void {
    this.run(this.svc.addReferenceName({ label: this.draft.label.trim(), requiredFor: this.draft.requiredFor }), () => {
      this.draft = { label: '', requiredFor: [] };
      this.reload();
    });
  }

  startEdit(n: ManagedArtifactName): void {
    this.editingCode = n.code;
    this.edit = { label: n.label, requiredFor: [...n.requiredFor] };
    this.confirmCode = null;
  }

  saveEdit(n: ManagedArtifactName): void {
    this.run(this.svc.updateReferenceName(n.code, { label: this.edit.label.trim(), requiredFor: this.edit.requiredFor }), u => {
      this.editingCode = null;
      this.replace(u);
    });
  }

  toggle(n: ManagedArtifactName): void {
    this.run(this.svc.updateReferenceName(n.code, { active: !n.active }), u => this.replace(u));
  }

  remove(n: ManagedArtifactName): void {
    this.run(this.svc.removeReferenceName(n.code), () => {
      this.confirmCode = null;
      this.names.update(list => list.filter(x => x.code !== n.code));
    });
  }

  move(index: number, delta: number): void {
    const codes = this.names().map(n => n.code);
    [codes[index], codes[index + delta]] = [codes[index + delta], codes[index]];
    this.run(this.svc.orderReferenceNames(codes), list => this.names.set(list));
  }

  private replace(updated: ManagedArtifactName): void {
    this.names.update(list => list.map(x => (x.code === updated.code ? updated : x)));
  }

  private reload(): void {
    this.run(this.svc.referenceNames(), list => this.names.set(list));
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
