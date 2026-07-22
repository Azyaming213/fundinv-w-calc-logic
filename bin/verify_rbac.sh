#!/usr/bin/env bash
# verify_rbac.sh — Log in as each seed user and assert expected 200/403
# Usage: bash bin/verify_rbac.sh [BASE_URL]
#   BASE_URL defaults to http://localhost:8000

set -euo pipefail
BASE_URL="${1:-http://localhost:8000}"
PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

login() {
  local email="$1" password="$2"
  local resp
  resp=$(curl -s -X POST "$BASE_URL/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$email\",\"password\":\"$password\"}")
  echo "$resp" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('data',{}).get('access_token',''))" 2>/dev/null
}

assert_200() {
  local label="$1" method="$2" path="$3" token="$4" body="${5:-}"
  local code
  if [ -z "$body" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path" -H "Authorization: Bearer $token")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body")
  fi
  if [ "$code" = "200" ]; then
    echo -e "  ${GREEN}PASS${NC} ($code) $label"
    ((PASS++))
  else
    echo -e "  ${RED}FAIL${NC} (got $code, expected 200) $label"
    ((FAIL++))
  fi
}

assert_403() {
  local label="$1" method="$2" path="$3" token="$4" body="${5:-}"
  local code
  if [ -z "$body" ]; then
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path" -H "Authorization: Bearer $token")
  else
    code=$(curl -s -o /dev/null -w "%{http_code}" -X "$method" "$BASE_URL$path" -H "Authorization: Bearer $token" -H 'Content-Type: application/json' -d "$body")
  fi
  if [ "$code" = "403" ]; then
    echo -e "  ${GREEN}PASS${NC} ($code) $label"
    ((PASS++))
  else
    echo -e "  ${RED}FAIL${NC} (got $code, expected 403) $label"
    ((FAIL++))
  fi
}

echo "============================================="
echo "FundInv RBAC Verification (v0.2.9 - camelCase claims)"
echo "Target: $BASE_URL"
echo "============================================="

# ── Login as each seed user ──
echo ""
echo -e "${CYAN}Logging in as seed users...${NC}"

ADMIN_TOKEN=$(login "admin@fundinv.com" "admin123")
MANAGER_TOKEN=$(login "manager@fundinv.com" "admin123")
OPS_TOKEN=$(login "operations@fundinv.com" "admin123")
INVESTOR_TOKEN=$(login "investor@fundinv.com" "investor123")
ALICE_TOKEN=$(login "alice@example.com" "investor123")

if [ -z "$ADMIN_TOKEN" ]; then echo -e "${RED}Failed to log in admin${NC}"; exit 1; fi
if [ -z "$MANAGER_TOKEN" ]; then echo -e "${RED}Failed to log in manager${NC}"; exit 1; fi
if [ -z "$OPS_TOKEN" ]; then echo -e "${RED}Failed to log in operations${NC}"; exit 1; fi
if [ -z "$INVESTOR_TOKEN" ]; then echo -e "${RED}Failed to log in investor${NC}"; exit 1; fi
if [ -z "$ALICE_TOKEN" ]; then echo -e "${RED}Failed to log in alice${NC}"; exit 1; fi

echo "  All 5 users logged in successfully."

# ── Admin tests ──
echo ""
echo -e "${CYAN}=== Admin (admin@fundinv.com) ===${NC}"
assert_200 "GET /api/admin/stats"                GET  "/api/admin/stats"               "$ADMIN_TOKEN"
assert_200 "GET /api/admin/fund-flows"           GET  "/api/admin/fund-flows"          "$ADMIN_TOKEN"
assert_200 "GET /api/admin/users"                GET  "/api/admin/users"               "$ADMIN_TOKEN"
assert_200 "GET /api/admin/investors"            GET  "/api/admin/investors"           "$ADMIN_TOKEN"
assert_200 "GET /api/admin/audit-logs"           GET  "/api/admin/audit-logs"          "$ADMIN_TOKEN"
assert_200 "GET /api/admin/transactions"         GET  "/api/admin/transactions"        "$ADMIN_TOKEN"
assert_200 "GET /api/admin/orders"               GET  "/api/admin/orders"              "$ADMIN_TOKEN"
assert_200 "GET /api/auth/invites"               GET  "/api/auth/invites"              "$ADMIN_TOKEN"
assert_200 "GET /api/articles/"                  GET  "/api/articles/"                 "$ADMIN_TOKEN"
assert_200 "GET /api/admin/reconcile"            GET  "/api/admin/reconcile"           "$ADMIN_TOKEN"
assert_403 "POST /api/admin/fund-flows/1/approve" POST "/api/admin/fund-flows/1/approve" "$ADMIN_TOKEN"
assert_403 "POST /api/admin/fund-flows/1/complete" POST "/api/admin/fund-flows/1/complete" "$ADMIN_TOKEN"
assert_403 "POST /api/admin/fund-flows/1/reject"  POST "/api/admin/fund-flows/1/reject"  "$ADMIN_TOKEN"
assert_403 "POST /api/admin/fund-flows/initiate-deposit?investor_email=investor@fundinv.com&amount=100" POST "/api/admin/fund-flows/initiate-deposit?investor_email=investor@fundinv.com&amount=100" "$ADMIN_TOKEN"

