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
from werkzeug.serving import WSGIRequestHandler

from flask_socketio import SocketIO
from socketIO_client import SocketIO as SocketIOClient

from lib import libpen


def createFlaskApp():
  # Needs to happen before app is created!
  WSGIRequestHandler.protocol_version = "HTTP/1.1"
  app = Flask(__name__)
  app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
  # make flask shut up.
  log = logging.getLogger('werkzeug')
  log.disabled = True
  return app


def log(msg, level='status'):
  color = ({
    'info': 92,
    'status': 95,
    'warning': 93,
    'error': 91
  }).get(level, 94)
  msg = str(msg)
  msg = msg.replace("\n", "\n      ")
  print(f'\033[{color}m  ==>\033[0m {msg}')


class ChromeCommCall(object):
  def __init__(self, n, comm):
    self._comm = comm
    self._n = n

  def __getattr__(self, attr):
    return ChromeCommCall(f'{self._n}.{attr}', self._comm)

  def __call__(self, **kwargs):
    return self._comm(self._n, kwargs)


class ChromeComm(object):
  def __init__(self, connection):
    self._connection = connection
    self._reqid = 0

  def __getattr__(self, attr):
    return ChromeCommCall(attr, self)

  def __call__(self, method, params):
    self._reqid += 1
    self._connection.send(json.dumps({
      'method':method, 'id':self._reqid, 'params':params}))
    while True:
      msg = json.loads(self._connection.recv())
      if msg.get('id', None) == self._reqid:
        return msg

  def close(self):
    self._connection.close()


def RunFromOutDir(flaskapp,
                  devtools_src=None,
                  chromiumbinary=None,
                  debugger_port=5001,
                  chromeflags=None,
                  host='127.0.0.1'):

  if chromeflags is None:
    chromeflags = []

  def StartChrome():
    chrome_process_flags = [
       chromiumbinary, '--headless',
       f'--remote-debugging-address={host}',
       f'--remote-debugging-port={debugger_port}'] + chromeflags
    flagstr = '\n'.join(chrome_process_flags)
    log(f'Chrome flags:\n{flagstr}', level='info')
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
    raise 'Chrome not starting!'

  proc, chromeconn, page_id = StartChrome()

  def IsIP(netloc):
    return re.match(r'\d+\.\d+\.\d+\.\d+', netloc)

  def GetDevtoolsWss(requrl, page):
    parsed = urlparse(requrl)
    netloc = parsed.netloc.split(':')[0]
    if IsIP(netloc):
      return f'ws={netloc}:{debugger_port}/devtools/page/{page}'
    if 'proxy.googleprod.com' in netloc:
      parsed = libpen.PenEncoded.FromEncoded(netloc.split('.')[0])
      parsed = parsed.WithPort(int(debugger_port))
      return f'wss={parsed.Encode()}.proxy.googleprod.com/devtools/page/{page}'
    if 'localhost' in netloc:
      return f'ws={netloc}:{debugger_port}/devtools/page/{page}'
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

  @flaskapp.route('/')
  def rewrite():
    devtools_url = GetDevtoolsWss(request.url_root, page_id)
    has_experiments = (request.args.get('experiments') == 'true')
    has_ws = (request.args.get('pid') == page_id)
    has_tabs = request.args.get('tabs')

    if not (has_experiments and has_ws):
      newurl = request.url_root + '?'
      if has_tabs:
        newurl += f'tabs={has_tabs}'
      newurl += f'&experiments=true&{devtools_url}&pid={page_id}'
      return redirect(newurl, code=302)
    with open(os.path.join(devtools_src, 'devtools_app.html'), 'r') as f:
      textual = f.read()
      first_bit, second_bit = textual.split('</head>')
      return f'{first_bit}{hijackJS()}{second_bit}'

  @flaskapp.route('/<path:path>')
  def serve(path):
    return send_from_directory(devtools_src, path)

  return proc, ChromeComm(chromeconn)


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

  def GetDevtoolsSrc(self):
    if hasattr(self, 'srcs'):
      return self.srcs
    return os.path.join(
      os.environ['CHROMIUM_SRC'],
      'out', self.GetOutDir(),
      'resources', 'inspector')

  def GetChromiumBinary(self):
    if hasattr(self, 'binary'):
      return self.binary
    return os.path.join(
      os.environ['CHROMIUM_SRC'],
      'out', self.GetOutDir(), 'chrome')


def RunItAll():
  proc = None,
  conn = None
  original = signal.getsignal(signal.SIGINT)
  def kill_me(num, fr):
    print('')  # get newline after ^C
    signal.signal(signal.SIGINT, original)
    if proc:
      proc.terminate()
      log('Headless Chrome terminated')
    if conn:
      conn.close()
      log('Connections closed')
    log('Exiting...')
    sys.exit()
  signal.signal(signal.SIGINT, kill_me)
  log('Signals Up')

  args = DevDevArgs()
  log('Args Parsed')

  flaskapp = createFlaskApp()
  proc, conn = RunFromOutDir(
    flaskapp,
    devtools_src=args.GetDevtoolsSrc(),
    chromiumbinary=args.GetChromiumBinary(),
    debugger_port=args.GetPort(),
    host=args.GetHost(),
    chromeflags=[args.GetChromeFeatureFlag()])
  log('Chrome Headless Started')

  log(f'Navigating to {args.GetUrl()}')
  log(conn.Page.navigate(url=args.GetUrl()), level='info')
  log('Navigation complete')

  flaskapp.run(host=args.GetHost())


if __name__ == '__main__':
  RunItAll()
