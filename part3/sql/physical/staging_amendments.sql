-- Jingrui Feng (jf4446) - database systems project part 3 - brfss staging amendment
-- Part 3 staging amendment. The inherited Part 2 bridge DDL remains unchanged.
-- This table preserves BRFSS individual-record grain; STG_BRFSS remains the
-- database-derived summary-grain table used by the DIKW transition.
CREATE TABLE STG_BRFSS_RECORD (
    StgBRFSSRecordID INT IDENTITY(1,1) NOT NULL,
    SourceYear       INT            NOT NULL,
    AgeBand          VARCHAR(10)    NULL,
    Gender           VARCHAR(1)     NULL,
    SmokingStatus    VARCHAR(10)    NULL,
    DiabetesStatus   VARCHAR(10)    NULL,
    BMIBand          VARCHAR(10)    NULL,
    ExerciseFreq     VARCHAR(10)    NULL,
    BMIValue         NUMERIC(5,2)   NULL,
    LoadDate         DATE           NOT NULL,
    SourceFile       VARCHAR(255)   NOT NULL,
    CONSTRAINT STG_BRFSS_RECORD_PK PRIMARY KEY (StgBRFSSRecordID)
);
