import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { RequestListComponent } from './components/request-list/request-list.component';
import { RequestFormComponent } from './components/request-form/request-form.component';
import { RequestDetailComponent } from './components/request-detail/request-detail.component';
import { InsightsComponent } from './components/insights/insights.component';
import { HelpComponent } from './components/help/help.component';
import { BoardComponent } from './components/board/board.component';
import { KanbanComponent } from './components/kanban/kanban.component';
import { CalendarComponent } from './components/calendar/calendar.component';
import { LoginComponent } from './components/login/login.component';
import { AdminComponent } from './components/admin/admin.component';
import { PermissionsComponent } from './components/permissions/permissions.component';
import { authGuard, guestGuard } from './core/auth.guard';
import { Permission } from './models/user.model';

const needs = (...permissions: Permission[]) => ({ permissions });
const VIEW_REQUESTS = needs('request:view:own', 'request:view:all');

export const routes: Routes = [
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  {
    path: '',
    canActivateChild: [authGuard],
    children: [
      { path: '', component: DashboardComponent },
      { path: 'insights', component: InsightsComponent, data: needs('insights:view') },
      { path: 'board', component: BoardComponent },
      { path: 'kanban', component: KanbanComponent, data: VIEW_REQUESTS },
      { path: 'calendar', component: CalendarComponent, data: needs('calendar:view') },
      { path: 'help', component: HelpComponent },
      { path: 'admin/users', component: AdminComponent, data: needs('user:manage') },
      { path: 'admin/permissions', component: PermissionsComponent, data: needs('role:assign') },
      { path: 'requests', component: RequestListComponent, data: VIEW_REQUESTS },
      { path: 'requests/new', component: RequestFormComponent, data: needs('request:create') },
      { path: 'requests/:id', component: RequestDetailComponent, data: VIEW_REQUESTS },
      { path: 'requests/:id/edit', component: RequestFormComponent, data: needs('request:edit:own', 'request:edit:all') },
    ],
  },
  { path: '**', redirectTo: '' },
];
