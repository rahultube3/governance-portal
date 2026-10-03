import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { RbacService } from '../../services/rbac.service';
import { AuthService } from '../../services/auth.service';
import { UserDirectoryService } from '../../services/user-directory.service';
import { AuditStampComponent } from '../audit-stamp/audit-stamp.component';
import { PermissionDef, RbacSnapshot, RoleDef } from '../../models/rbac.model';
import { Permission, Role } from '../../models/user.model';

interface Category {
  name: string;
  permissions: PermissionDef[];
}

type Grants = Record<Role, Set<Permission>>;

@Component({
  selector: 'app-permissions',
  standalone: true,
  imports: [CommonModule, FormsModule, AuditStampComponent],
  templateUrl: './permissions.component.html',
  styleUrls: ['./permissions.component.css'],
})
export class PermissionsComponent implements OnInit {
  snapshot = signal<RbacSnapshot | null>(null);
  draft = signal<Grants | null>(null);
  groupDrafts: Partial<Record<Role, string>> = {};
  saving = signal(false);
  error = signal('');
  notice = signal('');

  roles = computed<RoleDef[]>(() => this.snapshot()?.roles ?? []);

  categories = computed<Category[]>(() => {
    const out: Category[] = [];
    for (const p of this.snapshot()?.permissions ?? []) {
      let cat = out.find(c => c.name === p.category);
      if (!cat) out.push(cat = { name: p.category, permissions: [] });
      cat.permissions.push(p);
    }
    return out;
  });

  changes = computed(() => {
    const draft = this.draft();
    if (!draft) return 0;
    let n = 0;
    for (const role of this.roles()) {
      const saved = new Set(role.permissions);
      const now = draft[role.code];
      for (const p of now) if (!saved.has(p)) n++;
      for (const p of saved) if (!now.has(p)) n++;
    }
    return n;
  });

  constructor(private svc: RbacService, private auth: AuthService, private dir: UserDirectoryService) {
    dir.ensureLoaded();
  }

  ngOnInit(): void {
    this.svc.get().subscribe({ next: s => this.apply(s), error: e => this.fail(e) });
  }

  granted(role: Role, p: Permission): boolean {
    return this.draft()?.[role].has(p) ?? false;
  }

  grantTitle(role: RoleDef, p: Permission): string {
    const g = role.grants[p];
    if (!g) return '';
    return `Granted by ${this.dir.name(g.grantedBy)} on ${new Date(g.grantedAt).toLocaleString()}`;
  }

  isChanged(role: RoleDef, p: Permission): boolean {
    return role.permissions.includes(p) !== this.granted(role.code, p);
  }

  toggle(role: Role, p: Permission): void {
    const draft = this.draft();
    if (!draft) return;
    const next = new Set(draft[role]);
    if (next.has(p)) next.delete(p); else next.add(p);
    this.draft.set({ ...draft, [role]: next });
    this.notice.set('');
  }

  discard(): void {
    const s = this.snapshot();
    if (s) this.apply(s);
  }

  save(): void {
    const draft = this.draft();
    if (!draft) return;
    const grants: Partial<Record<Role, Permission[]>> = {};
    for (const role of this.roles()) grants[role.code] = [...draft[role.code]];
    this.saving.set(true);
    this.error.set('');
    this.svc.setGrants(grants).subscribe({
      next: s => this.saved(s, 'Permissions saved.'),
      error: e => { this.saving.set(false); this.fail(e); },
    });
  }

  groupChanged(role: RoleDef): boolean {
    return (this.groupDrafts[role.code] ?? '').trim() !== role.adGroup;
  }

  saveGroup(role: RoleDef): void {
    this.saving.set(true);
    this.error.set('');
    this.svc.updateRole(role.code, { adGroup: this.groupDrafts[role.code] ?? '' }).subscribe({
      next: s => this.saved(s, `${role.name} is now granted to members of “${(this.groupDrafts[role.code] ?? '').trim() || 'no group'}”.`),
      error: e => { this.saving.set(false); this.fail(e); },
    });
  }

  private saved(s: RbacSnapshot, message: string): void {
    this.saving.set(false);
    this.apply(s);
    this.notice.set(message);
    this.auth.restore().subscribe();
  }

  private apply(s: RbacSnapshot): void {
    this.snapshot.set(s);
    const draft = {} as Grants;
    for (const r of s.roles) {
      draft[r.code] = new Set(r.permissions);
      this.groupDrafts[r.code] = r.adGroup;
    }
    this.draft.set(draft);
  }

  private fail(e: unknown): void {
    const msg = e instanceof HttpErrorResponse ? e.error?.error : null;
    this.error.set(typeof msg === 'string' ? msg : 'Something went wrong. Check the API is running.');
  }
}
