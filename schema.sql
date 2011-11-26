CREATE TABLE teams (
  id INTEGER PRIMARY KEY,
  name TEXT
);

CREATE TABLE accounts (
  id INTEGER PRIMARY KEY,
  email TEXT,
  team INTEGER,
  auth_key TEXT,
  UNIQUE (email),
  UNIQUE (auth_key)
);

CREATE TABLE players (
  id INTEGER PRIMARY KEY,
  team INTEGER,
  active INTEGER,
  name TEXT
);

CREATE TABLE matches (
  week INTEGER,
  match_number INTEGER,
  home_team INTEGER,
  away_team INTEGER,
  PRIMARY KEY (week, match_number)
);

CREATE TABLE maps (
  week INTEGER,
  set_number INTEGER,
  mapname TEXT,
  PRIMARY KEY (week, set_number)
);

CREATE TABLE lineup (
  week INTEGER,
  team INTEGER,
  set_number INTEGER,
  player INTEGER,
  race TEXT,
  PRIMARY KEY (week, team, set_number)
);

CREATE TABLE ace_matches (
  week INTEGER,
  match_number INTEGER,
  home_player TEXT,
  away_player TEXT,
  home_race TEXT,
  away_race TEXT,
  PRIMARY KEY (week, match_number)
);

CREATE TABLE set_results (
  week INTEGER,
  match_number INTEGER,
  set_number INTEGER,
  home_winner INTEGER,
  away_winner INTEGER,
  forfeit INTEGER,
  replay_hash TEXT,
  PRIMARY KEY (week, match_number, set_number)
);
