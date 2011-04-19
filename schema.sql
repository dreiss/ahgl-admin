CREATE TABLE teams (
  id INTEGER PRIMARY KEY,
  name TEXT
);

CREATE TABLE maps (
  week INTEGER,
  setnum INTEGER,
  mapname TEXT,
  PRIMARY KEY (week, setnum)
);

CREATE TABLE lineup (
  week INTEGER,
  team INTEGER,
  setnum INTEGER,
  player TEXT,
  race TEXT,
  PRIMARY KEY (week, team, setnum)
);
