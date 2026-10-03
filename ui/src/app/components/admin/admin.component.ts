import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { UsersService } from '../../services/users.service';
import { AuthService } from '../../services/auth.service';
import { RbacService } from '../../services/rbac.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { RoleSummary } from '../../models/rbac.model';
import { ManagedUser, Role, User, UserInput } from '../../models/user.model';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, AuditStampComponent],
  templateUrl: './admin.component.html',
  styleUrls: ['./admin.component.css'],
})
export class AdminComponent implements OnInit {
  roles = signal<RoleSummary[]>([]);
  users = signal<ManagedUser[]>([]);
  loading = signal(true);
  error = signal('');
  draft: UserInput = { name: '', email: '', role: 'REQUESTOR' };

  counts = computed(() => this.roles().map(r => ({
    role: r.code,
    label: r.name,
    count: this.users().filter(u => u.role === r.code).length,
  })));

  constructor(
    private svc: UsersService,
    private rbac: RbacService,
    private dir: UserDirectoryService,
    public auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.rbac.roles().subscribe({ next: r => this.roles.set(r), error: e => this.fail(e) });
    this.load();
  }

  optionLabel(r: RoleSummary): string {
    return r.adGroup ? `${r.name} — ${r.adGroup}` : `${r.name} (unmapped)`;
  }

  load(): void {
    this.svc.list().subscribe({
      next: list => { this.users.set(list); this.loading.set(false); },
      error: e => this.fail(e),
    });
  }

  add(): void {
    this.error.set('');
    this.svc.create(this.draft).subscribe({
      next: u => {
        this.users.update(list => [...list, u]);
        this.draft = { name: '', email: '', role: this.draft.role };
        this.dir.refresh();
      },
      error: e => this.fail(e),
    });
  }

  changeRole(u: User, role: Role): void {
    this.error.set('');
    this.svc.update(u.id, { role }).subscribe({
      next: updated => this.users.update(list => list.map(x => x.id === updated.id ? updated : x)),
      error: e => { this.fail(e); this.load(); },
    });
  }

  remove(u: User): void {
    if (!confirm(`Delete ${u.name}? Their requests stay but lose their owner.`)) return;
    this.error.set('');
    this.svc.remove(u.id).subscribe({
      next: () => { this.users.update(list => list.filter(x => x.id !== u.id)); this.dir.refresh(); },
      error: e => this.fail(e),
    });
  }

  isSelf(u: User): boolean {
    return u.id === this.auth.user()?.id;
  }

  private fail(e: unknown): void {
    this.loading.set(false);
    const msg = e instanceof HttpErrorResponse ? e.error?.error : null;
    this.error.set(typeof msg === 'string' ? msg : 'Something went wrong. Check the API is running.');
  }
}
