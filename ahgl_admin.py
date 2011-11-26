#!/usr/bin/env python
import functools
import contextlib
import collections
import re
import hashlib
import os
import errno
import zipfile
import cStringIO
import cgi
import flask


def open_db(path):
  import sqlite3
  driver = sqlite3
  if driver.paramstyle != "qmark":
    raise Exception("Require qmark paramstyle")
  conn = driver.connect(path)
  return conn


app = flask.Flask(__name__)
g = flask.g


def content_type(ctype):
  def decorator(func):
    @functools.wraps(func)
    def wrapper(*args, **kwds):
      ret = func(*args, **kwds)
      resp = app.make_response(ret)
      resp.headers["Content-Type"] = ctype
      return resp
    return wrapper
  return decorator


def require_auth(func):
  @functools.wraps(func)
  def wrapper(*args, **kwds):
    account = flask.session.get("account")
    if not account:
      return flask.render_template("no_account.html")
    g.account = account
    return func(*args, **kwds)
  return wrapper


def get_user_team():
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT team FROM accounts WHERE id = ?", (g.account,))
    return list(cursor)[0][0]


@app.before_request
def before_request():
  g.db = open_db(os.path.join(app.config["DATA_DIR"], "ahgl.sq3"))

@app.teardown_request
def teardown_request(exception):
  if hasattr(g, "db"):
    g.db.close()


@app.route("/_debug")
@content_type("text-plain")
def debug_page():
  return "".join(["%s: %s\n" % (key, value)
         for key, value in flask.request.environ.iteritems()])


@app.route("/")
def home_page():
  return flask.render_template("home.html", links=dict(
      show_lineup = flask.url_for(show_lineup_select.__name__),
      enter_lineup = flask.url_for(enter_lineup.__name__),
      show_result = flask.url_for(show_result_select.__name__),
      enter_result = flask.url_for(enter_result.__name__),
    ))


@app.route("/login/<auth_key>")
def login(auth_key):
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id FROM accounts WHERE auth_key = ?", (auth_key,))
    results = list(cursor)

  if not results:
    return flask.render_template("no_account.html")

  flask.session["account"] = results[0][0]

  return flask.redirect(flask.url_for(home_page.__name__))


@app.route("/logout")
def logout():
  del flask.session["account"]
  return flask.redirect(flask.url_for(home_page.__name__))


@app.route("/show-lineup")
def show_lineup_select():
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT DISTINCT week FROM maps ORDER BY week")
    weeks = [ int(row[0]) for row in cursor ]

  items = [ (week, flask.url_for(show_lineup_week.__name__, week=week)) for week in weeks ]

  return flask.render_template("week_list.html",
      item_type = "Lineup",
      items = items,
      )


@app.route("/show-lineup/<int:week>")
def show_lineup_week(week):
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id, name FROM teams")
    teams = dict(cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, home_team, away_team FROM matches WHERE week = ?", (week,))
    matches = dict((row[0], (row[1], row[2])) for row in cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week,))
    maps = dict((row[0], row[1]) for row in cursor)

  lineups = collections.defaultdict(dict)
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute(
        "SELECT l.team, set_number, p.name, race "
        "FROM lineup l JOIN players p on p.id = l.player "
        "WHERE week = ? "
        , (week,))
    for (team, set_number, player, race) in cursor:
      lineups[team][set_number] = (player, race)

  # TODO: Jinja-ize this.
  lineup_displays = []
  for (match, (home, away)) in sorted(matches.items()):
    lineup_displays.append("<h2>Match %d: %s vs %s</h2><p>"
        % (match, cgi.escape(teams[home]), cgi.escape(teams[away])))
    if lineups[home] and lineups[away]:
      for setnum in range(1,5+1):
        mapname = maps[setnum]
        if setnum == 5:
          homeplayer = ("ACE", "?")
          awayplayer = ("ACE", "?")
        else:
          homeplayer = lineups[home][setnum]
          awayplayer = lineups[away][setnum]
        lineup_displays.append("%s (%s) &lt; %s &gt; (%s) %s<br>"
            % tuple(cgi.escape(val) for val in (homeplayer[0], homeplayer[1], mapname, awayplayer[1], awayplayer[0])))
    else:
      displays = ["NOT ENTERED", "LINEUP ENTERED"]
      lineup_displays.append(
          displays[int(bool(lineups[home]))]
          + " &lt;&gt; " +
          displays[int(bool(lineups[away]))]
          )

  return "".join([("""
    <html>
      <head>
        <title>AHGL Lineup</title>
      </head>
      <body>
        <h1>AHGL Lineup Week %d</h1>
        %s
      </body>
    </html>
  """ % (week, "".join(lineup_displays))).encode()])


