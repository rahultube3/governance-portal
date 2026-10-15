# Review types, PDLC checkpoints, reference link names and reviewers live in the DB and are managed on the
# Reference Data admin page; portal/schema.py seeds their defaults into an empty table.
MAX_ARTIFACTS = 5

# Reviewer roles: (code, label, request field, requests column). A request names any number of each role's
# reviewers; the column holds them as a JSON list of names.
REVIEWER_ROLES = [
    ("BU",  "BU Governance Reviewer",  "buGovReviewers", "bu_gov_reviewers"),
    ("FAE", "FAE Governance Reviewer", "eaGovReviewers", "ea_gov_reviewers"),
    ("ECS", "ECS (Security) Reviewer", "ecsReviewers",   "ecs_reviewers"),
]


# Built-in request statuses: (code, default label, meaning, who acts). The review route in portal/workflow.py
# depends on these codes. Admins edit their text, deactivate the optional ones and add their own (pause steps).
REQUEST_STATUSES = [
    ("DRAFT",                     "Draft",                     "Saved, not submitted",                            "Requestor"),
    ("SUBMITTED",                 "Submitted",                 "Waiting for a reviewer to pick it up",            "Reviewer"),
    ("IN_REVIEW",                 "In Review",                 "Reviewer is assessing it",                        "Reviewer"),
    ("CHANGES_REQUESTED",         "Changes Requested",         "Sent back for changes",                           "Requestor"),
    ("SCHEDULED",                 "Scheduled",                 "Booked for an Architecture Review Board meeting", "Admin / Chief Architect / Reviewer"),
    ("CHIEF_ARCHITECTURE_REVIEW", "Chief Architecture Review", "Critical risk: waiting for Chief Architect approval", "Chief Architect"),
    ("APPROVED",                  "Approved",                  "Final approval",                                  "Admin / Chief Architect / Reviewer"),
    ("APPROVED_WITH_CONDITIONS",  "Approved with Conditions",  "Approved, with conditions attached",              "Admin / Chief Architect / Reviewer"),
    ("REJECTED",                  "Rejected",                  "Final rejection",                                 "Admin / Chief Architect / Reviewer"),
    ("WITHDRAWN",                 "Withdrawn",                 "Cancelled by the Requestor",                      "Requestor"),
]

# Built-in statuses an admin may deactivate (no new moves into them). The rest are the review route's backbone
# and always stay active; admin-added statuses can always be deactivated.
DEACTIVATABLE_STATUSES = {"APPROVED_WITH_CONDITIONS", "CHANGES_REQUESTED", "REJECTED", "WITHDRAWN"}

APPROVED_STATUSES = {"APPROVED", "APPROVED_WITH_CONDITIONS"}

# The requestor's own steps: (from, to) -> permission. Fixed, since submitting and withdrawing carry rules
# of their own (submit dates, a chosen risk tier).
OWNER_TRANSITIONS = {
    ("DRAFT", "SUBMITTED"): "request:create",
    ("CHANGES_REQUESTED", "SUBMITTED"): "request:resubmit",
    ("DRAFT", "WITHDRAWN"): "request:withdraw:own",
    ("SUBMITTED", "WITHDRAWN"): "request:withdraw:own",
}

# Fixed risk tiers. The requestor picks one; after submission only a reviewer changes it, and only the
# Chief Architect lowers it. portal/workflow.py turns the tier into the review route.
RISK_TIERS = [
    {"tier": 1, "label": "Low",
     "route": "Agent validation: auto-approved when it passes, otherwise a reviewer decides."},
    {"tier": 2, "label": "Medium", "route": "Reviewer assessment and an ARB meeting; a reviewer decides."},
    {"tier": 3, "label": "High", "route": "Reviewer assessment and an ARB meeting; a reviewer decides."},
    {"tier": 4, "label": "Critical",
     "route": "Reviewer assessment, an ARB meeting, then Chief Architect approval."},
]
LOW, CRITICAL = 1, 4
TIER_LABELS = {t["tier"]: t["label"] for t in RISK_TIERS}

FINAL_STATUSES = ["APPROVED", "APPROVED_WITH_CONDITIONS", "REJECTED", "WITHDRAWN"]

# The API enforces these codes, so the catalog lives in code and is synced into the
# `permissions` table on startup; which role holds which permission lives only in the DB.
PERMISSION_CATALOG = [
    ("request:create",       "Requests",       "Create requests",            "Submit new intake requests."),
    ("request:view:own",     "Requests",       "View own requests",          "See requests you submitted."),
    ("request:view:all",     "Requests",       "View all requests",          "See every request in the portal."),
    ("request:edit:own",     "Requests",       "Edit own requests",          "Edit your own request while DRAFT, SUBMITTED or CHANGES_REQUESTED. Review fields excluded."),
    ("request:edit:all",     "Requests",       "Edit any request",           "Edit any request, including status, review dates and comments."),
    ("request:withdraw:own", "Requests",       "Withdraw own requests",      "Withdraw your own request while it is DRAFT or SUBMITTED."),
    ("request:delete:all",   "Requests",       "Delete any request",         "Permanently delete any request."),
    ("request:resubmit",     "Review",         "Resubmit after changes",      "Send your own request back to SUBMITTED after changes were requested."),
    ("request:review",       "Review",         "Review requests",            "Approve, reject or send back other people's requests."),
    ("request:schedule",     "Review",         "Schedule ARB meetings",      "Move other people's requests to SCHEDULED and set or change the ARB meeting date and time."),
    ("request:signoff",      "Review",         "Chief Architect sign-off",   "Decide Critical-risk requests in CHIEF_ARCHITECTURE_REVIEW and lower a risk tier."),
    ("board:card:edit",      "Team Board",     "Edit board cards",           "Add, edit, move and delete Team Board cards."),
    ("board:field:manage",   "Team Board",     "Manage board fields",        "Add, rename and delete Team Board fields and lanes."),
    ("calendar:view",        "ARB Calendar",   "View ARB calendar",          "Open the Calendar of ARB meetings."),
    ("insights:view",        "Insights",       "View insights",              "Open the Insights scorecard."),
    ("insights:export",      "Insights",       "Export insights",            "Download Insights data as CSV."),
    ("user:manage",          "Administration", "Manage users",               "Add, rename and delete users and set their group."),
    ("reference:manage",     "Administration", "Manage reference data",      "Add, edit, order, activate, deactivate and remove review types, PDLC checkpoints, reference link names and reviewers, and edit status text."),
    ("role:assign",          "Administration", "Assign permissions",         "Edit the permission matrix and create roles."),
]
