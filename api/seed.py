"""Seed the governance DB with sample records for demo/testing.

Generates 5 records for each artifact type, for each month Jan-July 2026.
9 types x 7 months x 5 records = 315 records.
"""
import json, sqlite3, os
from calendar import monthrange
from datetime import date, timedelta
from portal.config import DB_PATH
from portal.db import now_iso
from portal.constants import CRITICAL, LOW
from portal.schema import DEFAULT_PDLC_CHECKPOINTS as PDLC, DEFAULT_REVIEW_TYPES, DEFAULT_REVIEWERS, init_db

YEAR = 2026
MONTHS = list(range(1, 8))  # Jan..Jul

# Every status except DRAFT, which only a signed-in requestor creates.
STATUSES = [
    "SUBMITTED", "IN_REVIEW", "SCHEDULED", "CHIEF_ARCHITECTURE_REVIEW", "CHANGES_REQUESTED",
    "APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "WITHDRAWN",
]

# Per-type seed catalog: 5 title/summary/app tuples per type
CATALOG = {
    "Solution Architecture (SAD)": [
        ("Real-time Fraud Detection Platform", "ARB review for streaming fraud engine", "FraudGuard", "APP-1024"),
        ("Global Trade Settlement Rewrite", "ARB intake for T+1 settlement rearchitecture", "SettleCore", "APP-1025"),
        ("Zero-Trust Network Segmentation", "ARB review for east-west traffic policy", "ZTNet", "APP-1026"),
        ("Digital Wallet Consolidation", "ARB review to merge legacy wallet stacks", "OneWallet", "APP-1027"),
        ("Batch to Micro-batch Migration", "ARB intake for nightly batch modernization", "BatchLift", "APP-1028"),
    ],
    "Data Architecture & Modeling": [
        ("Customer 360 Data Model", "Unified customer profile across LOBs", "Customer360", "APP-2210"),
        ("Lakehouse for Regulatory Reporting", "Bronze/silver/gold layers for CCAR feeds", "RegLake", "APP-2211"),
        ("PII Vault Federation", "Cross-region tokenization catalog", "PIIVault", "APP-2212"),
        ("Master Product Data Hub", "Product MDM ingestion & survivorship", "ProdHub", "APP-2213"),
        ("Analytics Feature Store", "Central feature store for risk & marketing", "FeatureX", "APP-2214"),
    ],
    "Architecture Decision Records (ADR)": [
        ("ADR Adopt Kafka over SQS", "Messaging backbone decision", "Customer360", "APP-2210"),
        ("ADR gRPC for Internal Services", "Service-to-service transport standard", "MeshCore", "APP-3011"),
        ("ADR Postgres for OLTP Baseline", "Default OLTP engine selection", "CoreDB", "APP-3012"),
        ("ADR OpenTelemetry as Trace Std", "Observability trace standardization", "ObsPlatform", "APP-3013"),
        ("ADR Terraform over CloudFormation", "IaC tooling direction", "CloudOps", "APP-3014"),
    ],
    "Event-Driven Architecture Design": [
        ("Event Mesh for Order Pipeline", "Order events pub/sub redesign", "OrderFlow", "APP-3300"),
        ("Kafka Multi-Region DR", "Active/active cluster stretch", "StreamCore", "APP-3301"),
        ("Schema Registry Rollout", "Centralized Avro/Protobuf registry", "SchemaHub", "APP-3302"),
        ("CDC Pipeline for Ledger", "Debezium CDC for ledger replication", "LedgerCDC", "APP-3303"),
        ("MQ to Kafka Migration", "Legacy IBM MQ decommission plan", "MQLift", "APP-3304"),
    ],
    "AI/ML Solution Architecture": [
        ("LLM Copilot for Support", "Support assistant powered by RAG", "SupportAI", "APP-4400"),
        ("Fraud Scoring Model v3", "Gradient boosted fraud classifier refresh", "FraudML", "APP-4401"),
        ("Document AI for KYC", "OCR + NER pipeline for KYC docs", "KYCAI", "APP-4402"),
        ("Marketing Propensity Models", "Next-best-action scoring platform", "PropensityX", "APP-4403"),
        ("Anomaly Detection for Ops", "Time-series anomaly detection for SRE", "AnomOps", "APP-4404"),
    ],
    "Architecture Due Diligence": [
        ("Acquired Robo-Advisor Platform", "Due diligence on target's tech stack and scalability", "RoboAdvise", "APP-5500"),
        ("Market Data Vendor Selection", "Vendor architecture and resiliency assessment", "MktFeed", "APP-5501"),
        ("Custody Partner Integration", "Partner platform security and integration review", "CustodyLink", "APP-5502"),
        ("Crypto Trading Startup Acquisition", "Target architecture, debt and compliance gaps", "CryptoX", "APP-5503"),
        ("Core Banking SaaS Evaluation", "SaaS fit, data residency and exit strategy", "CoreSaaS", "APP-5504"),
    ],
    "API Contract & Design": [
        ("Orders API v2 Contract", "OpenAPI contract for the order capture service", "OrderFlow", "APP-6600"),
        ("Partner Account Aggregation API", "External API for partner account data", "PartnerHub", "APP-6601"),
        ("Quotes Streaming API", "WebSocket contract for real-time quotes", "QuoteStream", "APP-6602"),
        ("Payments API Deprecation Plan", "Sunset of v1 payments endpoints", "PayCore", "APP-6603"),
        ("Internal Identity API", "Token exchange contract for internal services", "IdentityX", "APP-6604"),
    ],
    "Architecture Patterns & Standards": [
        ("Saga Pattern for Order Workflows", "Proposed standard for distributed transactions", "OrderFlow", "APP-6700"),
        ("Strangler Fig Migration Pattern", "Reference pattern for legacy decomposition", "MeshCore", "APP-6701"),
        ("Multi-Region Active/Active Standard", "Resiliency standard for tier-0 services", "CloudOps", "APP-6702"),
        ("Secrets Management Standard", "Vault-based secrets pattern for all apps", "SecOps", "APP-6703"),
        ("Cell-Based Architecture Pattern", "Blast-radius isolation for trading systems", "TradeCore", "APP-6704"),
    ],
    "Architecture Certification": [
        ("Trading Platform Annual Certification", "Yearly architecture recertification", "TradeCore", "APP-6800"),
        ("Mobile App Go-Live Certification", "Production readiness architecture review", "MobileX", "APP-6801"),
        ("Data Lake Platform Certification", "Certification against data platform standards", "RegLake", "APP-6802"),
        ("Cloud Landing Zone Certification", "Landing zone conformance check", "CloudOps", "APP-6803"),
        ("Customer Portal Recertification", "Recertification after major release", "CustPortal", "APP-6804"),
    ],
}

