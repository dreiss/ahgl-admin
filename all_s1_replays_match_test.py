#!/usr/bin/env python
import sys
import operator
import itertools
import contextlib
import os
import shutil
import tempfile
import sqlite3
import unittest
import flask

import ahgl_admin

SEASON_1_DIR = "./season1-new-schema"

def get_sql_setup_file():
  return "./test_replay_match_data.sql"

class AhglReplaysMatchTest(unittest.TestCase):
  def setUp(self):
    self.data_dir = tempfile.mkdtemp()
    ahgl_admin.app.debug = True
    ahgl_admin.app.config["DATA_DIR"] = self.data_dir

  def tearDown(self):
    if not os.environ.get("TEST_PRESERVE"):
      shutil.rmtree(self.data_dir)

  def runTest(self):
    with ahgl_admin.app.test_request_context():
      ahgl_admin.app.preprocess_request()

      with open(get_sql_setup_file()) as handle:
        flask.g.db.executescript(handle.read())

      with contextlib.closing(flask.g.db.cursor()) as cursor:
        cursor.execute(
            "SELECT week, match_number, set_number, replay_hash FROM actual_set_results "
            "WHERE replay_hash IS NOT NULL "
            "AND   set_number < 5 "
            #"AND week = 2 AND match_number = 4 AND set_number = 3 "
            "ORDER BY week, match_number, set_number "
            )
        actuals = [ (key, list(vals)) for key, vals in
            itertools.groupby(cursor, operator.itemgetter(0)) ]

      for week, rows in actuals:
        #if week != 1: continue  # XXX
        rfnames = [ os.path.join(SEASON_1_DIR, rhash + ".SC2Replay") for (_, _, _, rhash) in rows ]

        entry_weeks =(week, week+1)
        #entry_weeks =(week,) # XXX
        for entry_week in entry_weeks:
          suggestions = ahgl_admin.infer_wms_from_replays(rfnames, entry_week)
          for ((w, m, s, rhash), sug) in zip(rows, suggestions):
            if sug is None:
              ahgl_admin.app.logger.warning("Failed to get suggestion for %s" % rhash)
              continue
            #self.assertNotEqual(sug, None)
            ssug = (sug["week"], sug["match_number"], sug["set_number"])
            self.assertEqual(ssug, (w, m, s),
                "Bad suggestion for %r.  Expected %r, got %r" %
                (rhash[:16], ssug, (w, m, s)))


if __name__ == "__main__":
  unittest.main()
