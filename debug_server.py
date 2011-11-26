#!/usr/bin/env python
import ahgl_admin

DATA_DIR = './data'

if __name__ == '__main__':
  ahgl_admin.app.config.from_object(__name__)
  ahgl_admin.app.run(debug=True)
