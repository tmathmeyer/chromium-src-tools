#!/usr/bin/env python3.8

from flask import Flask, escape, request, send_from_directory, redirect
import logging
import json
import os
import re
import requests
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse
import websocket

from lib import libpen


app = Flask(__name__)
log = logging.getLogger('werkzeug')
log.disabled = True


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


def RunFromOutDir(outdir, debugger_port=5001, chromeflags=None, host='127.0.0.1'):
  devtools_src = os.path.join(
    os.environ['CHROMIUM_SRC'],
    'out', outdir,
    'resources', 'inspector')

  if chromeflags is None:
    chromeflags = []

  def StartChrome():
    chrome_process_flags = [
       os.path.join(os.environ['CHROMIUM_SRC'], 'out', outdir, 'chrome'),
       '--headless',
       f'--remote-debugging-address={host}',
       f'--remote-debugging-port={debugger_port}'] + chromeflags
    print(f'Starting chrome as: \n{chrome_process_flags}')
    browser_proc = subprocess.Popen(chrome_process_flags)
    wait_seconds = 10
    sleep_seconds = 0.5
    while wait_seconds > 0:
      try:
        resp = requests.get(f'http://127.0.0.1:{debugger_port}/json').json()
        return (browser_proc,
                websocket.create_connection(resp[0]['webSocketDebuggerUrl']),
                resp[0]['id'])
      except requests.exceptions.ConnectionError:
        time.sleep(sleep_seconds)
        wait_seconds -= sleep_seconds
      except:
        raise

  proc, chromeconn, page_id = StartChrome()

  def IsIP(netloc):
    return re.match(r'\d+\.\d+\.\d+\.\d+', netloc)

  def GetDevtoolsWss(requrl, page):
    parsed = urlparse(requrl)
    if IsIP(parsed.netloc):
      return f'{parsed.netloc}:{debugger_port}/devtools/page/{page}'
    if 'proxy.googleprod.com' in parsed.netloc:
      parsed = libpen.PenEncoded.FromEncoded(parsed.netloc.split('.')[0])
      parsed = parsed.WithPort(int(debugger_port))
      return f'{parsed.Encode()}.proxy.googleprod.com/devtools/page/{page}'
    raise ValueError(f'Cant get devtools WSS from {requrl}, {page}')

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
    devtools_url = GetDevtoolsWss(request.url_root, page_id)
    has_experiments = (request.args.get('experiments') == 'true')
    has_ws = (request.args.get('pid') == page_id)
    has_tabs = request.args.get('tabs')

    if not (has_experiments and has_ws):
      newurl = request.url_root + '?'
      if has_tabs:
        newurl += f'tabs={has_tabs}'
      newurl += f'&experiments=true&wss={devtools_url}&pid={page_id}'
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
    self.SetValueFlag(flag, True)

  def SetValueFlag(self, flag, value):
    while flag.startswith('-'):
      flag = flag[1:]
    setattr(self, flag, value)


class DevDevArgs(FlObAr):
  def __init__(self):
    super().__init__()

  def GetChromeFeatureFlag(self):
    if hasattr(self, 'chrome-features'):
      return f'--enable-features={getattr(self, "chrome-features")}'
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

  def GetHost(self):
    if hasattr(self, 'host'):
      return self.host
    return '127.0.0.1'


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
    debugger_port=args.GetPort(),
    host=args.GetHost(),
    chromeflags=[args.GetChromeFeatureFlag()])
  print('  ==> Chrome Headless Started')

  print(f'  ==> Navigating to {args.GetUrl()}')
  print(ChromeComm(conn, 'Page.navigate', url=args.GetUrl()))
  print('  ==> Navigation complete')
  
  app.run(host=args.GetHost())


if __name__ == '__main__':
  RunItAll()