@app.route("/enter-lineup")
@require_auth
def enter_lineup():
  week_number = 1
  try:
    week_number = int(flask.request.args.get("week"))
  except (ValueError, TypeError):
    pass

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week_number,))
    maps = dict((row[0], row[1]) for row in cursor)

  team_number = get_user_team()
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT name FROM teams WHERE id = ?", (team_number,))
    team_name = list(cursor)[0][0]

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id, name FROM players WHERE team = ? AND active = 1 ORDER BY name", (team_number,))
    players = list(cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT COUNT(*) FROM lineup WHERE week = ? AND team = ?", (week_number, team_number,))
    lineup_already_entered = bool(list(cursor)[0][0])

  return flask.render_template("enter_lineup.html",
      week_number = week_number,
      lineup_already_entered = lineup_already_entered,
      maps = maps,
      team_number = team_number,
      team_name = team_name,
      players = players,
      num_sets = 5,
      submit_link = flask.url_for(submit_lineup.__name__),
      )


@app.route("/submit-lineup", methods=["POST"])
@require_auth
def submit_lineup():
  postdata = flask.request.form

  week_number = postdata.getlist("week")
  if len(week_number) != 1 or not week_number[0]:
    return "No value submitted for 'week'"
  week_number = week_number[0]
  try:
    week_number = int(week_number)
  except ValueError:
    return "Invalid week"

  teamfield = postdata.getlist("team")
  if len(teamfield) != 1 or not teamfield[0]:
    return "No value submitted for 'team'"
  team_string = teamfield[0]
  try:
    team_number = int(team_string)
  except ValueError:
    return "Invalid team"
  if team_number != get_user_team():
    return "Can't submit for another team"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT name FROM teams WHERE id = ?", (team_number,))
    if len(list(cursor)) != 1:
      return "Invalid team"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT DISTINCT week FROM maps WHERE week = ?", (week_number,))
    if len(list(cursor)) != 1:
      return "Invalid week"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT COUNT(*) FROM lineup WHERE team = ? AND week = ?", (team_number, week_number))
    if list(cursor) != [(0,)]:
      return "Lineup already submitted"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id FROM players WHERE team = ? AND active = 1", (team_number,))
    eligible_players = set([row[0] for row in cursor])

  entered_players = set()

  for setnum in range(1,5):
    player = postdata.getlist("player_%d" % setnum)
    if len(player) != 1 or not player[0]:
      return "No value submitted for 'player_%d'" % setnum
    player = player[0]
    try:
      player = int(player)
    except ValueError:
      return "Invalid value for player %d" % setnum
    if player not in eligible_players:
      return "Player %d is not an eligible team member" % setnum
    if player in entered_players:
      return "Duplicate player for player %d" % setnum
    entered_players.add(player)

    race = postdata.getlist("race_%d" % setnum)
    if len(race) != 1 or not race[0]:
      return "No value submitted for 'race_%d'" % setnum
    race = race[0]
    if race not in list("TZPR"):
      return "Invalid race for player %d" % setnum

    with contextlib.closing(g.db.cursor()) as cursor:
      cursor.execute(
          "INSERT INTO lineup(week, team, set_number, player, race) "
          "VALUES (?,?,?,?,?) "
          , (week_number, team_number, setnum, player, race))

  g.db.commit()

  return flask.render_template("success.html", item_type="Lineup")


@app.route("/show-result")
def show_result_select():
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT DISTINCT week FROM maps ORDER BY week")
    weeks = [ int(row[0]) for row in cursor ]

  items = [ (week, flask.url_for(show_result_week.__name__, week=week)) for week in weeks ]

  return flask.render_template("week_list.html",
      item_type = "Result",
      items = items,
      )


@app.route("/show-result/<int:week>")
def show_result_week(week):
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id, name FROM teams")
    teams = dict(cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, home_team, away_team FROM matches WHERE week = ?", (week,))
    matches = dict((row[0], (row[1], row[2])) for row in cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week,))
    maps = dict((row[0], row[1]) for row in cursor)

  lineups = collections.defaultdict(dict)
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute(
        "SELECT l.team, set_number, p.name, race "
        "FROM lineup l JOIN players p on p.id = l.player "
        "WHERE week = ? "
        , (week,))
    for (team, set_number, player, race) in cursor:
      lineups[team][set_number] = (player, race)

  results = collections.defaultdict(dict)
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, set_number, home_winner, away_winner, forfeit, replay_hash FROM set_results WHERE week = ?", (week,))
    for (match_number, set_number, home_winner, away_winner, forfeit, replay_hash) in cursor:
      results[match_number][set_number] = (home_winner, away_winner, forfeit, replay_hash)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, home_player, away_player, home_race, away_race FROM ace_matches WHERE week = ?", (week,))
    aces = dict((row[0], row[1:]) for row in cursor)

  # TODO: Jinja-ize this.
  result_displays = []
  for (match, (home, away)) in sorted(matches.items()):
    result_displays.append("<h2>Match %d: %s vs %s</h2><p>"
        % (match, cgi.escape(teams[home]), cgi.escape(teams[away])))
    if not results[match]:
      result_displays.append("No result entered")
      continue
    elif not lineups[matches[match][0]] or not lineups[matches[match][1]]:
      result_displays.append("Missing lineup")
      continue

    for setnum in range(1,5+1):
      result_displays.append(
          "Game %d (%s): " % (setnum, cgi.escape(maps[setnum])))
      win_tuple = (results[match][setnum][0], results[match][setnum][1])
      if not sum(win_tuple):
        result_displays.append("Not played<br>")
        continue
      if setnum == 5:
        homeplayer = (aces[match][0], aces[match][2])
        awayplayer = (aces[match][1], aces[match][3])
      else:
        homeplayer = lineups[home][setnum]
        awayplayer = lineups[away][setnum]
      win_arrows = {(1,0): ">", (0,1): "<"}
      win_arrow = win_arrows[win_tuple]
      result_displays.append("%s (%s) %s (%s) %s"
          % tuple(cgi.escape(val) for val in (homeplayer[0], homeplayer[1], win_arrow, awayplayer[1], awayplayer[0])))

      if results[match][setnum][2]:
        result_displays.append(" -- forfeit")
      elif not results[match][setnum][3]:
        result_displays.append(" -- no replay")
      else:
        replayhash = results[match][setnum][3]
        def cleanit(word):
          return re.sub("[^a-zA-Z0-9]", "", word)
        replaylink = "/replay/%s/%s-%s_%d_%s-%s.SC2Replay" % (
            replayhash, cleanit(teams[home]), cleanit(teams[away]), setnum, cleanit(homeplayer[0]), cleanit(awayplayer[0]))
        result_displays.append(" -- <a href=\"%s\">replay</a>" % cgi.escape(replaylink, True))

      result_displays.append("<br>")

  return "".join([("""
    <html>
      <head>
        <title>AHGL Result</title>
      </head>
      <body>
        <h1>AHGL Result Week %d</h1>
        <p><a href="/replay-pack/%d/ahgl_replays_week_%d.zip">Replay Pack</a></p>
        %s
      </body>
    </html>
  """ % (week, week, week, "".join(result_displays))).encode()])


@app.route("/enter-result")
@require_auth
def enter_result():
  week_number = 1
  try:
    week_number = int(flask.request.args.get("week"))
  except (ValueError, TypeError):
    pass

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, ht.name, at.name FROM matches, teams ht, teams at WHERE week = ? AND ht.id = home_team AND at.id = away_team", (week_number,))
    matches = list(cursor)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week_number,))
    maps = dict((row[0], row[1]) for row in cursor)

  return flask.render_template("enter_result.html",
      week_number = week_number,
      matches = matches,
      num_sets = 5,
      max_required = 3,
      submit_link = flask.url_for(submit_result.__name__),
      )


