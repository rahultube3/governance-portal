import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, ActivatedRoute } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import { GovRequest, Meta } from '../../models/request.model';
import { StatusBadgeComponent } from '../status-badge/status-badge.component';
import { RequestStatusService } from '../../services/request-status.service';

@Component({
  selector: 'app-request-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, StatusBadgeComponent],
  templateUrl: './request-list.component.html',
  styleUrls: ['./request-list.component.css'],
})
export class RequestListComponent implements OnInit {
  requests: GovRequest[] = [];
  meta?: Meta;
  loading = true;

  fStatus = '';
  fType = '';
  fSearch = '';

  constructor(
    private svc: GovernanceService,
    private router: Router,
    private route: ActivatedRoute,
    public auth: AuthService,
    public statuses: RequestStatusService,
  ) {
    statuses.ensureLoaded();
  }

  ngOnInit(): void {
    this.svc.getMeta().subscribe(m => (this.meta = m));
    this.route.queryParams.subscribe(q => {
      this.fStatus = q['status'] || '';
      this.fType = q['artifactType'] || '';
      this.load();
    });
  }

  load(): void {
    this.loading = true;
    this.svc.list({ status: this.fStatus, artifactType: this.fType, search: this.fSearch })
      .subscribe(r => { this.requests = r; this.loading = false; });
  }

  clear(): void {
    this.fStatus = ''; this.fType = ''; this.fSearch = '';
    this.load();
  }

  shortType(t: string): string {
    const m = t.match(/\(([^)]+)\)/);
    if (m) return m[1];
    return t.replace(/ (Intake Request|Submission)$/,'').trim();
  }

  open(r: GovRequest): void {
    this.router.navigate(['/requests', r.id]);
  }
}
