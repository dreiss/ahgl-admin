#!/usr/bin/env python
import sys
import os
import contextlib
import logging
import re
import cgi
import hashlib
import collections
import errno

def open_db(path):
  import sqlite3
  driver = sqlite3
  if driver.paramstyle != "qmark":
    raise Exception("Require qmark paramstyle")
  conn = driver.connect(path)
  return conn

def app(environ, start_response):
  is_nfsn = "NFSN_SITE_ROOT" in environ
  if is_nfsn:
    work_path = "/home/protected/ahgl_pre"
    request_uri = re.sub(r'\?.*', '', environ["REQUEST_URI"])
  else:
    work_path = "./data"
    request_uri = environ["PATH_INFO"]

  db_path = os.path.join(work_path, "ahgl-pre.sq3")

  if request_uri == "/debug":
    start_response("200 OK", [("Content-type", "text/plain")])

    return ["%s: %s\n" % (key, value)
           for key, value in environ.iteritems()]

  elif request_uri in ("/", "/ahgl", "/ahgl/"):
    start_response("200 OK", [("Content-type", "text/html")])

    return ["""
        <html>
          <head>
            <title>AHGL Admin Page</title>
          </head>
          <body>
            <h1>AHGL Admin Page</h1>
            <ul>
              <li><a href="/ahgl/show-lineup">Show Lineup</a>
              <li><a href="/ahgl/enter-lineup">Enter Lineup</a>
              <li><a href="/ahgl/show-result">Show result</a>
              <li><a href="/ahgl/enter-result">Enter Result</a>
            </ul>
          </body>
        </html>
        """]

  elif request_uri.endswith("/show-lineup"):
    db = open_db(db_path)

    start_response("200 OK", [("Content-type", "text/html")])

    getdata = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
    )

    week = None
    try:
      week = int(getdata.getfirst("week"))
    except (ValueError, TypeError):
      pass

    if not week:
      with contextlib.closing(db.cursor()) as cursor:
        cursor.execute("SELECT DISTINCT week FROM maps ORDER BY week")
        weeks = [ int(row[0]) for row in cursor ]

      return ["""
        <html>
          <head>
            <title>AHGL Select Lineup Week</title>
          </head>
          <body>
          """] + [
              "<a href=\"?week=%d\">Week %d</a><br>" % (wk, wk)
              for wk in weeks
          ] + ["""
          </body>
        </html>
      """]

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT id, name FROM teams")
      teams = dict(cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT match_number, home_team, away_team FROM matches WHERE week = ?", (week,))
      matches = dict((row[0], (row[1], row[2])) for row in cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week,))
      maps = dict((row[0], row[1]) for row in cursor)

    lineups = collections.defaultdict(dict)
    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT team, set_number, player, race FROM lineup WHERE week = ?", (week,))
      for (team, set_number, player, race) in cursor:
        lineups[team][set_number] = (player, race)

    lineup_displays = []
    for (match, (home, away)) in sorted(matches.items()):
      lineup_displays.append("<h2>Match %d: %s vs %s</h2>"
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
          lineup_displays.append("%s (%s) < %s > (%s) %s<br>"
              % tuple(cgi.escape(val) for val in (homeplayer[0], homeplayer[1], mapname, awayplayer[1], awayplayer[0])))
      else:
        displays = ["NOT ENTERED", "LINEUP ENTERED"]
        lineup_displays.append(
            displays[int(bool(lineups[home]))]
            + " <> " +
            displays[int(bool(lineups[away]))]
            )

    return [("""
      <html>
        <head>
          <title>AHGL Lineup</title>
        </head>
        <body>
          <h1>AHGL Lineup Week %d<h1>
          %s
        </body>
      </html>
    """ % (week, "".join(lineup_displays))).encode()]

  elif request_uri.endswith("/enter-lineup"):
    db = open_db(db_path)

    start_response("200 OK", [("Content-type", "text/html")])

    values = {}

    week_number = 3
    values["week_number"] = week_number

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week_number,))
      maps = dict((row[0], row[1]) for row in cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT id, name FROM teams ORDER BY id")
      values["team_options"] = "".join(
          "<option value=\"%d\">%s</option>"
          % (row[0], cgi.escape(row[1]))
          for row in cursor)

    values["lineup_entries"] = "".join(
        "<li>%s <input name=\"player_%d\"></input>"
        "<select name=\"race_%d\">"
        "<option>T</option><option>Z</option><option>P</option><option>R</option>"
        "</select>"
        % (cgi.escape(maps[setnum]), setnum, setnum)
        for setnum in range(1,5))

    return [("""
        <html>
          <head>
            <title>AHGL Lineup Entry</title>
          </head>
          <body>
            <h1>AHGL Lineup Entry</h1>
            <h2>Week %(week_number)d</h2>
            <form method="POST" action="/ahgl/submit-lineup">
              <select name="team">
              %(team_options)s
              </select>
              <ul>
                %(lineup_entries)s
              </ul>
              <input type="submit">
            </form>
          </body>
        </html>
        """ % values).encode()]

  elif request_uri.endswith("/submit-lineup"):
    start_response("200 OK", [("Content-type", "text/html")])

    week_number = 3

    db = open_db(db_path)

    postdata = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
    )
    
    team = postdata.getlist("team")
    if len(team) != 1 or not team[0]:
      return ["No value submitted for 'team'"]
    team = team[0]
    try:
      team = int(team)
    except ValueError:
      return ["Invalid team"]

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT name FROM teams WHERE id = ?", (team,))
      if len(list(cursor)) != 1:
        return ["Invalid team"]

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT COUNT(*) FROM lineup WHERE team = ? AND week = ?", (team, week_number))
      if list(cursor) != [(0,)]:
        return ["Lineup already submitted"]

    for setnum in range(1,5):
      player = postdata.getlist("player_%d" % setnum)
      if len(player) != 1 or not player[0]:
        return ["No value submitted for 'player_%d'" % setnum]
      player = player[0]

      race = postdata.getlist("race_%d" % setnum)
      if len(race) != 1 or not race[0]:
        return ["No value submitted for 'race_%d'" % setnum]
      race = race[0]
      if race not in list("TZPR"):
        return ["Invalid race"]

      with contextlib.closing(db.cursor()) as cursor:
        cursor.execute(
            "INSERT INTO lineup(week, team, set_number, player, race) "
            "VALUES (?,?,?,?,?) "
            , (week_number, team, setnum, player, race))

    db.commit()

    return ["""
        <html>
          <head>
            <title>Success</title>
          </head>
          <body>
            <p>Lineup entered successfully.</p>
          </body>
        </html>
        """]

  elif request_uri.endswith("/show-result"):
    db = open_db(db_path)

    start_response("200 OK", [("Content-type", "text/html")])

    getdata = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
    )

    week = None
    try:
      week = int(getdata.getfirst("week"))
    except (ValueError, TypeError):
      pass

    if not week:
      with contextlib.closing(db.cursor()) as cursor:
        cursor.execute("SELECT DISTINCT week FROM maps ORDER BY week")
        weeks = [ int(row[0]) for row in cursor ]

      return ["""
        <html>
          <head>
            <title>AHGL Select Result Week</title>
          </head>
          <body>
          """] + [
              "<a href=\"?week=%d\">Week %d</a><br>" % (wk, wk)
              for wk in weeks
          ] + ["""
          </body>
        </html>
      """]

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT id, name FROM teams")
      teams = dict(cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT match_number, home_team, away_team FROM matches WHERE week = ?", (week,))
      matches = dict((row[0], (row[1], row[2])) for row in cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week,))
      maps = dict((row[0], row[1]) for row in cursor)

    lineups = collections.defaultdict(dict)
    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT team, set_number, player, race FROM lineup WHERE week = ?", (week,))
      for (team, set_number, player, race) in cursor:
        lineups[team][set_number] = (player, race)

    results = collections.defaultdict(dict)
    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT match_number, set_number, home_winner, away_winner, forfeit, replay_hash FROM set_results WHERE week = ?", (week,))
      for (match_number, set_number, home_winner, away_winner, forfeit, replay_hash) in cursor:
        results[match_number][set_number] = (home_winner, away_winner, forfeit, replay_hash)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT match_number, home_player, away_player FROM ace_matches WHERE week = ?", (week,))
      aces = dict((row[0], (row[1], row[2])) for row in cursor)

    result_displays = []
    for (match, (home, away)) in sorted(matches.items()):
      result_displays.append("<h2>Match %d: %s vs %s</h2>"
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
          homeplayer = aces[match][0]
          awayplayer = aces[match][1]
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
          replaylink = "/aghl/replay/%s/%s-%s_%d_%s-%s.SC2Replay" % (
              replayhash, cleanit(teams[home]), cleanit(teams[away]), setnum, cleanit(homeplayer[0]), cleanit(awayplayer[0]))
          result_displays.append(" -- <a href=\"%s\">replay</a>" % cgi.escape(replaylink, True))

        result_displays.append("<br>")

    return [("""
      <html>
        <head>
          <title>AHGL Result</title>
        </head>
        <body>
          <h1>AHGL Result Week %d<h1>
          %s
        </body>
      </html>
    """ % (week, "".join(result_displays))).encode()]

  elif request_uri.endswith("/enter-result"):
    db = open_db(db_path)

    start_response("200 OK", [("Content-type", "text/html")])

    week_number = 2
    values = {}

    values["week_number"] = week_number

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT match_number, ht.name, at.name FROM matches, teams ht, teams at WHERE week = ? AND ht.id = home_team AND at.id = away_team", (week_number,))
      matches = dict((row[0], (row[1], row[2])) for row in cursor)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT set_number, mapname FROM maps WHERE week = ?", (week_number,))
      maps = dict((row[0], row[1]) for row in cursor)

    values["match_options"] = "".join([
      "<option value=\"%d\">%s (Home) vs %s (Away)</option>"
      % (matchnum, cgi.escape(ht), cgi.escape(at))
      for (matchnum, (ht, at)) in matches.items() ])

    fields = []

    for setnum in range(1,5+1):
      fields.append(
          "<li>Game %d winner: "
          "<input type=\"radio\" name=\"winner_%d\" value=\"home\">home "
          "<input type=\"radio\" name=\"winner_%d\" value=\"away\">away "
          % (setnum, setnum, setnum)
          )
      if setnum > 3:
        fields.append(
            "<input type=\"radio\" name=\"winner_%d\" value=\"none\">not played "
            % (setnum,))
      fields.append(
          "| <input type=\"checkbox\" name=\"forfeit_%d\">forfeit "
          "| Replay: <input type=\"file\" name=\"replay_%d\">"
          % (setnum, setnum))

    values["result_entries"] = "".join(fields)

    return [("""
        <html>
          <head>
            <title>AHGL Result Entry</title>
          </head>
          <body>
            <h1>AHGL Result Entry</h1>
            <h2>Week %(week_number)d</h2>
            <form enctype="multipart/form-data" method="POST" action="/ahgl/submit-result">
              <select name="match">
              %(match_options)s
              </select>
              <ul>
                %(result_entries)s
                <li>
                  Home ace: <input type="text" name="home_ace"></input>
                  Away ace: <input type="text" name="away_ace"></input>
              </ul>
              <input type="submit">
            </form>
          </body>
        </html>
        """ % values).encode()]

  elif request_uri.endswith("/submit-result"):
    start_response("200 OK", [("Content-type", "text/html")])

    week_number = 2
    postdata = cgi.FieldStorage(
        fp=environ['wsgi.input'],
        environ=environ,
    )

    match = postdata.getlist("match")
    if len(match) != 1 or not match[0]:
      return ["No value submitted for 'match'"]
    match = match[0]
    try:
      match = int(match)
    except ValueError:
      return ["Invalid match"]

    sum_home = 0
    sum_away = 0

    winners = {}

    for setnum in range(1, 5+1):
      winner = postdata.getfirst("winner_%d" % setnum, "none")
      if sum_home >= 3 or sum_away >= 3:
        if setnum == 5 and winner != "none":
          return ["You played the ace match after one team won?"]
        winners[setnum] = (0, 0)
        continue
      if winner == "home":
        winners[setnum] = (1, 0)
        sum_home += 1
      elif winner == "away":
        winners[setnum] = (0, 1)
        sum_away += 1
      else:
        return ["Invalid winner for set %d" % setnum]

    num_sets = sum_home + sum_away

    if num_sets == 5:
      home_ace = postdata.getfirst("home_ace")
      away_ace = postdata.getfirst("away_ace")
      if not home_ace:
        return ["No home ace specified."]
      if not away_ace:
        return ["No away ace specified."]

    db = open_db(db_path)

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT COUNT(*) FROM matches WHERE week = ? AND match_number = ?", (week_number, match))
      if list(cursor) != [(1,)]:
        return ["Invalid match"]

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT COUNT(*) FROM set_results WHERE week = ? AND match_number = ?", (week_number, match))
      if list(cursor) != [(0,)]:
        return ["Result already submitted"]

    rephashes = {}

    for setnum in range(1, 5+1):
      rep = postdata.getfirst("replay_%d" % setnum)
      if not rep:
        continue
      rephash = hashlib.sha1(rep).hexdigest()
      repfile = os.path.join(work_path, rephash + ".SC2Replay")
      if not os.path.exists(repfile):
        with open(repfile, "wb") as handle:
          handle.write(rep)
      rephashes[setnum] = rephash

    for setnum in range(1, 5+1):
      forfeit = 1 if postdata.getfirst("forfeit_%d" % setnum) == "on" else 0
      wins = winners[setnum]
      db.cursor().execute(
          "INSERT INTO set_results(week, match_number, set_number, home_winner, away_winner, forfeit, replay_hash) "
          "VALUES (?,?,?,?,?,?,?) "
          , (week_number, match, setnum, wins[0], wins[1], forfeit, rephashes.get(setnum)))

    if num_sets == 5:
      db.cursor().execute(
          "INSERT INTO ace_matches(week, match_number, home_player, away_player) "
          "VALUES (?,?,?,?) "
          , (week_number, match, home_ace, away_ace))

    db.commit()

    return ["""
        <html>
          <head>
            <title>Success</title>
          </head>
          <body>
            <p>Result entered successfully.</p>
          </body>
        </html>
        """]

  elif "/replay/" in request_uri:
    match = re.search(r'/replay/([0-9a-f]{40})/', request_uri)

    try:
      handle = open(os.path.join(work_path, match.group(1) + ".SC2Replay"), "rb")
    except IOError as err:
      if err.errno != errno.ENOENT:
        raise
      start_response("200 OK", [("Content-type", "text/plain")])
      return ["404"]

    with handle:
      start_response("200 OK", [("Content-type", "application/octet-stream")])
      return [handle.read()]

  else:
    start_response("404 Not Found", [("Content-type", "text/plain")])
    return ["404"]



def main(argv = None):
  is_cgi = ("SERVER_SOFTWARE" in os.environ)
  if is_cgi:
    import wsgiref.handlers
    wsgiref.handlers.CGIHandler().run(app)
  else:
    import wsgiref.simple_server
    wsgiref.simple_server.make_server("", 8000, app).serve_forever()


if __name__ == "__main__":
  sys.exit(main(sys.argv))