@app.route("/submit-result", methods=["POST"])
@require_auth
def submit_result():
  postdata = flask.request.form

  week_number = postdata.getlist("week")
  if len(week_number) != 1 or not week_number[0]:
    return "No value submitted for 'week'"
  week_number = week_number[0]
  try:
    week_number = int(week_number)
  except ValueError:
    return "Invalid week"

  match = postdata.getlist("match")
  if len(match) != 1 or not match[0]:
    return "No value submitted for 'match'"
  match = match[0]
  try:
    match = int(match)
  except ValueError:
    return "Invalid match"

  sum_home = 0
  sum_away = 0

  winners = {}

  for setnum in range(1, 5+1):
    winner = postdata.get("winner_%d" % setnum, "none")
    if winner == "home":
      winners[setnum] = (1, 0)
      sum_home += 1
    elif winner == "away":
      winners[setnum] = (0, 1)
      sum_away += 1
    elif sum_home >= 3 or sum_away >= 3:
      winners[setnum] = (0, 0)
    else:
      return "Invalid winner for set %d" % setnum

  num_sets = sum_home + sum_away

  if sum(winners[5]):
    home_ace = postdata.get("home_ace")
    away_ace = postdata.get("away_ace")
    home_ace_race = postdata.get("home_ace_race")
    away_ace_race = postdata.get("away_ace_race")
    if not home_ace:
      return "No home ace specified."
    if not away_ace:
      return "No away ace specified."
    if not home_ace_race:
      return "No home ace race specified."
    if not away_ace_race:
      return "No away ace race specified."

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT DISTINCT week FROM maps WHERE week = ?", (week_number,))
    if len(list(cursor)) != 1:
      return "Invalid week"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT COUNT(*) FROM matches WHERE week = ? AND match_number = ?", (week_number, match))
    if list(cursor) != [(1,)]:
      return "Invalid match"

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT COUNT(*) FROM set_results WHERE week = ? AND match_number = ?", (week_number, match))
    if list(cursor) != [(0,)]:
      return "Result already submitted"

  rephashes = {}

  for setnum in range(1, 5+1):
    repfield = flask.request.files.get("replay_%d" % setnum)
    if not repfield:
      continue
    rep = repfield.read()
    rephash = hashlib.sha1(rep).hexdigest()
    repfile = os.path.join(app.config["DATA_DIR"], rephash + ".SC2Replay")
    if not os.path.exists(repfile):
      with open(repfile, "wb") as handle:
        handle.write(rep)
    rephashes[setnum] = rephash

  for setnum in range(1, 5+1):
    forfeit = 1 if postdata.get("forfeit_%d" % setnum) == "on" else 0
    wins = winners[setnum]
    g.db.cursor().execute(
        "INSERT INTO set_results(week, match_number, set_number, home_winner, away_winner, forfeit, replay_hash) "
        "VALUES (?,?,?,?,?,?,?) "
        , (week_number, match, setnum, wins[0], wins[1], forfeit, rephashes.get(setnum)))

  if sum(winners[5]):
    g.db.cursor().execute(
        "INSERT INTO ace_matches(week, match_number, home_player, away_player, home_race, away_race) "
        "VALUES (?,?,?,?,?,?) "
        , (week_number, match, home_ace, away_ace, home_ace_race, away_ace_race))

  g.db.commit()

  return flask.render_template("success.html", item_type="Result")


