-- Part 4 amendment: one renewal per contract and renewal date.
-- Existing data is checked before deployment by the Part 4 verification flow.
IF NOT EXISTS (
    SELECT 1
    FROM sys.key_constraints
    WHERE parent_object_id = OBJECT_ID(N'dbo.POLICY_RENEWAL')
      AND name = N'UQ_POLICY_RENEWAL_ContractID_RenewalDate'
)
BEGIN
    ALTER TABLE dbo.POLICY_RENEWAL
        ADD CONSTRAINT UQ_POLICY_RENEWAL_ContractID_RenewalDate
        UNIQUE (ContractID, RenewalDate);
END;
GO
