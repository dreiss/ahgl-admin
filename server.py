#!/usr/bin/env python
import sys
import os
import contextlib
import logging
import cgi

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
    db_path = "/home/protected/ahgl-pre.sq3"
    request_uri = environ["REQUEST_URI"]
  else:
    db_path = "./ahgl-pre.sq3"
    request_uri = environ["PATH_INFO"]

  week_number = 2

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
              <li><a href="/ahgl/enter-lineup">Enter Lineup</a>
            </ul>
          </body>
        </html>
        """]

  elif request_uri.endswith("/enter-lineup"):
    db = open_db(db_path)

    start_response("200 OK", [("Content-type", "text/html")])

    values = {}

    values["week_number"] = week_number

    with contextlib.closing(db.cursor()) as cursor:
      cursor.execute("SELECT setnum, mapname FROM maps WHERE week = ?", (week_number,))
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
      cursor.execute("SELECT COUNT(*) FROM lineup WHERE team = ?", (team,))
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
            "INSERT INTO lineup(week, team, setnum, player, race) "
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
