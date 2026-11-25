-- Data-preserving alter: add nullable badge_color (default NULL).
IF COL_LENGTH('teams', 'badge_color') IS NULL
    ALTER TABLE teams ADD badge_color NVARCHAR(50) NULL;
