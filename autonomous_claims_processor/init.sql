-- ============================================================
-- Database Initialization Script
-- ============================================================

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text similarity search

-- Note: Tables are created by SQLAlchemy ORM on application startup
-- This script is for additional database setup if needed

-- Create index for faster policy number lookups
CREATE INDEX IF NOT EXISTS idx_policies_number ON policies(policy_number);

-- Create index for faster claim lookups
CREATE INDEX IF NOT EXISTS idx_claims_claim_id ON claims(claim_id);
CREATE INDEX IF NOT EXISTS idx_claims_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claims_fnol ON claims(fnol_received);

-- Create index for audit logs
CREATE INDEX IF NOT EXISTS idx_audit_logs_claim_timestamp ON audit_logs(claim_id, timestamp DESC);

-- Insert sample policy (for testing)
INSERT INTO policies (
    id, policy_number, policy_form, policy_type,
    policyholder_name, policyholder_dob, policyholder_address,
    policyholder_phone, policyholder_email,
    effective_date, expiration_date,
    coverage_a_limit, coverage_b_limit, coverage_c_limit, coverage_d_limit,
    all_peril_deductible, wind_hail_deductible,
    status, state_of_issue
) VALUES (
    uuid_generate_v4(),
    'POL-2024-001',
    'HO-3',
    'Property',
    'John Smith',
    '1980-05-15',
    '123 Main Street, Austin, TX 78701',
    '512-555-0100',
    'john.smith@email.com',
    '2024-01-01',
    '2025-01-01',
    300000, 30000, 150000, 60000,
    1000, 2000,
    'ACTIVE',
    'TX'
) ON CONFLICT (policy_number) DO NOTHING;

-- Insert sample policy 2
INSERT INTO policies (
    id, policy_number, policy_form, policy_type,
    policyholder_name, policyholder_dob, policyholder_address,
    policyholder_phone, policyholder_email,
    effective_date, expiration_date,
    coverage_a_limit, coverage_b_limit, coverage_c_limit, coverage_d_limit,
    all_peril_deductible, wind_hail_deductible,
    status, state_of_issue
) VALUES (
    uuid_generate_v4(),
    'POL-2024-002',
    'DP-1',
    'Auto',
    'Jane Doe',
    '1985-08-22',
    '456 Oak Avenue, Dallas, TX 75201',
    '214-555-0200',
    'jane.doe@email.com',
    '2024-02-01',
    '2025-02-01',
    250000, 25000, 125000, 50000,
    500, 1000,
    'ACTIVE',
    'TX'
) ON CONFLICT (policy_number) DO NOTHING;