@app.route("/replay/<rephash>/<fakepath>")
@content_type("application/octet-stream")
def get_replay(rephash, fakepath):
  match = re.search(r'^[0-9a-f]{40}$', rephash)
  if not match:
    flask.abort(404)

  try:
    handle = open(os.path.join(app.config["DATA_DIR"], rephash + ".SC2Replay"), "rb")
  except IOError as err:
    if err.errno != errno.ENOENT:
      raise
    flask.abort(404)

  with handle:
    return handle.read()


@app.route("/replay-pack/<int:week>/<fakepath>")
@content_type("application/zip")
def get_replay_pack(week, fakepath):
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT id, name FROM teams")
    teams = dict(cursor)

  lineups = collections.defaultdict(dict)
  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute(
        "SELECT l.team, set_number, p.name "
        "FROM lineup l JOIN players p on p.id = l.player "
        "WHERE week = ? "
        , (week,))
    for (team, set_number, player) in cursor:
      lineups[team][set_number] = player

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute("SELECT match_number, home_player, away_player FROM ace_matches WHERE week = ?", (week,))
    aces = dict((row[0], row[1:]) for row in cursor)

  buf = cStringIO.StringIO()
  zfile = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)

  with contextlib.closing(g.db.cursor()) as cursor:
    cursor.execute(
        "SELECT m.match_number, m.home_team, m.away_team, s.set_number, s.replay_hash "
        "FROM matches m JOIN set_results s "
        "  ON m.match_number = s.match_number "
        "  AND m.week = ? AND s.week = ? "
        , (week, week))
    for row in cursor:
      match, hteam, ateam, setnum, replayhash = row
      if not replayhash:
        continue
      if setnum < 5:
        hplayer = lineups[hteam][setnum]
        aplayer = lineups[ateam][setnum]
      else:
        hplayer = aces[match][0]
        aplayer = aces[match][1]
      def cleanit(word):
        return re.sub("[^a-zA-Z0-9]", "", word)
      zfile.write(
        os.path.join(app.config["DATA_DIR"], replayhash + ".SC2Replay"),
        "AHGLpre_Week-%d/Match-%d_%s-%s/%s-%s_%d_%s-%s.SC2Replay" % (
          week, match, cleanit(teams[hteam]), cleanit(teams[ateam]), cleanit(teams[hteam]), cleanit(teams[ateam]), setnum, cleanit(hplayer), cleanit(aplayer)))

  zfile.close()

  return buf.getvalue()
