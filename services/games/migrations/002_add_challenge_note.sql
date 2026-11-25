-- Data-preserving: add an optional note captains can attach to a challenge.
IF COL_LENGTH('challenges', 'note') IS NULL
    ALTER TABLE challenges ADD note NVARCHAR(200) NULL;
