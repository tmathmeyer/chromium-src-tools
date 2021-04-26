#!/usr/bin/env python3.9

import asyncio
from flask import Flask, escape, request, send_from_directory, redirect
import json
import logging
from multiprocessing import Process
import os
import re
import requests
import signal
import subprocess
import sys
import time
from urllib.parse import urlparse
import websocket
import websockets
from werkzeug.serving import WSGIRequestHandler

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
    if params:
      self._connection.send(json.dumps({
        'method':method, 'id':self._reqid, 'params':params}))
    else:
      self._connection.send(json.dumps({
        'method':method, 'id':self._reqid}))
    while True:
      msg = json.loads(self._connection.recv())
      if msg.get('id', None) == self._reqid:
        return msg

  def close(self):
    self._connection.close()


class WhatsAlive(Exception):
  def __init__(self, chrome=False, connection=False):
    super().__init__()
    self.chrome = chrome
    self.connection = connection


def StartChrome(binary, port, flags):
  host = '127.0.0.1'
  chrome_process_flags = [
     binary, '--headless',
     #f'--remote-debugging-address={host}',
     f'--remote-debugging-port={port}'] + flags
  flagstr = '\n'.join(chrome_process_flags)
  log(f'Chrome flags:\n{flagstr}', level='info')
  browser_proc = subprocess.Popen(chrome_process_flags)
  wait_seconds = 30
  sleep_seconds = 0.5
  while wait_seconds > 0:
    try:
      resp = requests.get(f'http://{host}:{port}/json').json()
      return (browser_proc,
              resp[0]['devtoolsFrontendUrl'],
              websocket.create_connection(resp[0]['webSocketDebuggerUrl']),
              resp[0]['id'])
    except requests.exceptions.ConnectionError:
      time.sleep(sleep_seconds)
      wait_seconds -= sleep_seconds
    except IndexError:
      time.sleep(sleep_seconds)
      wait_seconds -= sleep_seconds
    except:
      raise
  raise WhatsAlive(chrome=True)


def IsIP(netloc):
  return re.match(r'\d+\.\d+\.\d+\.\d+', netloc)


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

  def ShouldShowHelp(self):
    if hasattr(self, 'help'):
      print('[CHROMIUM_SRC=*] devdev.py [--outdir=Default] '
            '[--chrome-features=*,*] [--port=9001] [--url=about:blank] '
            '[--host=127.0.0.1]')
      exit()

  def GetPort(self, default=9222):
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


def MakeWSProxy(comm, proxyport, pageid):
  def startserver(com):
    print(f'making WS proxy from :9001 -> :{proxyport}')
    async def devtools(WS, path):
      while True:
        request = await WS.recv()
        request = json.loads(request)
        response = comm(request['method'], request.get('params', None))
        response['id'] = request['id']
        print(f'{request["id"]} => {response["id"]}')
        await WS.send(json.dumps(response))
    loop = asyncio.new_event_loop()
    starts = websockets.serve(devtools, '0.0.0.0', proxyport, loop=loop)
    loop.run_until_complete(starts)
    loop.run_forever()
    print('proxy dead')

  server = Process(target=startserver, args=(comm,))
  server.start()
  os.system(f'curl http://localhost:{proxyport}/')
  return server



def GetDevtoolsWss(requrl, page, debugger_port, proxy, chromecomm):
  absolve_me = False
  if not proxy:
    proxy['wsproxy'] = None
    absolve_me = True

  parsed = urlparse(requrl)
  netloc = parsed.netloc.split(':')[0]
  # Connect directly to chrome
  if IsIP(netloc) or ('localhost' in netloc):
    return f'ws={netloc}:{debugger_port}/devtools/page/{page}'

  # This is some real bullshit
  if 'proxy.googleprod.com' in netloc:
    proxyport = debugger_port+1
    if absolve_me:
      proxy['wsproxy'] = MakeWSProxy(chromecomm, proxyport, page)
    parsed = libpen.PenEncoded.FromEncoded(netloc.split('.')[0])
    parsed = parsed.WithPort(int(proxyport))
    return f'wss={parsed.Encode()}.proxy.googleprod.com/devtools/page/{page}'

  raise ValueError(f'Cant get devtools WSS from {requrl}, {page}')


def RunFromOutDir(flaskapp,
                  devtools_src=None,
                  chromiumbinary=None,
                  debugger_port=5001,
                  chromeflags=None,
                  host='127.0.0.1'):
  if None in (flaskapp, devtools_src, chromiumbinary, debugger_port, host):
    raise WhatsAlive()

  if chromeflags is None:
    chromeflags = []

  proc, FEURL, chromeconn, page_id = StartChrome(
    chromiumbinary, debugger_port, chromeflags)
  maybeProxy = {}
  chromeconn = ChromeComm(chromeconn)

  def hijackJS():
    tabs = request.args.get('tabs')
    result = '<script type="module">'
    if tabs:
      tabs = tabs.split(',')
    else:
      tabs = []
    #tabs.append('protocolMonitor')
    for enable in tabs:
      result += f"Root.Runtime.experiments.setEnabled('{enable}', true);"
    result += '</script>'
    return result

  @flaskapp.route('/')
  def rewrite():
    #GetDevtoolsWss(request.url_root, page_id, debugger_port, maybeProxy, chromeconn)
    devtools_url = FEURL.split('?')[1]
    has_experiments = (request.args.get('experiments', None) != None)
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
      return textual
      #print(textual)
      #first_bit, second_bit = textual.split('</head>')
      #return f'{first_bit}{hijackJS()}{second_bit}'

  @flaskapp.route('/<path:path>')
  def serve(path):
    try:
      return send_from_directory(devtools_src, path)
    except:
      if path.startswith('common/'):
        return serve(path[7:])
      if path.startswith('core/'):
        return serve(path[5:])
      if path.startswith('models/'):
        return serve(path[7:])
      if path.startswith('text_utils/'):
        return send_from_directory(devtools_src, 'text_editor/' + path[11:])


      if path == 'ui/legacy/legacy.js':
        return send_from_directory(devtools_src, 'ui/ui-legacy.js')

      if path == 'ui/legacy/ui.js':
        return send_from_directory(devtools_src, 'ui/ui.js')
      if path == 'text_utils/CodeMirrorUtils.js':
        return send_from_directory(devtools_src, 'text_editor/CodeMirrorUtils.js')

      if path.startswith('ui/legacy/'):
        return send_from_directory(devtools_src, 'ui/' + path[10:])


      real = os.path.join(devtools_src, path)
      print(f'Cant load {path} from {real}')
      os.system(f'ls -lash {real}')

      return send_from_directory(devtools_src, path)

  return proc, chromeconn, maybeProxy


def RunItAll():
  proc = None
  conn = None
  proxy = None
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
    if proxy:
      for p in proxy.values():
        if p:
          p.terminate()
          p.join()
    log('Exiting...')
    sys.exit()
  signal.signal(signal.SIGINT, kill_me)
  log('Signals Up')

  args = DevDevArgs()
  args.ShouldShowHelp()
  log('Args Parsed')

  flaskapp = createFlaskApp()
  try:
    proc, conn, proxy = RunFromOutDir(
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
  except WhatsAlive as alive:
    kill_me()


if __name__ == '__main__':
  RunItAll()