SOLUTION_ARCHITECTS = ["A. Nguyen", "L. Gomez", "P. Shah", "M. Cho", "R. Patel"]
CONTRIBUTORS = ["T. Ito", "K. Lee", "R. Patel, M. Cho", "S. Ng", "J. Alvarez, D. Park"]
BU_REVIEWERS, EA_REVIEWERS, ECS_REVIEWERS = (DEFAULT_REVIEWERS[r] for r in ("BU", "FAE", "ECS"))

COMMENT_BY_STATUS = {
    "SUBMITTED": "Awaiting initial review",
    "IN_REVIEW": "Reviewer assessing the design",
    "SCHEDULED": "Booked for the next ARB meeting",
    "CHIEF_ARCHITECTURE_REVIEW": "Critical risk; waiting for chief architect approval",
    "CHANGES_REQUESTED": "Changes required before re-review",
    "APPROVED": "Approved, cleared for build",
    "APPROVED_WITH_CONDITIONS": "Approved; conditions tracked as follow-ups",
    "REJECTED": "Rejected; design does not meet standards",
    "WITHDRAWN": "Withdrawn by the requestor",
}


AGENT_PASS = {"passed": True, "summary": "Intake is complete and nothing in it suggests more than Low risk.",
              "findings": []}
AGENT_FAIL = {"passed": False, "summary": "The summary is too thin to confirm the change is Low risk.",
              "findings": ["Say which data the change touches and who can reach it."]}


# Seeded statuses follow the tier's route: Low requests leave Submitted at once (agent validation) and skip
# the ARB meeting; only Critical requests reach Chief Architecture Review.
def route_status(status, tier):
    if tier == LOW and status in ("SUBMITTED", "SCHEDULED", "CHIEF_ARCHITECTURE_REVIEW"):
        return "IN_REVIEW"
    if tier != CRITICAL and status == "CHIEF_ARCHITECTURE_REVIEW":
        return "SCHEDULED"
    return status


# The references each review type needs (artifact_names.required_for), plus a default for the rest.
MAIN_REFERENCES = {
    "Solution Architecture (SAD)": ["SAD"],
    "Architecture Decision Records (ADR)": ["SAD", "ADR"],
    "API Contract & Design": ["API_SPEC"],
    "Architecture Due Diligence": ["DUE_DILIGENCE"],
    "Architecture Patterns & Standards": ["PATTERNS"],
    "Data Architecture & Modeling": ["SAD", "DATA_DESIGN"],
    "Event-Driven Architecture Design": ["SAD"],
}
SUPPORTING = ["SAD", "OTHER"]


def seed_artifacts(artifact_type, app_id, seq, i):
    main = MAIN_REFERENCES.get(artifact_type, ["SAD"])
    codes = [*main, *(c for c in SUPPORTING[:i % 3] if c not in main)]
    base = f"https://wiki/gov/{app_id.lower()}/{seq}"
    return [{"code": c, "link": f"{base}/{c.lower().replace('_', '-')}"} for c in codes]


