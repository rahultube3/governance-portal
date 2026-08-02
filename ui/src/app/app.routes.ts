import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { RequestListComponent } from './components/request-list/request-list.component';
import { RequestFormComponent } from './components/request-form/request-form.component';
import { RequestDetailComponent } from './components/request-detail/request-detail.component';
import { InsightsComponent } from './components/insights/insights.component';
import { HelpComponent } from './components/help/help.component';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'insights', component: InsightsComponent },
  { path: 'help', component: HelpComponent },
  { path: 'requests', component: RequestListComponent },
  { path: 'requests/new', component: RequestFormComponent },
  { path: 'requests/:id', component: RequestDetailComponent },
  { path: 'requests/:id/edit', component: RequestFormComponent },
  { path: '**', redirectTo: '' },
];