# ── Manager tests ──
echo ""
echo -e "${CYAN}=== Manager (manager@fundinv.com) ===${NC}"
assert_200 "GET /api/manager/investors"          GET  "/api/manager/investors"         "$MANAGER_TOKEN"
assert_200 "GET /api/manager/funds"              GET  "/api/manager/funds"             "$MANAGER_TOKEN"
assert_200 "GET /api/manager/transactions"       GET  "/api/manager/transactions?page=1&page_size=5" "$MANAGER_TOKEN"
assert_200 "GET /api/manager/articles"           GET  "/api/manager/articles"          "$MANAGER_TOKEN"
assert_200 "GET /api/articles/"                  GET  "/api/articles/"                 "$MANAGER_TOKEN"
assert_200 "POST /api/manager/fund-assign?investor_id=1&fund_id=1" POST "/api/manager/fund-assign?investor_id=1&fund_id=1" "$MANAGER_TOKEN"
assert_403 "GET /api/admin/fund-flows"           GET  "/api/admin/fund-flows"          "$MANAGER_TOKEN"
assert_403 "GET /api/admin/users"                GET  "/api/admin/users"               "$MANAGER_TOKEN"
assert_403 "GET /api/admin/audit-logs"           GET  "/api/admin/audit-logs"          "$MANAGER_TOKEN"
assert_403 "POST /api/admin/fund-flows/1/approve" POST "/api/admin/fund-flows/1/approve" "$MANAGER_TOKEN"

# ── Operations tests ──
echo ""
echo -e "${CYAN}=== Operations (operations@fundinv.com) ===${NC}"
assert_200 "GET /api/admin/fund-flows"           GET  "/api/admin/fund-flows"          "$OPS_TOKEN"
assert_200 "POST /api/admin/fund-flows/initiate-deposit?investor_email=investor@fundinv.com&amount=500" POST "/api/admin/fund-flows/initiate-deposit?investor_email=investor@fundinv.com&amount=500" "$OPS_TOKEN"
assert_403 "GET /api/admin/users"                GET  "/api/admin/users"               "$OPS_TOKEN"
assert_403 "GET /api/admin/stats"                GET  "/api/admin/stats"               "$OPS_TOKEN"
assert_403 "GET /api/admin/audit-logs"           GET  "/api/admin/audit-logs"          "$OPS_TOKEN"
assert_403 "GET /api/manager/funds"              GET  "/api/manager/funds"             "$OPS_TOKEN"
assert_403 "POST /api/manager/fund-assign?investor_id=1&fund_id=1" POST "/api/manager/fund-assign?investor_id=1&fund_id=1" "$OPS_TOKEN"

# ── Investor tests ──
echo ""
echo -e "${CYAN}=== Investor (investor@fundinv.com) ===${NC}"
assert_200 "GET /api/portfolio/summary"          GET  "/api/portfolio/summary"         "$INVESTOR_TOKEN"
assert_200 "GET /api/funds"                      GET  "/api/funds"                     "$INVESTOR_TOKEN"
assert_200 "GET /api/articles/"                  GET  "/api/articles/"                 "$INVESTOR_TOKEN"
assert_200 "GET /api/portfolio/chart-data"       GET  "/api/portfolio/chart-data"      "$INVESTOR_TOKEN"
assert_403 "GET /api/admin/fund-flows"           GET  "/api/admin/fund-flows"          "$INVESTOR_TOKEN"
assert_403 "GET /api/admin/users"                GET  "/api/admin/users"               "$INVESTOR_TOKEN"
assert_403 "GET /api/admin/audit-logs"           GET  "/api/admin/audit-logs"          "$INVESTOR_TOKEN"
assert_403 "GET /api/manager/investors"          GET  "/api/manager/investors"         "$INVESTOR_TOKEN"

# ── Summary ──
echo ""
echo "============================================="
echo -e "Results: ${GREEN}$PASS passed${NC}, ${RED}$FAIL failed${NC}"
echo "============================================="

# Cleanup — logout each user
for token in "$ADMIN_TOKEN" "$MANAGER_TOKEN" "$OPS_TOKEN" "$INVESTOR_TOKEN" "$ALICE_TOKEN"; do
  curl -s -X POST "$BASE_URL/api/auth/logout" -H "Authorization: Bearer $token" > /dev/null 2>&1 || true
done

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi
exit 0
