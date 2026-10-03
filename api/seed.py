"""Seed the governance DB with sample records for demo/testing.

Generates 5 records for each artifact type, for each month Jan-July 2026.
5 types x 7 months x 5 records = 175 records.
"""
import sqlite3, os
from calendar import monthrange
from datetime import date, timedelta
from portal.config import DB_PATH
from portal.db import now_iso
from portal.constants import ARTIFACT_TYPES, PDLC_CHECKPOINTS as PDLC
from portal.schema import init_db

YEAR = 2026
MONTHS = list(range(1, 8))  # Jan..Jul

# Every status except DRAFT, which only a signed-in requestor creates.
STATUSES = [
    "SUBMITTED", "IN_REVIEW", "SCHEDULED", "CHIEF_ARCHITECTURE_REVIEW", "CHANGES_REQUESTED",
    "APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "WITHDRAWN",
]

# Per-type seed catalog: 5 title/summary/app tuples per type
CATALOG = {
    "Architecture Review Board (ARB) Intake Request": [
        ("Real-time Fraud Detection Platform", "ARB review for streaming fraud engine", "FraudGuard", "APP-1024"),
        ("Global Trade Settlement Rewrite", "ARB intake for T+1 settlement rearchitecture", "SettleCore", "APP-1025"),
        ("Zero-Trust Network Segmentation", "ARB review for east-west traffic policy", "ZTNet", "APP-1026"),
        ("Digital Wallet Consolidation", "ARB review to merge legacy wallet stacks", "OneWallet", "APP-1027"),
        ("Batch to Micro-batch Migration", "ARB intake for nightly batch modernization", "BatchLift", "APP-1028"),
    ],
    "Data Architecture Intake Request": [
        ("Customer 360 Data Model", "Unified customer profile across LOBs", "Customer360", "APP-2210"),
        ("Lakehouse for Regulatory Reporting", "Bronze/silver/gold layers for CCAR feeds", "RegLake", "APP-2211"),
        ("PII Vault Federation", "Cross-region tokenization catalog", "PIIVault", "APP-2212"),
        ("Master Product Data Hub", "Product MDM ingestion & survivorship", "ProdHub", "APP-2213"),
        ("Analytics Feature Store", "Central feature store for risk & marketing", "FeatureX", "APP-2214"),
    ],
    "Architecture Decision Record (ADR) Submission": [
        ("ADR Adopt Kafka over SQS", "Messaging backbone decision", "Customer360", "APP-2210"),
        ("ADR gRPC for Internal Services", "Service-to-service transport standard", "MeshCore", "APP-3011"),
        ("ADR Postgres for OLTP Baseline", "Default OLTP engine selection", "CoreDB", "APP-3012"),
        ("ADR OpenTelemetry as Trace Std", "Observability trace standardization", "ObsPlatform", "APP-3013"),
        ("ADR Terraform over CloudFormation", "IaC tooling direction", "CloudOps", "APP-3014"),
    ],
    "Messaging & Streaming Architecture Intake Request": [
        ("Event Mesh for Order Pipeline", "Order events pub/sub redesign", "OrderFlow", "APP-3300"),
        ("Kafka Multi-Region DR", "Active/active cluster stretch", "StreamCore", "APP-3301"),
        ("Schema Registry Rollout", "Centralized Avro/Protobuf registry", "SchemaHub", "APP-3302"),
        ("CDC Pipeline for Ledger", "Debezium CDC for ledger replication", "LedgerCDC", "APP-3303"),
        ("MQ to Kafka Migration", "Legacy IBM MQ decommission plan", "MQLift", "APP-3304"),
    ],
    "AI/ML Architecture Intake Request": [
        ("LLM Copilot for Support", "Support assistant powered by RAG", "SupportAI", "APP-4400"),
        ("Fraud Scoring Model v3", "Gradient boosted fraud classifier refresh", "FraudML", "APP-4401"),
        ("Document AI for KYC", "OCR + NER pipeline for KYC docs", "KYCAI", "APP-4402"),
        ("Marketing Propensity Models", "Next-best-action scoring platform", "PropensityX", "APP-4403"),
        ("Anomaly Detection for Ops", "Time-series anomaly detection for SRE", "AnomOps", "APP-4404"),
    ],
}

SOLUTION_ARCHITECTS = ["A. Nguyen", "L. Gomez", "P. Shah", "M. Cho", "R. Patel"]
CONTRIBUTORS = ["T. Ito", "K. Lee", "R. Patel, M. Cho", "S. Ng", "J. Alvarez, D. Park"]
BU_REVIEWERS = ["J. Rivera", "D. Fox", "H. Bello", "N. Osei", "C. Weiss"]
EA_REVIEWERS = ["S. Kaplan", "V. Iyer", "B. O'Neil", "F. Marchetti", "E. Sato"]

COMMENT_BY_STATUS = {
    "SUBMITTED": "Awaiting initial review",
    "IN_REVIEW": "Reviewer assessing the design",
    "SCHEDULED": "Booked for the next ARB meeting",
    "CHIEF_ARCHITECTURE_REVIEW": "Escalated for chief architect sign-off",
    "CHANGES_REQUESTED": "Changes required before re-review",
    "APPROVED": "Approved, cleared for build",
    "APPROVED_WITH_CONDITIONS": "Approved; conditions tracked as follow-ups",
    "REJECTED": "Rejected; design does not meet standards",
    "WITHDRAWN": "Withdrawn by the requestor",
}


def build_rows():
    rows = []
    for artifact_type in ARTIFACT_TYPES:
        catalog = CATALOG[artifact_type]
        for month in MONTHS:
            last_day = monthrange(YEAR, month)[1]
            for i in range(5):
                title_base, summary, app_name, app_id = catalog[i]
                day = min(3 + i * 5, last_day)  # spread across the month
                submitted = f"{YEAR:04d}-{month:02d}-{day:02d}"
                status = STATUSES[(month + i) % len(STATUSES)]
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
                    artifact_link=f"https://wiki/gov/{app_id.lower()}/{seq}",
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
                    bu_gov=bu,
                    ea_gov=ea,
                    status=status,
                    approval_date=approved,
                    meeting_date=meeting,
                    meeting_time=meeting_time,
                    comments=COMMENT_BY_STATUS[status],
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
            arb_title, summary, artifact_link, pr, app_id, app_name, trackit_id,
            solution_architect, sa_contributors, artifact_type, pdlc_checkpoint,
            date_submitted, date_reviewed, bu_gov_reviewer, ea_gov_reviewer,
            status, approval_date, meeting_date, meeting_time, comments, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            s["arb_title"], s["summary"], s["artifact_link"], s["pr"], s["app_id"],
            s["app_name"], s["trackit_id"], s["solution_architect"], s["sa_contributors"],
            s["artifact_type"], s["pdlc_checkpoint"], s["date_submitted"],
            s["date_reviewed"], s["bu_gov"], s["ea_gov"],
            s["status"], s["approval_date"], s["meeting_date"], s["meeting_time"], s["comments"], ts, ts
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
