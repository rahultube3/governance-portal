import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router, RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from './services/auth.service';

type Theme = 'dark' | 'light';
const THEME_KEY = 'gov-portal-theme';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="shell" *ngIf="auth.user() as me; else signedOut">
      <aside class="sidebar">
        <a routerLink="/" class="brand">
          <span class="glyph" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
              <path d="M12 2 3 7v10l9 5 9-5V7l-9-5Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
              <path d="M12 7v10M7.5 9.5 12 12l4.5-2.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span class="brand-text">
            <span class="brand-name">Governance Portal</span>
            <span class="brand-sub mono">Architecture Review · Self-Service</span>
          </span>
        </a>
        <a *ngIf="auth.can('request:create')" routerLink="/requests/new" class="btn btn-primary nav-cta">
          <svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
          New intake
        </a>
        <nav class="nav">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact:true}">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/>
              <rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>
            </svg>
            Dashboard
          </a>
          <a *ngIf="auth.can('request:view:own', 'request:view:all')" routerLink="/requests" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>
            </svg>
            {{ auth.can('request:view:all') ? 'Requests' : 'My Requests' }}
          </a>
          <a routerLink="/board" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
              <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>
            </svg>
            Board
          </a>
          <a *ngIf="auth.can('request:view:own', 'request:view:all')" routerLink="/kanban" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 7v7M12 7v4M16 7v10"/>
            </svg>
            Kanban Board
          </a>
          <a *ngIf="auth.can('calendar:view')" routerLink="/calendar" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>
            </svg>
            Calendar
          </a>
          <a *ngIf="auth.can('insights:view')" routerLink="/insights" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 3v18h18"/><path d="m7 15 4-5 3 3 5-7"/>
            </svg>
            Insights
          </a>
          <a routerLink="/help" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="9"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3M12 17h.01"/>
            </svg>
            Help
          </a>
          <a *ngIf="auth.can('user:manage')" routerLink="/admin/users" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="8" r="4"/><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1"/>
            </svg>
            Users
          </a>
          <a *ngIf="auth.can('role:assign')" routerLink="/admin/permissions" routerLinkActive="active">
            <svg class="ico" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Z"/><path d="m9 12 2 2 4-4"/>
            </svg>
            Permissions
          </a>
        </nav>
        <div class="side-foot">
          <div class="me" [attr.data-role]="me.role">
            <span class="avatar" aria-hidden="true">{{ initials(me.name) }}</span>
            <span class="me-text">
              <span class="me-name">{{ me.name }}</span>
              <span class="role-tag mono" [title]="'AD groups: ' + (me.adGroups.join(', ') || 'none')">{{ me.roleNames.join(' · ') || 'No access' }}</span>
            </span>
          </div>
          <button
            class="side-btn"
            type="button"
            (click)="toggleTheme()"
            [attr.aria-label]="'Switch to ' + (theme() === 'dark' ? 'light' : 'dark') + ' theme'"
            [title]="'Switch to ' + (theme() === 'dark' ? 'light' : 'dark') + ' theme'">
            <svg *ngIf="theme() === 'dark'" class="ico" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>
            </svg>
            <svg *ngIf="theme() === 'light'" class="ico" viewBox="0 0 24 24">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>
            </svg>
            <span>{{ theme() === 'dark' ? 'Light' : 'Dark' }} theme</span>
          </button>
          <button class="side-btn" type="button" (click)="signOut()" aria-label="Sign out" title="Sign out">
            <svg class="ico" viewBox="0 0 24 24">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <div class="main-col">
        <main class="container page">
          <router-outlet></router-outlet>
        </main>

        <footer class="foot container">
          <span class="mono mute">Brokerage Architecture · Governance Lifecycle</span>
          <span class="mono mute">Draft → Submitted → In Review → Approved</span>
        </footer>
      </div>
    </div>

    <ng-template #signedOut>
      <router-outlet></router-outlet>
    </ng-template>
  `,
  styles: [`
    .shell { display: flex; min-height: 100vh; }
    .sidebar {
      position: sticky; top: 0; height: 100vh; z-index: 20;
      flex: 0 0 236px; box-sizing: border-box;
      display: flex; flex-direction: column; gap: 22px;
      padding: 22px 16px;
      border-right: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 78%, transparent);
      backdrop-filter: blur(10px);
      overflow-y: auto;
    }
    .main-col { flex: 1; min-width: 0; display: flex; flex-direction: column; }

    .brand { display: flex; align-items: center; gap: 12px; color: var(--paper); padding: 0 6px; }
    .brand:hover { text-decoration: none; }
    .glyph { color: var(--cyan); display: grid; place-items: center; }
    .brand-text { display: flex; flex-direction: column; line-height: 1.25; }
    .brand-name { font-family: var(--ff-display); font-weight: 600; font-size: 16px; }
    .brand-sub { font-size: 9.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--mute); }

    .ico {
      width: 18px; height: 18px; flex: 0 0 auto;
      fill: none; stroke: currentColor; stroke-width: 1.6;
      stroke-linecap: round; stroke-linejoin: round;
    }
    .nav-cta { justify-content: center; gap: 8px; color: var(--on-primary) !important; }
    .nav-cta:hover { color: var(--on-primary) !important; text-decoration: none; }

    .nav { display: flex; flex-direction: column; gap: 2px; }
    .nav a {
      position: relative;
      display: flex; align-items: center; gap: 12px;
      color: var(--mute); font-size: 14px; font-weight: 500;
      padding: 9px 12px; border-radius: var(--radius-sm);
      transition: color .15s, background .15s;
    }
    .nav a:hover { color: var(--paper); background: var(--panel-2); text-decoration: none; }
    .nav a.active { color: var(--paper); background: var(--panel-2); }
    .nav a.active::before {
      content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px;
      border-radius: 2px; background: var(--cyan);
    }

    .side-foot {
      margin-top: auto; padding-top: 14px; border-top: 1px solid var(--line-soft);
      display: flex; flex-direction: column; gap: 8px;
    }
    .me { display: flex; align-items: center; gap: 10px; padding: 4px 6px 8px; }
    .me[data-role] { --role: var(--st-ea); }
    .me[data-role="REQUESTOR"] { --role: var(--st-pending); }
    .me[data-role="REVIEWER"] { --role: var(--st-follow); }
    .me[data-role="ADMIN"] { --role: var(--cyan); }
    .avatar {
      flex: 0 0 auto; width: 34px; height: 34px; border-radius: 50%;
      display: grid; place-items: center; font-size: 12px; font-weight: 600;
      color: var(--role); border: 1.5px solid var(--role);
    }
    .me-text { display: flex; flex-direction: column; min-width: 0; line-height: 1.3; }
    .me-name { color: var(--paper); font-size: 13.5px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .role-tag { color: var(--role); font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; }

    .side-btn {
      background: transparent;
      border: 1px solid var(--line);
      color: var(--mute);
      width: 100%; padding: 8px 12px;
      border-radius: var(--radius-sm);
      display: flex; align-items: center; gap: 10px;
      font-size: 13px;
      cursor: pointer;
      transition: color .15s, border-color .15s, background .15s, transform .12s;
    }
    .side-btn:hover { color: var(--paper); border-color: var(--cyan-dim); background: var(--panel-2); }
    .side-btn:active { transform: scale(0.98); }

    .page { flex: 1; width: 100%; box-sizing: border-box; padding: 36px 28px 60px; }
    .foot {
      width: 100%; box-sizing: border-box;
      display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
      padding: 20px 28px; border-top: 1px solid var(--line-soft); font-size: 11px;
    }
    @media (max-width: 760px) {
      .shell { flex-direction: column; }
      .sidebar {
        height: auto; flex: none; flex-direction: row; flex-wrap: wrap; align-items: center;
        gap: 10px 12px; padding: 12px 16px;
        border-right: none; border-bottom: 1px solid var(--line);
      }
      .brand { margin-right: auto; }
      .brand-sub { display: none; }
      .nav { order: 3; flex: 1 0 100%; flex-direction: row; overflow-x: auto; }
      .nav a { white-space: nowrap; padding: 7px 10px; gap: 8px; }
      .nav .ico { width: 16px; height: 16px; }
      .nav a.active::before { left: 10px; right: 10px; top: auto; bottom: 0; width: auto; height: 2px; }
      .side-foot { margin: 0; padding: 0; border: none; flex-direction: row; align-items: center; }
      .me { padding: 0; }
      .me-text { display: none; }
      .side-btn { width: 34px; height: 34px; padding: 0; justify-content: center; border-radius: 999px; }
      .side-btn span { display: none; }
      .page { padding: 24px 16px 48px; }
      .foot { padding: 16px; }
    }
  `],
})
export class AppComponent implements OnInit {
  theme = signal<Theme>('dark');

  constructor(public auth: AuthService, private router: Router) {}

  ngOnInit() {
    const saved = (localStorage.getItem(THEME_KEY) as Theme | null);
    const initial: Theme = saved
      ?? (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    this.applyTheme(initial);
  }

  toggleTheme() {
    this.applyTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  signOut() {
    const done = () => {
      this.auth.clear();
      this.router.navigate(['/login']);
    };
    this.auth.logout().subscribe({ next: done, error: done });
  }

  initials(name: string): string {
    return name.split(/[\s.]+/).filter(Boolean).slice(0, 2).map(p => p[0].toUpperCase()).join('');
  }

  private applyTheme(t: Theme) {
    this.theme.set(t);
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem(THEME_KEY, t);
  }
}
