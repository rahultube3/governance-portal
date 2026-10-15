import { Component, Input, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Observable } from 'rxjs';
import { OptionList, ReferenceService } from '../../services/reference.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { ManagedOption } from '../../models/request.model';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { apiError } from './api-error';

// The Review Types and PDLC Checkpoints tabs: a list of names to add, rename, activate, deactivate and remove.
// An ordered list (PDLC) also moves entries up and down; an unordered one is sorted by name.
@Component({
  selector: 'app-option-list',
  standalone: true,
  imports: [CommonModule, FormsModule, AuditStampComponent],
  templateUrl: './option-list.component.html',
  styleUrls: ['../admin/admin.component.css', './list.css'],
})
export class OptionListComponent implements OnInit {
  @Input({ required: true }) list!: OptionList;
  @Input({ required: true }) noun!: string;
  @Input() ordered = false;

  items = signal<ManagedOption[]>([]);
  loading = signal(true);
  busy = signal(false);
  error = signal('');
  newName = '';
  editingId: number | null = null;
  editName = '';
  confirmId: number | null = null;

  constructor(private svc: ReferenceService, dir: UserDirectoryService) {
    dir.ensureLoaded();
  }

  ngOnInit(): void {
    this.run(this.svc.options(this.list), list => this.items.set(list));
  }

  add(): void {
    this.run(this.svc.addOption(this.list, this.newName.trim()), () => { this.newName = ''; this.reload(); });
  }

  startEdit(o: ManagedOption): void {
    this.editingId = o.id;
    this.editName = o.name;
    this.confirmId = null;
  }

  saveEdit(o: ManagedOption): void {
    this.run(this.svc.updateOption(this.list, o.id, { name: this.editName.trim() }), () => {
      this.editingId = null;
      this.reload();
    });
  }

  toggle(o: ManagedOption): void {
    this.run(this.svc.updateOption(this.list, o.id, { active: !o.active }), u => this.replace(u));
  }

  remove(o: ManagedOption): void {
    this.run(this.svc.removeOption(this.list, o.id), () => {
      this.confirmId = null;
      this.items.update(list => list.filter(x => x.id !== o.id));
    });
  }

  move(index: number, delta: number): void {
    const ids = this.items().map(o => o.id);
    [ids[index], ids[index + delta]] = [ids[index + delta], ids[index]];
    this.run(this.svc.orderOptions(this.list, ids), list => this.items.set(list));
  }

  private replace(updated: ManagedOption): void {
    this.items.update(list => list.map(x => (x.id === updated.id ? updated : x)));
  }

  private reload(): void {
    this.run(this.svc.options(this.list), list => this.items.set(list));
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
