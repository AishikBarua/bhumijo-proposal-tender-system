"""
The fixed vocabularies. These were scattered through proposal_server.py and
the HTML as bare strings; having them in one place is what makes a typo in a
status impossible rather than merely unlikely.

Values are exactly those already present in the live data — nothing renamed.
"""

from __future__ import annotations

from enum import Enum


class Entity(str, Enum):
    PD = "P&D"
    FM = "FM"
    WASH = "WASH"
    TECH = "Tech"

    @property
    def display_name(self) -> str:
        return {
            "P&D": "Planning & Design",
            "FM": "Facility Management",
            "WASH": "WASH/Toilets",
            "Tech": "Technology",
        }[self.value]

    @property
    def folder_name(self) -> str:
        # "/" is not allowed in a Windows folder name, so WASH/Toilets became
        # WASH-Toilets on disk. Preserved for the migration and exports.
        return {
            "P&D": "Planning & Design",
            "FM": "Facility Management",
            "WASH": "WASH-Toilets",
            "Tech": "Technology",
        }[self.value]


OTHER_ENTITY_FOLDER = "Other"


class ProposalStatus(str, Enum):
    SUBMITTED = "Submitted"
    YET_TO_BE_SUBMITTED = "Yet to be submitted"
    UNABLE_TO_SUBMIT = "Unable to submit"
    HOLD = "Hold"
    DROP = "Drop"
    BLANK = ""


class ProposalResult(str, Enum):
    ACCEPTED = "Accepted"
    REJECTED = "Rejected"
    WAITING = "Waiting for Result"
    BLANK = ""


class ContractFlag(str, Enum):
    YES = "Yes"
    NO = "No"
    BLANK = ""


class GrantResult(str, Enum):
    FOLLOW_UP = "Follow-up"
    BLANK = ""


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    LOGIN = "login"


class RoleCode(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ENTITY_LEAD = "entity_lead"
    CONTRIBUTOR = "contributor"
    VIEWER = "viewer"


# A proposal counted as "won" for win-rate purposes.
WON_RESULTS = {ProposalResult.ACCEPTED.value}
LOST_RESULTS = {ProposalResult.REJECTED.value}
DECIDED_RESULTS = WON_RESULTS | LOST_RESULTS

# Statuses that mean the proposal is no longer live in the pipeline.
CLOSED_STATUSES = {
    ProposalStatus.DROP.value,
    ProposalStatus.UNABLE_TO_SUBMIT.value,
}


def entity_from_code(code: str | None) -> Entity | None:
    if not code:
        return None
    try:
        return Entity(code)
    except ValueError:
        return None


def entity_folder(code: str | None) -> str:
    entity = entity_from_code(code)
    return entity.folder_name if entity else OTHER_ENTITY_FOLDER
