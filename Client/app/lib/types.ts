// ── Shared / Generic ──────────────────────────

export interface ApiResponse<T = unknown> {
  success: boolean;
  data: T | null;
  error: { message: string } | null;
}

export interface ApiError {
  status: number;
  message: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ── Auth / User ──────────────────────────────

export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  mfa_required?: boolean;
  mfa_token?: string;
  user?: {
    user_id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
    claims: string[];
  };
}

export interface UserRecord {
  id: number;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  role_id: number;
  is_active: boolean;
  mfa_enabled: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface Role {
  id: number;
  name: string;
}

export interface Invite {
  id: number;
  email: string;
  full_name: string;
  role: string;
  token: string;
  expires_at: string;
  used: boolean;
  used_at: string | null;
  created_at: string;
}

export interface InviteResponse {
  invite_id: number;
  token: string;
  email: string;
  expires_at: string;
}

// ── Investor ─────────────────────────────────

export interface InvestorRow {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  manager_id: number | null;
  manager_name: string | null;
  manager_email: string | null;
  initial_capital: number;
  onboarded_at: string | null;
}

export interface ManagerInvestor {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  total_in_funds: number;
  /** Look-through exposure already contained in total_in_funds; never add to AUM. */
  total_in_stocks: number;
  account_count: number;
  onboarded_at: string | null;
}

export interface ManagerOption {
  id: number;
  full_name: string;
  email: string;
}

// ── Fund ─────────────────────────────────────

export interface Fund {
  id: number;
  name: string;
  ticker: string | null;
  description: string | null;
  fund_type: string;
  strategy: string | null;
  asset_class: string | null;
  risk_level: string | null;
  current_price: number | null;
  change_pct: number | null;
  ytd_return: number | null;
  expense_ratio: number | null;
  is_featured: boolean;
  manager_name?: string | null;
  review_status?: string;
  investor_risk_tolerance?: 'conservative' | 'balanced' | 'growth' | 'aggressive';
}

export interface ManagerFund {
  id: number;
  name: string;
  ticker: string | null;
  description: string | null;
  fund_type: string;
  strategy: string;
  risk_level: string | null;
  current_price: number | null;
  is_active: boolean;
  creator_manager_id: number | null;
  manager_name: string | null;
  portfolio_composition: Holding[];
}

export interface Holding {
  symbol: string;
  name: string;
  allocation: number;
  asset_type?: string;
  fund_id?: number;
}

export interface FundInvestmentItem {
  id: number;
  fund_id: number;
  fund_name: string;
  fund_type: string;
  amount: number;
  currency?: string;
  status: string;
  invested_at: string | null;
}

export interface FundInvestor {
  investor_id: number;
  full_name: string;
  email: string;
  amount: number;
  status: string;
  invested_at: string | null;
}

// ── Account ──────────────────────────────────

export interface Account {
  id: number;
  account_name: string;
  account_number: string;
  status: string;
  total_invested: number;
  current_value: number;
  fund_balance: number;
  unallocated_balance: number;
  manager_fund_balance: Record<string, number>;
  fund_allocations: Record<string, number>;
  investment_strategy: string;
}

export type AccountWallet = Pick<
  Account,
  'id' | 'account_name' | 'account_number' | 'fund_balance' | 'investment_strategy'
>;

export type AccountInfo = Pick<
  Account,
  'id' | 'account_name' | 'account_number' | 'fund_balance'
>;

// ── Portfolio ────────────────────────────────

export interface PortfolioSummary {
  total_invested: number;
  total_current_value: number;
  total_fund_balance: number;
  total_account_value: number;
  fund_breakdown: FundBreakdown[];
  fund_positions: FundPosition[];
  accounts: Account[];
  today_pnl: number;
  pnl_as_of_date: string | null;
  pnl: {
    total_pnl: number;
    realized_pnl: number;
    unrealized_pnl: number;
    portfolio_return_pct: number;
    start_date: string;
    end_date: string;
  };
}

export type PnlReport = PortfolioSummary['pnl'];

export interface FundBreakdown {
  fund: string;
  fund_id?: number;
  amount: number;
  units?: number;
  nav_per_unit?: number;
}

export interface FundPosition {
  investment_account_id: number;
  fund_id: number;
  fund: string;
  units: number;
  nav_per_unit: number;
  market_value: number;
  cost_basis: number;
}

export interface Position {
  symbol: string;
  qty: number;
  market_value: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  fund_id?: number;
  fund_name?: string;
}

export interface SellResult {
  order_id: number;
  alpaca_order_id: string;
  symbol: string;
  amount: number;
  status: string;
  position_market_value: number;
  sold_value: number;
  remaining_position: number;
}

export interface InvestResult {
  order_id?: number;
  alpaca_order_id?: string;
  symbol?: string;
  fund_id?: number;
  fund_name?: string;
  amount: number;
  status: string;
  message?: string;
  remaining_balance?: number;
}

// ── Transaction / Order ──────────────────────

export interface Transaction {
  id: number;
  ticket: string;
  trade_type: string;
  symbol: string;
  volume: number;
  price: number;
  net_pnl: number;
  trade_time: string | null;
}

export interface AdminTransaction {
  id: number;
  ticket: string;
  investor_email: string | null;
  investor_name: string | null;
  trade_type: string;
  symbol: string;
  volume: number;
  price: number;
  profit: number;
  commission: number;
  swap: number;
  fee: number;
  net_pnl: number;
  trade_time: string | null;
}

export interface ManagerOrder {
  id: number;
  symbol: string;
  side: string;
  amount: number;
  filled_qty: number | null;
  filled_price: number | null;
  status: string;
  investor_name: string;
  investor_email: string;
  created_at: string;
}

// ── Fund Flows ───────────────────────────────

export interface FundFlowEntry {
  id: number;
  investor_email: string | null;
  investor_name: string | null;
  flow_type: string;
  fund_id?: number | null;
  fund_name?: string | null;
  amount: number;
  paid_amount?: number | null;
  currency: string;
  status: string;
  request_id: string;
  requested_at: string | null;
  processed_at: string | null;
  payment_received_at?: string | null;
  processed_by_email: string | null;
  processed_by_name: string | null;
  notes: string | null;
  status_message?: string;
  next_action?: string;
  settlement_ready?: boolean;
  settlement_message?: string | null;
  payment_url?: string | null;
  provider?: string | null;
  provider_reference?: string | null;
  paynow_qr_data_url?: string | null;
}

export interface PaymentRecord {
  id: number;
  flow_type: string;
  amount: number;
  status: string;
  account_name: string | null;
  account_number: string | null;
  requested_at: string | null;
  processed_at: string | null;
}

// ── Articles ─────────────────────────────────

export interface Article {
  title: string;
  summary: string;
  url: string;
  source: string;
  category: string;
  tickers: string[];
  published_at: string | null;
}

// ── Stock / Market Data ──────────────────────

export interface StockData {
  symbol: string;
  name: string;
  asset_class: string;
  exchange: string;
  price: number;
  change_pct: number;
  change_amt: number;
  daily_high: number;
  daily_low: number;
  daily_volume: number;
  daily_open: number;
  prev_close: number;
  bars: { t: string; o: number; h: number; l: number; c: number; v: number }[];
}

export interface StockResult {
  symbol: string;
  name: string;
  asset_type?: string;
  fund_id?: number;
}

// ── Audit ────────────────────────────────────

export interface AuditLogEntry {
  id: number;
  email: string | null;
  full_name: string | null;
  action: string;
  details: string | null;
  ip_address: string | null;
  created_at: string | null;
}
