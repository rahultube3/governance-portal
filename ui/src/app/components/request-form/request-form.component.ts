import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import { GovRequest, Meta, LifecycleStatus } from '../../models/request.model';
import { RequestStatusService } from '../../services/request-status.service';

@Component({
  selector: 'app-request-form',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './request-form.component.html',
  styleUrls: ['./request-form.component.css'],
})
export class RequestFormComponent implements OnInit {
  meta?: Meta;
  editing = false;
  id?: number;
  saving = false;
  error = '';

  model: GovRequest = {
    arbTitle: '',
    summary: '',
    artifactLink: '',
    pr: '',
    appId: '',
    appName: '',
    trackitId: '',
    solutionArchitect: '',
    saContributors: '',
    artifactType: '',
    pdlcCheckpoint: '',
    dateSubmitted: this.today(),
    dateReviewed: '',
    buGovReviewer: '',
    eaGovReviewer: '',
    status: 'SUBMITTED' as LifecycleStatus,
    approvalDate: '',
    meetingDate: '',
    meetingTime: '',
    comments: '',
  };

  constructor(
    private svc: GovernanceService,
    private router: Router,
    private route: ActivatedRoute,
    private auth: AuthService,
    public statuses: RequestStatusService,
  ) {
    statuses.ensureLoaded();
  }

  ngOnInit(): void {
    this.svc.getMeta().subscribe(m => (this.meta = m));
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.editing = true;
      this.id = +idParam;
      this.svc.get(this.id).subscribe(r => (this.model = { ...this.model, ...r }));
    }
  }

  get canEditReview(): boolean {
    return this.auth.can('request:edit:all');
  }

  today(): string {
    return new Date().toISOString().slice(0, 10);
  }

  save(asDraft = false): void {
    this.error = '';
    if (!this.model.arbTitle?.trim()) { this.error = 'ARB Title is required.'; return; }
    if (!this.model.artifactType) { this.error = 'Review Type is required.'; return; }

    this.saving = true;
    const done = (r: GovRequest) => {
      this.saving = false;
      this.router.navigate(['/requests', r.id]);
    };
    const fail = (e: any) => {
      this.saving = false;
      this.error = e?.error?.error || 'Could not save the request. Check the API is running.';
    };

    if (this.editing && this.id) {
      this.svc.update(this.id, this.model).subscribe({ next: done, error: fail });
    } else {
      const status: LifecycleStatus = asDraft ? 'DRAFT' : this.canEditReview ? this.model.status : 'SUBMITTED';
      this.svc.create({ ...this.model, status }).subscribe({ next: done, error: fail });
    }
  }

  cancel(): void {
    if (this.editing && this.id) this.router.navigate(['/requests', this.id]);
    else this.router.navigate(['/requests']);
  }
}
