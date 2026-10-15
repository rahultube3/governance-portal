import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, ActivatedRoute } from '@angular/router';
import { GovernanceService } from '../../services/governance.service';
import { AuthService } from '../../services/auth.service';
import {
  Artifact, ArtifactName, GovRequest, Meta, LifecycleStatus, NamedOption, Reviewer, ReviewerRole, RiskTier, RiskTierInfo,
} from '../../models/request.model';
import { TierBadgeComponent } from '../tier-badge/tier-badge.component';

@Component({
  selector: 'app-request-form',
  standalone: true,
  imports: [CommonModule, FormsModule, TierBadgeComponent],
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
    artifacts: [{ code: '', link: '' }],
    intelEaCapabilityLink: '',
    solutionId: '',
    pr: '',
    appId: '',
    appName: '',
    trackitId: '',
    solutionArchitect: '',
    saContributors: '',
    artifactType: '',
    pdlcCheckpoint: '',
    buGovReviewers: [],
    eaGovReviewers: [],
    ecsReviewers: [],
    status: 'SUBMITTED' as LifecycleStatus,
    comments: '',
    riskTier: null,
  };

  constructor(
    private svc: GovernanceService,
    private router: Router,
    private route: ActivatedRoute,
    private auth: AuthService,
  ) {}

  ngOnInit(): void {
    this.svc.getMeta().subscribe(m => {
      this.meta = m;
      // A new request starts with every active reviewer of each role ticked; the requestor unticks any they don't want.
      if (!this.editing) {
        for (const role of m.reviewerRoles) {
          this.model[role.field] = m.reviewers.filter(r => r.role === role.code && r.active).map(r => r.name);
        }
      }
    });
    const idParam = this.route.snapshot.paramMap.get('id');
    if (idParam) {
      this.editing = true;
      this.id = +idParam;
      this.svc.get(this.id).subscribe(r => {
        this.model = { ...this.model, ...r, artifacts: r.artifacts?.length ? r.artifacts : [{ code: '', link: '' }] };
      });
    }
  }

  get canEditReview(): boolean {
    return this.auth.can('request:edit:all');
  }

  get artifacts(): Artifact[] {
    return this.model.artifacts!;
  }

  canAddArtifact(): boolean {
    return this.artifacts.length < (this.meta?.maxArtifacts ?? 5);
  }

  addArtifact(): void {
    if (this.canAddArtifact()) this.artifacts.push({ code: '', link: '' });
  }

  removeArtifact(i: number): void {
    this.artifacts.splice(i, 1);
    if (!this.artifacts.length) this.addArtifact();
  }

  // Active review types or PDLC checkpoints, plus a deactivated one the request already holds.
  optionsFor(options: NamedOption[] | undefined, current: string | undefined): NamedOption[] {
    return (options ?? []).filter(o => o.active || o.name === current);
  }

  // Active names, plus a deactivated one the row already holds so editing doesn't clear it.
  choicesFor(a: Artifact): ArtifactName[] {
    return (this.meta?.artifactNames ?? []).filter(n => n.active || n.code === a.code);
  }

  // Active reviewers of the role (sorted by name by the API), plus deactivated ones the request already names.
  reviewersFor(role: ReviewerRole): Reviewer[] {
    const picked = this.model[role.field] ?? [];
    return (this.meta?.reviewers ?? []).filter(r => r.role === role.code && (r.active || picked.includes(r.name)));
  }

  isPicked(role: ReviewerRole, name: string): boolean {
    return (this.model[role.field] ?? []).includes(name);
  }

  togglePicked(role: ReviewerRole, name: string, picked: boolean): void {
    const names = this.model[role.field] ?? [];
    this.model[role.field] = picked ? [...names, name] : names.filter(n => n !== name);
  }

  // References the chosen review type must carry before submission, e.g. ADR needs both SAD and ADR.
  requiredArtifacts(): ArtifactName[] {
    return (this.meta?.artifactNames ?? []).filter(n => n.active && n.requiredFor.includes(this.model.artifactType));
  }

  // The first row holding each required reference is locked until the review type changes.
  isRequiredRow(i: number): boolean {
    const code = this.artifacts[i].code;
    return !!code && this.requiredArtifacts().some(n => n.code === code)
      && this.artifacts.findIndex(a => a.code === code) === i;
  }

  // e.g. "Architecture Decision Records (ADR) requests need SAD and ADR reference links."
  requirementText(names: ArtifactName[]): string {
    const labels = names.map(n => n.label);
    const what = labels.length === 1
      ? `${/^[aeiou]/i.test(labels[0]) ? 'an' : 'a'} ${labels[0]} reference link`
      : `${labels.join(' and ')} reference links`;
    return `${this.model.artifactType} requests need ${what}.`;
  }

  // Each review type change rebuilds the rows: the new type's required references first (reusing a row that
  // already has a link for them), then any other row with a link. Empty rows, including the previous type's
  // pre-filled ones, are dropped, so typed links are never lost.
  onTypeChange(): void {
    const filled = this.artifacts.filter(a => a.link.trim());
    const required = this.requiredArtifacts().map(n => filled.find(a => a.code === n.code) ?? { code: n.code, link: '' });
    const rows = [...required, ...filled.filter(a => !required.includes(a))];
    this.model.artifacts = rows.length ? rows : [{ code: '', link: '' }];
  }

  // After submission only a reviewer changes the tier, from the request page.
  get tierLocked(): boolean {
    return this.editing && this.model.status !== 'DRAFT';
  }

  tierInfo(tier: RiskTier | null | undefined): RiskTierInfo | undefined {
    return this.meta?.riskTiers.find(t => t.tier === tier);
  }

  save(asDraft = false): void {
    this.error = '';
    if (!this.model.arbTitle?.trim()) { this.error = 'ARB Title is required.'; return; }
    if (!this.model.artifactType) { this.error = 'Review Type is required.'; return; }
    const status: LifecycleStatus = this.editing ? this.model.status : asDraft ? 'DRAFT' : 'SUBMITTED';
    if (status !== 'DRAFT' && !this.model.riskTier) { this.error = 'Choose a risk tier before submitting.'; return; }
    if (status !== 'DRAFT' && !this.model.intelEaCapabilityLink?.trim()) { this.error = 'IntelEA Capability Link is required.'; return; }
    const artifacts = this.artifacts
      .map(a => ({ code: a.code, link: a.link.trim() }))
      .filter(a => a.code || a.link);
    if (artifacts.some(a => !a.code || !a.link)) { this.error = 'Each Architecture Reference Link needs a name and a link or text.'; return; }
    const missing = this.requiredArtifacts().filter(n => !artifacts.some(a => a.code === n.code));
    if (status !== 'DRAFT' && missing.length) {
      this.error = this.requirementText(missing);
      return;
    }
    // Status, review dates and the ARB meeting are set by lifecycle actions on the request page, not here.
    const { status: _status, dateReviewed, approvalDate, meetingDate, meetingTime, ...fields } = this.model;

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
      this.svc.update(this.id, { ...fields, artifacts }).subscribe({ next: done, error: fail });
    } else {
      this.svc.create({ ...fields, status, artifacts }).subscribe({ next: done, error: fail });
    }
  }

  cancel(): void {
    if (this.editing && this.id) this.router.navigate(['/requests', this.id]);
    else this.router.navigate(['/requests']);
  }
}
