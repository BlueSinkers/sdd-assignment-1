-- Teams service initial schema (SQL Server dialect).

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'teams')
CREATE TABLE teams (
    id             INT            IDENTITY(1,1) NOT NULL PRIMARY KEY,
    name           NVARCHAR(40)   NOT NULL,
    password_hash  NVARCHAR(255)  NOT NULL,
    captain_name   NVARCHAR(100)  NOT NULL,
    format         NVARCHAR(10)   NOT NULL,
    player_count   INT            NOT NULL,
    skill_level    NVARCHAR(20)   NOT NULL,
    district       NVARCHAR(100)  NULL,
    created_at     DATETIME2      NOT NULL CONSTRAINT DF_teams_created_at DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_teams_name UNIQUE (name),
    CONSTRAINT CK_teams_format CHECK (format IN (N'3v3', N'5v5')),
    CONSTRAINT CK_teams_skill CHECK (skill_level IN (N'casual', N'intermediate', N'competitive')),
    CONSTRAINT CK_teams_player_count CHECK (player_count > 0)
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'health_check')
CREATE TABLE health_check (
    id          INT       IDENTITY(1,1) NOT NULL PRIMARY KEY,
    checked_at  DATETIME2 NOT NULL CONSTRAINT DF_health_check_checked_at DEFAULT SYSUTCDATETIME()
);
