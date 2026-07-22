-- FundInv canonical schema entry point.
-- The previous v0.2.0 DDL defined claim_value/user_role_claims, which does not
-- match the application. Keep this path for existing setup instructions while
-- delegating to the one canonical schema file.
\ir ../table/v0.0.1_init_schema.sql
