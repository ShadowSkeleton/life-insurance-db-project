-- Jingrui Feng (jf4446) - database systems project part 3 - schema amendments
-- Part 3 physical schema amendments. The inherited Part 2 DDL remains unchanged.
-- EffectiveDate consolidates application, issue, and effective date for this project.
IF COL_LENGTH('dbo.Contract', 'EffectiveDate') IS NULL
    ALTER TABLE Contract ADD EffectiveDate DATE NULL;
GO
IF COL_LENGTH('dbo.Contract', 'ExpiryDate') IS NULL
    ALTER TABLE Contract ADD ExpiryDate DATE NULL;
GO

-- The inherited model records issued policies but not the applications that
-- produced them. APPLICATION persists the quote-time profile and face amount.
IF OBJECT_ID('dbo.APPLICATION', 'U') IS NULL
BEGIN
    CREATE TABLE APPLICATION (
        ApplicationID       INT IDENTITY(1,1) NOT NULL,
        Customer_CustomerID INT NOT NULL,
        ProductID           INT NOT NULL,
        ApplicationDate     DATE NOT NULL,
        ApplicantAge        INT NOT NULL,
        Gender              VARCHAR(1) NOT NULL,
        SmokingStatus       VARCHAR(10) NOT NULL,
        DiabetesStatus      VARCHAR(10) NOT NULL,
        BMIValue            NUMERIC(5,2) NOT NULL,
        AgeBand             VARCHAR(10) NOT NULL,
        BMIBand             VARCHAR(10) NOT NULL,
        FaceAmount          NUMERIC(12,2) NOT NULL,
        QuotedRateVersionID INT NULL,
        QuotedPremium       NUMERIC(12,2) NULL,
        Status              VARCHAR(10) NOT NULL,
        CONSTRAINT APPLICATION_PK PRIMARY KEY (ApplicationID),
        CONSTRAINT APPLICATION_CUSTOMER_FK FOREIGN KEY (Customer_CustomerID)
            REFERENCES Customer (CustomerID),
        CONSTRAINT APPLICATION_PRODUCT_FK FOREIGN KEY (ProductID)
            REFERENCES Product (ProductID),
        CONSTRAINT APPLICATION_RATEVERSION_FK FOREIGN KEY (QuotedRateVersionID)
            REFERENCES RATE_VERSION (RateVersionID)
    );
END;
GO

IF COL_LENGTH('dbo.Contract', 'ApplicationID') IS NULL
    ALTER TABLE Contract ADD ApplicationID INT NULL;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys WHERE name = 'CONTRACT_APPLICATION_FK'
)
    ALTER TABLE Contract ADD CONSTRAINT CONTRACT_APPLICATION_FK
        FOREIGN KEY (ApplicationID) REFERENCES APPLICATION (ApplicationID);
GO
