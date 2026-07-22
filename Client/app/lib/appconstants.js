export const ROLES = {
    INVESTOR: 'investor',
    OPERATIONS: 'operations',
    MANAGER: 'manager',
    ADMIN: 'admin',
};

export const CLAIMS = {
    readDashboard: 'readDashboard',
    readFunds: 'readFunds',
    createFunds: 'createFunds',
    updateFunds: 'updateFunds',
    submitFundsForReview: 'submitFundsForReview',
    reviewFunds: 'reviewFunds',
    manageFundWeights: 'manageFundWeights',
    manageFundTargeting: 'manageFundTargeting',
    depositToFunds: 'depositToFunds',
    withdrawFromFunds: 'withdrawFromFunds',
    readOwnPortfolio: 'readOwnPortfolio',
    exportPortfolio: 'exportPortfolio',
    readArticles: 'readArticles',
    readOwnFundFlows: 'readOwnFundFlows',
    readAllFundFlows: 'readAllFundFlows',
    approveFundFlows: 'approveFundFlows',
    completeFundFlows: 'completeFundFlows',
    rejectFundFlows: 'rejectFundFlows',
    readAssignedInvestors: 'readAssignedInvestors',
    readUsers: 'readUsers',
    writeUsers: 'writeUsers',
    readInvites: 'readInvites',
    writeInvites: 'writeInvites',
    createInvites: 'createInvites',
    requestInvites: 'requestInvites',
    readRoles: 'readRoles',
    readAuditLogs: 'readAuditLogs',
    readSystemStats: 'readSystemStats',
    readTransactions: 'readTransactions',
    readOrders: 'readOrders',
    executeTrades: 'executeTrades',
    readFeedback: 'readFeedback',
    manageFeedback: 'manageFeedback',
    createFeedback: 'createFeedback',
    readOwnFeedback: 'readOwnFeedback',
};

export const CLAIMS_BY_ROLE = {
    [ROLES.INVESTOR]: [
        CLAIMS.readDashboard,
        CLAIMS.readFunds,
        CLAIMS.depositToFunds,
        CLAIMS.withdrawFromFunds,
        CLAIMS.readOwnPortfolio,
        CLAIMS.exportPortfolio,
        CLAIMS.readArticles,
        CLAIMS.readOwnFundFlows,
        CLAIMS.createFeedback,
        CLAIMS.readOwnFeedback,
    ],
    [ROLES.MANAGER]: [
        CLAIMS.readDashboard,
        CLAIMS.readFunds,
        CLAIMS.createFunds,
        CLAIMS.updateFunds,
        CLAIMS.manageFundWeights,
        CLAIMS.manageFundTargeting,
        CLAIMS.readAssignedInvestors,
        CLAIMS.readArticles,
        CLAIMS.readTransactions,
        CLAIMS.executeTrades,
        CLAIMS.submitFundsForReview,
    ],
    [ROLES.OPERATIONS]: [
        CLAIMS.readDashboard,
        CLAIMS.readAllFundFlows,
        CLAIMS.approveFundFlows,
        CLAIMS.completeFundFlows,
        CLAIMS.rejectFundFlows,
        CLAIMS.reviewFunds,
        CLAIMS.readAuditLogs,
        CLAIMS.readFeedback,
        CLAIMS.manageFeedback,
        CLAIMS.requestInvites,
    ],
    [ROLES.ADMIN]: [
        CLAIMS.readDashboard,
        CLAIMS.readUsers,
        CLAIMS.writeUsers,
        CLAIMS.readInvites,
        CLAIMS.writeInvites,
        CLAIMS.createInvites,
        CLAIMS.readRoles,
        CLAIMS.readAuditLogs,
        CLAIMS.readSystemStats,
        CLAIMS.readAllFundFlows,
        CLAIMS.readFunds,
        CLAIMS.readTransactions,
        CLAIMS.readOrders,
        CLAIMS.readFeedback,
    ],
};

export const ROLE_CLAIMS = CLAIMS_BY_ROLE;

export const userHasClaim = (user, claim) => {
    if (!user || !user.claims) return false;
    return user.claims.includes(claim);
};

export const userInRole = (user, role) => {
    if (!user) return false;
    return user.role === role;
};

export const getAllRoles = () => Object.values(ROLES);

export const getRoleDisplayName = (role) => {
    const displayNames = {
        [ROLES.INVESTOR]: 'Investor',
        [ROLES.OPERATIONS]: 'Operations',
        [ROLES.MANAGER]: 'Manager',
        [ROLES.ADMIN]: 'Administrator',
    };
    return displayNames[role] || role;
};

export default {
    ROLES,
    CLAIMS,
    CLAIMS_BY_ROLE,
    ROLE_CLAIMS,
    userHasClaim,
    userInRole,
    getAllRoles,
    getRoleDisplayName,
};
