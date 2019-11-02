#!/usr/bin/env python3.8

import os
from flask import Flask, escape, request, send_from_directory, redirect
import subprocess
import requests
import time
import json
import websocket
import signal
import sys

app = Flask(__name__)

request_id = 0
def ChromeComm(conn, method, **kwargs):
    global request_id
    request_id += 1
    command = {'method': method,
               'id': request_id,
               'params': kwargs}
    conn.send(json.dumps(command))
    while True:
        msg = json.loads(conn.recv())
        if msg.get('id') == request_id:
            return msg
        else:
          print('fuck ---')


def RunFromOutDir(outdir, debugger_port=5001, chromeflags=None):
  devtools_src = os.path.join(
    os.environ['CHROMIUM_SRC'],
    'out', outdir,
    'resources', 'inspector')

  if chromeflags is None:
    chromeflags = []

  def StartChrome():
    browser_proc = subprocess.Popen(
      [os.path.join(os.environ['CHROMIUM_SRC'], 'out', outdir, 'chrome'),
       '--headless',
       f'--remote-debugging-port={debugger_port}'] + chromeflags)
    wait_seconds = 10
    sleep_seconds = 0.5
    while wait_seconds > 0:
      try:
        resp = requests.get(f'http://127.0.0.1:{debugger_port}/json').json()
        print(resp)
        return (browser_proc,
                websocket.create_connection(resp[0]['webSocketDebuggerUrl']),
                resp[0]['id'])
      except requests.exceptions.ConnectionError:
        time.sleep(sleep_seconds)
        wait_seconds -= sleep_seconds
      except:
        print('FUCK')
        raise

  proc, chromeconn, page_id = StartChrome()
  devtools_url = f'127.0.0.1:{debugger_port}/devtools/page/{page_id}'

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
    has_experiments = (request.args.get('experiments') == 'true')
    has_ws = (request.args.get('pid') == page_id)
    has_tabs = request.args.get('tabs')

    if not (has_experiments and has_ws):
      newurl = request.url_root + '?'
      if has_tabs:
        newurl += f'tabs={has_tabs}'
      newurl += f'&experiments=true&ws={devtools_url}&pid={page_id}'
      return redirect(newurl, code=302)
    with open(os.path.join(devtools_src, 'devtools_app.html'), 'r') as f:
      textual = f.read()
      first_bit, second_bit = textual.split('</head>')
      return f'{first_bit}{hijackJS()}{second_bit}'

  @app.route('/<path:path>')
  def serve(path):
    return send_from_directory(devtools_src, path)

  return proc, chromeconn


class FlObAr(object):
  def __init__(self):
    self.flags = sys.argv[1:]
    self.args = []
    was_prev_a_flag = None
    for flag in self.flags:
      if flag.startswith('-'):
        if was_prev_a_flag:
          self.SetBoolFlag(was_prev_a_flag)
        if '=' in flag:
          self.SetValueFlag(*flag.split('=', 1))
        else:
          was_prev_a_flag = flag
      else:
        if was_prev_a_flag:
          self.SetValueFlag(was_prev_a_flag, flag)
        else:
          self.args.append(flag)
        was_prev_a_flag = None
    if was_prev_a_flag:
      self.SetBoolFlag(was_prev_a_flag)

  def SetBoolFlag(self, flag):
    setattr(self, flag, True)

  def SetValueFlag(self, flag, value):
    setattr(self, flag, value)


class DevDevArgs(FlObAr):
  def __init__(self):
    super().__init__()

  def GetChromeFeatureFlag(self):
    if hasattr(self, 'chrome-flags'):
      return f'--enable-features={",".join(getattr(self, "chrome-flags"))}'
    return ''

  def GetPort(self, default=9001):
    if hasattr(self, 'port'):
      return int(self.port)
    return default

  def GetUrl(self):
    if hasattr(self, 'url'):
      return self.url
    return 'about:blank'

  def GetOutDir(self):
    if hasattr(self, 'outdir'):
      return self.outdir
    return 'Default'





def RunItAll():
  proc = None,
  conn = None
  original = signal.getsignal(signal.SIGINT)
  def kill_me(num, fr):
    signal.signal(signal.SIGINT, original)
    if proc:
      proc.terminate()
    if conn:
      conn.close()
    sys.exit()
  signal.signal(signal.SIGINT, kill_me)
  print('  ==> Signals Up')

  args = DevDevArgs()
  print('  ==> Args Parsed')

  proc, conn = RunFromOutDir(
    args.GetOutDir(),
    args.GetPort(),
    [args.GetChromeFeatureFlag()])
  print('  ==> Chrome Headless Started')


  ChromeComm(conn, 'Page.navigate', url=args.GetUrl())
  print('  ==> Navigation complete')

  app.run()




if __name__ == '__main__':
  RunItAll()