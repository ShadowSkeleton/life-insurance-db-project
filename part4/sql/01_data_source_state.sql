-- Part 4 retraining module: source-content lineage
IF OBJECT_ID(N'dbo.DATA_SOURCE_STATE', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.DATA_SOURCE_STATE (
        SourceStateID   INT IDENTITY(1,1) NOT NULL,
        SourcePath      VARCHAR(255) NOT NULL,
        ContentHash     CHAR(64) NOT NULL,
        ByteSize        BIGINT NOT NULL,
        ObservedAt      DATETIME2 NOT NULL,
        ObservedByRunID INT NOT NULL,
        CONSTRAINT DATA_SOURCE_STATE_PK PRIMARY KEY (SourceStateID),
        CONSTRAINT DATA_SOURCE_STATE_RUN_FK FOREIGN KEY (ObservedByRunID)
            REFERENCES dbo.DATA_REFRESH_RUN (RunID)
    );
END;
GO
