import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { AuthService } from '../../services/auth.service';
import { ROLES, ROLE_LABELS, Role, User } from '../../models/user.model';

const ROLE_BLURBS: Record<Role, string> = {
  REQUESTOR: 'Submit intakes and track your own requests.',
  REVIEWER: 'Review the queue and move requests through the lifecycle.',
  ADMIN: 'Full access, including users and roles.',
};

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.css'],
})
export class LoginComponent implements OnInit {
  users = signal<User[]>([]);
  loading = signal(true);
  error = signal('');
  signingIn = signal<number | null>(null);

  groups = computed(() => ROLES.map(role => ({
    role,
    label: ROLE_LABELS[role],
    blurb: ROLE_BLURBS[role],
    users: this.users().filter(u => u.role === role),
  })));

  constructor(private auth: AuthService, private router: Router) {}

  ngOnInit(): void {
    this.auth.directory().subscribe({
      next: list => { this.users.set(list); this.loading.set(false); },
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
