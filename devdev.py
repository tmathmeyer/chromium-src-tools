#!/usr/bin/env python3.8

import os
from flask import Flask, escape, request, send_from_directory, redirect

app = Flask(__name__)


def RunFromOutDir(outdir):
  devtools_src = os.path.join(
    os.environ['CHROME_SRC'],
    'out', outdir,
    'resources', 'inspector')

  def hijackJS():
    tabs = request.args.get('tabs')
    result = '<script type="module">'
    if tabs:
      tabs = tabs.split(',')
    else:
      tabs = []
    tabs.append('protocolMonitor')
    for enable in tabs:
      result += f"Root.Runtime.experiments.setEnabled('{enable}', true);"
    result += '</script>'
    return result

  @app.route('/')
  def rewrite():
    if not request.args.get('experiments'):
      newurl = request.url
      if request.args:
        newurl += '&experiments=true'
      else:
        newurl += '?experiments=true'
      return redirect(newurl, code=302)
    with open(os.path.join(devtools_src, 'devtools_app.html'), 'r') as f:
      textual = f.read()
      first_bit, second_bit = textual.split('</head>')
      return f'{first_bit}{hijackJS()}{second_bit}'

  @app.route('/<path:path>')
  def serve(path):
    return send_from_directory(devtools_src, path)


if __name__ == '__main__':
  RunFromOutDir('Default')
  app.run()