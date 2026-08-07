-- Jingrui Feng (jf4446) - database systems project part 3 - local database deployment
-- Reproducible local deployment. Before execution, copy this file plus the
-- three source files into /tmp/dbsys-p3-deploy inside dbsys-p3-mssql.
CREATE DATABASE LifeInsuranceP3;
GO
USE LifeInsuranceP3;
GO
:r /tmp/dbsys-p3-deploy/schema_final.sql
SELECT 'after base schema' AS deployment_step, COUNT(*) AS table_count FROM sys.tables;
GO
:r /tmp/dbsys-p3-deploy/bridge_schema.sql
SELECT 'after bridge schema' AS deployment_step, COUNT(*) AS table_count FROM sys.tables;
GO
ALTER TABLE Contract ADD IssuedRateVersionID INT NULL;
ALTER TABLE Contract ADD CONSTRAINT CONTRACT_RATEVERSION_FK
    FOREIGN KEY (IssuedRateVersionID) REFERENCES RATE_VERSION (RateVersionID);
ALTER TABLE RATE ADD CONSTRAINT RATE_PRODUCT_FK
    FOREIGN KEY (ProductID) REFERENCES Product (ProductID);
ALTER TABLE WELLNESS_ENROLLMENT ADD CONSTRAINT WENROLL_CONTRACT_FK
    FOREIGN KEY (ContractID) REFERENCES Contract (ContractID);
ALTER TABLE POLICY_RENEWAL ADD CONSTRAINT PRENEW_CONTRACT_FK
    FOREIGN KEY (ContractID) REFERENCES Contract (ContractID);
SELECT 'after post-deployment foreign keys' AS deployment_step, COUNT(*) AS table_count FROM sys.tables;
GO
:r /tmp/dbsys-p3-deploy/schema_amendments.sql
SELECT 'after physical and application amendments' AS deployment_step, COUNT(*) AS table_count FROM sys.tables;
GO
:r /tmp/dbsys-p3-deploy/staging_amendments.sql
SELECT 'after staging amendments' AS deployment_step, COUNT(*) AS table_count FROM sys.tables;
GO
