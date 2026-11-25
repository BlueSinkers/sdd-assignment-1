-- Games domain: courts, challenges, attendance.
-- Team ids are plain integers (no FK to Teams); court_id keeps a real FK.

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'courts')
CREATE TABLE courts (
    id                   INT            NOT NULL IDENTITY(1,1) PRIMARY KEY,
    name                 NVARCHAR(200)  NULL,
    address              NVARCHAR(200)  NOT NULL,
    maps_url             NVARCHAR(500)  NULL,
    proposed_by_team_id  INT            NOT NULL,
    created_at           DATETIME2      NOT NULL CONSTRAINT DF_courts_created DEFAULT SYSUTCDATETIME(),
    CONSTRAINT UQ_courts_address UNIQUE (address)
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'challenges')
CREATE TABLE challenges (
    id                  INT            NOT NULL IDENTITY(1,1) PRIMARY KEY,
    challenger_team_id  INT            NOT NULL,
    opponent_team_id    INT            NOT NULL,
    court_id            INT            NOT NULL,
    start_time          NVARCHAR(16)   NOT NULL,
    format              NVARCHAR(10)   NOT NULL,
    status              NVARCHAR(20)   NOT NULL CONSTRAINT DF_challenges_status DEFAULT 'pending',
    created_at          DATETIME2      NOT NULL CONSTRAINT DF_challenges_created DEFAULT SYSUTCDATETIME(),
    responded_at        DATETIME2      NULL,
    CONSTRAINT FK_challenges_court FOREIGN KEY (court_id) REFERENCES courts(id),
    CONSTRAINT CK_challenges_format CHECK (format IN ('3v3', '5v5')),
    CONSTRAINT CK_challenges_status CHECK (status IN ('pending', 'accepted', 'declined', 'cancelled'))
);

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'attendance')
CREATE TABLE attendance (
    challenge_id      INT      NOT NULL,
    team_id           INT      NOT NULL,
    players_attended  INT      NOT NULL,
    recorded_at       DATETIME2 NOT NULL CONSTRAINT DF_attendance_recorded DEFAULT SYSUTCDATETIME(),
    CONSTRAINT PK_attendance PRIMARY KEY (challenge_id, team_id),
    CONSTRAINT FK_attendance_challenge FOREIGN KEY (challenge_id) REFERENCES challenges(id),
    CONSTRAINT CK_attendance_players CHECK (players_attended >= 0)
);