def agent_review(status, tier, submitted):
    if tier != LOW or status == "WITHDRAWN":
        return None
    result = AGENT_PASS if status == "APPROVED" else AGENT_FAIL
    return json.dumps({**result, "checkedAt": f"{submitted}T09:00:00Z"})


def build_rows():
    rows = []
    for artifact_type in DEFAULT_REVIEW_TYPES:
        catalog = CATALOG[artifact_type]
        for month in MONTHS:
            last_day = monthrange(YEAR, month)[1]
            for i in range(5):
                title_base, summary, app_name, app_id = catalog[i]
                day = min(3 + i * 5, last_day)  # spread across the month
                submitted = f"{YEAR:04d}-{month:02d}-{day:02d}"
                tier = 1 + (month + 2 * i) % 4
                status = route_status(STATUSES[(month + i) % len(STATUSES)], tier)
                pdlc = PDLC[(month + i) % len(PDLC)]
                sa = SOLUTION_ARCHITECTS[i % len(SOLUTION_ARCHITECTS)]
                contrib = CONTRIBUTORS[i % len(CONTRIBUTORS)]
                bu = BU_REVIEWERS[i % len(BU_REVIEWERS)]
                ea = EA_REVIEWERS[i % len(EA_REVIEWERS)] if status not in ("SUBMITTED", "WITHDRAWN") else ""
                seq = f"{YEAR}{month:02d}-{i+1:02d}"
                trackit = f"TRK-{YEAR}{month:02d}{i+1:02d}"
                pr = f"PR-{5000 + month * 100 + i}"
                reviewed = submitted if status not in ("SUBMITTED", "WITHDRAWN") else None
                approved = submitted if status in ("APPROVED", "APPROVED_WITH_CONDITIONS") else None
                # Scheduled requests are booked for the ARB meeting two weeks after submission.
                meeting = (date.fromisoformat(submitted) + timedelta(days=14)).isoformat() if status == "SCHEDULED" else None
                meeting_time = f"{10 + i % 5}:00" if meeting else None
                rows.append(dict(
                    arb_title=f"{title_base} ({seq})",
                    summary=summary,
                    artifacts=json.dumps(seed_artifacts(artifact_type, app_id, seq, i)),
                    intelea_capability_link=f"https://intelea.example.com/capabilities/{app_id.lower()}",
                    solution_id=f"SOL-{app_id.split('-')[1]}",
                    pr=pr,
                    app_id=app_id,
                    app_name=app_name,
                    trackit_id=trackit,
                    solution_architect=sa,
                    sa_contributors=contrib,
                    artifact_type=artifact_type,
                    pdlc_checkpoint=pdlc,
                    date_submitted=submitted,
                    date_reviewed=reviewed,
                    bu_gov=json.dumps([bu, BU_REVIEWERS[(i + 1) % len(BU_REVIEWERS)]]),
                    ea_gov=json.dumps([ea] if ea else []),
                    ecs=json.dumps([ECS_REVIEWERS[i % len(ECS_REVIEWERS)]] if ea else []),
                    status=status,
                    approval_date=approved,
                    meeting_date=meeting,
                    meeting_time=meeting_time,
                    comments=COMMENT_BY_STATUS[status],
                    risk_tier=tier,
                    agent_review=agent_review(status, tier, submitted),
                ))
    return rows


# Seeded requests belong to the demo requestor whose name matches the solution architect.
def assign_owners(db: sqlite3.Connection) -> None:
    db.execute("""
        UPDATE requests SET created_by = (
            SELECT u.id FROM users u
            WHERE u.role = 'REQUESTOR' AND u.name = requests.solution_architect
        )
        WHERE created_by IS NULL
    """)
    db.commit()


def run():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db(DB_PATH)
    db = sqlite3.connect(DB_PATH)
    ts = now_iso()
    rows = build_rows()
    for s in rows:
        cur = db.execute("""INSERT INTO requests (
            arb_title, summary, artifacts, intelea_capability_link, solution_id, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewers, ea_gov_reviewers, ecs_reviewers,
            status, approval_date, meeting_date, meeting_time, comments, risk_tier, agent_review,
            created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            s["arb_title"], s["summary"], s["artifacts"], s["intelea_capability_link"], s["solution_id"], s["pr"], s["app_id"],
            s["app_name"], s["trackit_id"], s["solution_architect"], s["sa_contributors"],
            s["artifact_type"], s["pdlc_checkpoint"], s["date_submitted"],
            s["date_reviewed"], s["bu_gov"], s["ea_gov"], s["ecs"],
            s["status"], s["approval_date"], s["meeting_date"], s["meeting_time"], s["comments"],
            s["risk_tier"], s["agent_review"], ts, ts
        ))
        db.execute(
            "INSERT INTO status_history (request_id, from_status, to_status, note, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?)",
            (cur.lastrowid, None, s["status"], "Seeded", ts, ts)
        )
    db.commit()
    assign_owners(db)
    db.close()
    print(f"Seeded {len(rows)} records into {DB_PATH}")


if __name__ == "__main__":
    run()
