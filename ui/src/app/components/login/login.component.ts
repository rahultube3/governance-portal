import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { forkJoin } from 'rxjs';
import { RoleInfo } from '../../models/rbac.model';
import { User } from '../../models/user.model';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
})
export class LoginComponent implements OnInit {
  users = signal<User[]>([]);
  roles = signal<RoleInfo[]>([]);
  loading = signal(true);
  error = signal('');
  signingIn = signal<number | null>(null);

  groups = computed(() => this.roles().map(r => ({
    role: r.code,
    label: r.name,
    blurb: r.description,
    users: this.users().filter(u => u.role === r.code),
  })));

  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    forkJoin({ users: this.auth.directory(), roles: this.auth.roles() }).subscribe({
      next: ({ users, roles }) => { this.users.set(users); this.roles.set(roles); this.loading.set(false); },
      error: () => { this.error.set('Could not reach the API. Is it running?'); this.loading.set(false); },
    });
  }

  signIn(u: User): void {
    this.signingIn.set(u.id);
    this.error.set('');
    this.auth.login(u.id).subscribe({
      next: () => this.router.navigateByUrl('/'),
      error: () => { this.error.set('Sign-in failed. Try again.'); this.signingIn.set(null); },
    });
  }

  initials(name: string): string {
    return name.split(/[\s.]+/).filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('');
  }
}
