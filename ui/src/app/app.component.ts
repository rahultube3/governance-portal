import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';

type Theme = 'dark' | 'light';
const THEME_KEY = 'gov-portal-theme';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header class="topbar">
      <div class="container bar-inner">
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
        <nav class="nav">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact:true}">Dashboard</a>
          <a routerLink="/requests" routerLinkActive="active">Requests</a>
          <a routerLink="/insights" routerLinkActive="active">Insights</a>
          <button
            class="theme-toggle"
            type="button"
            (click)="toggleTheme()"
            [attr.aria-label]="'Switch to ' + (theme() === 'dark' ? 'light' : 'dark') + ' theme'"
            [title]="'Switch to ' + (theme() === 'dark' ? 'light' : 'dark') + ' theme'">
            <svg *ngIf="theme() === 'dark'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="4"/>
              <path d="M12 3v2M12 19v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M3 12h2M19 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>
            </svg>
            <svg *ngIf="theme() === 'light'" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/>
            </svg>
          </button>
          <a routerLink="/requests/new" class="btn btn-primary nav-cta">New intake</a>
        </nav>
      </div>
    </header>

    <main class="container page">
      <router-outlet></router-outlet>
    </main>

    <footer class="foot container">
      <span class="mono mute">Enterprise Architecture · Governance Lifecycle</span>
      <span class="mono mute">PENDING → APPROVED FB → APPROVED EA → FOLLOW UP → REWORK</span>
    </footer>
  `,
  styles: [`
    .topbar {
      position: sticky; top: 0; z-index: 20;
      border-bottom: 1px solid var(--line);
      background: color-mix(in srgb, var(--panel) 78%, transparent);
      backdrop-filter: blur(10px);
    }
    .bar-inner { display: flex; align-items: center; justify-content: space-between; height: 66px; }
    .brand { display: flex; align-items: center; gap: 12px; color: var(--paper); }
    .brand:hover { text-decoration: none; }
    .glyph { color: var(--cyan); display: grid; place-items: center; }
    .brand-text { display: flex; flex-direction: column; line-height: 1.15; }
    .brand-name { font-family: var(--ff-display); font-weight: 600; font-size: 16px; }
    .brand-sub { font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--mute); }
    .nav { display: flex; align-items: center; gap: 22px; }
    .nav a { color: var(--mute); font-size: 14px; font-weight: 500; }
    .nav a:hover { color: var(--paper); text-decoration: none; }
    .nav a.active { color: var(--paper); }
    .nav a.active:not(.nav-cta) { position: relative; }
    .nav a.active:not(.nav-cta)::after {
      content: ""; position: absolute; left: 0; right: 0; bottom: -22px; height: 2px; background: var(--cyan);
    }
    .nav-cta { color: var(--on-primary) !important; }
    .nav-cta:hover { color: var(--on-primary) !important; }

    .theme-toggle {
      background: transparent;
      border: 1px solid var(--line);
      color: var(--mute);
      width: 34px; height: 34px;
      border-radius: 999px;
      display: inline-flex; align-items: center; justify-content: center;
      cursor: pointer;
      transition: color .15s, border-color .15s, background .15s, transform .12s;
    }
    .theme-toggle:hover { color: var(--paper); border-color: var(--cyan-dim); background: var(--panel-2); }
    .theme-toggle:active { transform: scale(0.94); }

    .page { padding: 36px 28px 60px; min-height: calc(100vh - 66px - 60px); }
    .foot {
      display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;
      padding: 20px 28px; border-top: 1px solid var(--line-soft); font-size: 11px;
    }
    @media (max-width: 640px) {
      .brand-sub { display: none; }
      .nav { gap: 12px; }
      .nav a:not(.nav-cta) { display: none; }
    }
  `],
})
export class AppComponent implements OnInit {
  theme = signal<Theme>('dark');

  ngOnInit() {
    const saved = (localStorage.getItem(THEME_KEY) as Theme | null);
    const initial: Theme = saved
      ?? (window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    this.applyTheme(initial);
  }

  toggleTheme() {
    this.applyTheme(this.theme() === 'dark' ? 'light' : 'dark');
  }

  private applyTheme(t: Theme) {
    this.theme.set(t);
    document.documentElement.setAttribute('data-theme', t);
    localStorage.setItem(THEME_KEY, t);
  }
}
