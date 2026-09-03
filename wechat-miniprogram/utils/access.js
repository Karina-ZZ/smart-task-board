/**
 * Feature 04: Client-side permission projection.
 * Responsibilities: consume server-projected route capabilities for UI visibility only.
 * Does not own: authorization decisions, task state, or data-scope enforcement.
 * Plan task: WECHAT-MP-04.
 */

function canAccessExecutive(user) {
  return !!user?.permissions?.canAccessExecutive;
}

function canAccessRoute(user, route) {
  const allowed = user?.permissions?.allowedRoutes || [];
  return allowed.includes(route);
}

function relationsOf(item) {
  return Array.from(new Set(item?.currentUserRelations || []));
}

module.exports = { canAccessExecutive, canAccessRoute, relationsOf };
