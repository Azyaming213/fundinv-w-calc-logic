ROLES = {
    "INVESTOR": "investor",
    "ADMIN": "admin",
    "MANAGER": "manager",
    "OPERATIONS": "operations",
}

CLAIMS = {
    "readDashboard": "readDashboard",
    "readFunds": "readFunds",
    "createFunds": "createFunds",
    "updateFunds": "updateFunds",
    "submitFundsForReview": "submitFundsForReview",
    "reviewFunds": "reviewFunds",
    "manageFundWeights": "manageFundWeights",
    "manageFundTargeting": "manageFundTargeting",
    "depositToFunds": "depositToFunds",
    "withdrawFromFunds": "withdrawFromFunds",
    "readOwnPortfolio": "readOwnPortfolio",
    "exportPortfolio": "exportPortfolio",
    "readArticles": "readArticles",
    "readOwnFundFlows": "readOwnFundFlows",
    "readAllFundFlows": "readAllFundFlows",
    "approveFundFlows": "approveFundFlows",
    "completeFundFlows": "completeFundFlows",
    "rejectFundFlows": "rejectFundFlows",
    "readFeedback": "readFeedback",
    "manageFeedback": "manageFeedback",
    "createFeedback": "createFeedback",
    "readOwnFeedback": "readOwnFeedback",
    "readAssignedInvestors": "readAssignedInvestors",
    "readUsers": "readUsers",
    "writeUsers": "writeUsers",
    "readInvites": "readInvites",
    "writeInvites": "writeInvites",
    "createInvites": "createInvites",
    "requestInvites": "requestInvites",
    "readRoles": "readRoles",
    "readAuditLogs": "readAuditLogs",
    "readSystemStats": "readSystemStats",
    "readTransactions": "readTransactions",
    "readOrders": "readOrders",
    "executeTrades": "executeTrades",
}

CLAIMS_BY_ROLE: dict[str, list[str]] = {
    ROLES["INVESTOR"]: [
        CLAIMS["readDashboard"],
        CLAIMS["readFunds"],
        CLAIMS["depositToFunds"],
        CLAIMS["withdrawFromFunds"],
        CLAIMS["readOwnPortfolio"],
        CLAIMS["exportPortfolio"],
        CLAIMS["readArticles"],
        CLAIMS["readOwnFundFlows"],
        CLAIMS["createFeedback"],
        CLAIMS["readOwnFeedback"],
    ],
    ROLES["MANAGER"]: [
        CLAIMS["readDashboard"],
        CLAIMS["readFunds"],
        CLAIMS["createFunds"],
        CLAIMS["updateFunds"],
        CLAIMS["submitFundsForReview"],
        CLAIMS["manageFundWeights"],
        CLAIMS["manageFundTargeting"],
        CLAIMS["readAssignedInvestors"],
        CLAIMS["readArticles"],
        CLAIMS["readTransactions"],
        CLAIMS["executeTrades"],
    ],
    ROLES["OPERATIONS"]: [
        CLAIMS["readDashboard"],
        CLAIMS["readAllFundFlows"],
        CLAIMS["approveFundFlows"],
        CLAIMS["completeFundFlows"],
        CLAIMS["rejectFundFlows"],
        CLAIMS["reviewFunds"],
        CLAIMS["readAuditLogs"],
        CLAIMS["readFeedback"],
        CLAIMS["manageFeedback"],
        CLAIMS["requestInvites"],
    ],
    ROLES["ADMIN"]: [
        CLAIMS["readDashboard"],
        CLAIMS["readUsers"],
        CLAIMS["writeUsers"],
        CLAIMS["readInvites"],
        CLAIMS["writeInvites"],
        CLAIMS["createInvites"],
        CLAIMS["readRoles"],
        CLAIMS["readAuditLogs"],
        CLAIMS["readSystemStats"],
        CLAIMS["readAllFundFlows"],
        CLAIMS["readFunds"],
        CLAIMS["readTransactions"],
        CLAIMS["readOrders"],
        CLAIMS["readFeedback"],
    ],
}

ROLE_CLAIMS = CLAIMS_BY_ROLE


def has_claim(user, claim_key: str) -> bool:
    if isinstance(user, dict):
        claims = user.get("claims", [])
        return claim_key in claims

    from database import SessionLocal
    from models.role_claim import RoleClaim

    if hasattr(user, "role") and hasattr(user.role, "name"):
        role_name = user.role.name
        cached_claims = CLAIMS_BY_ROLE.get(role_name, [])
        if claim_key in cached_claims:
            return True

    db = SessionLocal()
    try:
        result = db.query(RoleClaim).filter(
            RoleClaim.role_id == user.role_id,
            RoleClaim.claim_key == claim_key,
        ).first()
        return result is not None
    finally:
        db.close()


def has_claim_db(user_role_id: int, claim_key: str, db) -> bool:
    from models.role_claim import RoleClaim

    result = db.query(RoleClaim).filter(
        RoleClaim.role_id == user_role_id,
        RoleClaim.claim_key == claim_key,
    ).first()
    return result is not None


def get_all_roles():
    return list(ROLES.values())


def get_role_display_name(role):
    display_names = {
        ROLES["INVESTOR"]: "Investor",
        ROLES["MANAGER"]: "Manager",
        ROLES["ADMIN"]: "Administrator",
        ROLES["OPERATIONS"]: "Operations",
    }
    return display_names.get(role, role)
