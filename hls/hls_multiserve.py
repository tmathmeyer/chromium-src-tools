

import flask
import multiprocessing
import signal
import tempfile
import typing


STREAM_INF = '#EXT-X-STREAM-INF'
DEFAULT = object()


class Variant(typing.NamedTuple):
  url:str
  codecs:list[str]
  bandwidth:int


def GenerateMultivariantPlaylist(variants):
  yield f'#EXTM3U'
  for v in variants:
    codecs = ', '.join(v.codecs)
    yield f'{STREAM_INF}:BANDWIDTH={v.bandwidth},CODECS="{codecs}"'
    yield v.url


class Segment(typing.NamedTuple):
  duration:float
  url:str


def GenerateMediaPlaylist(duration, segments, ptype=DEFAULT, start=DEFAULT):
  yield f'#EXTM3U'
  yield f'#EXT-X-TARGETDURATION:{duration}'
  yield f'#EXT-X-VERSION:3'
  yield f'#EXT-X-MEDIA_SEQUENCE:{0 if start is DEFAULT else start}'
  yield f'#EXT-X-PLAYLIST-TYPE:{"VOD" if ptype is DEFAULT else ptype}'
  for s in segments:
    yield f'#EXTINF:{s.duration}'
    yield s.url


def GuessMimeFromExtension(file):
  if file.endswith('.ts'):
    return 'video/mp2t'
  return 'application/unknown'


def GenerateProxyConfigFromPortmap(url2port):
  yield 'worker_processes 1;'
  yield 'events {'
  yield '  worker_connections 1024;'
  yield '}'
  yield 'http {'
  yield '  gzip on;'
  yield '  sendfile on;'
  for url,port in url2port.items():
    yield '  server {'
    yield '    listen 80;'
    yield f'    server_name {url};'
    yield '    location / {'
    yield f'      proxy_pass http://127.0.0.1:{port}'
    yield '    }'
    yield '  }'
  yield '}'


def OffProcess(func):
  def replacement(*args, **kwargs):
    proc = multiprocessing.Process(target=func, args=args, kwargs=kwargs)
    proc.start()
    return proc
  return replacement


@OffProcess
def HostHLSMainPage(port, urls):
  app = flask.Flask(__name__)
  @app.route('/')
  def host_main():
    return render_template('index.html.template', urls=urls)
  app.run(host='127.0.0.1', port=port)


@OffProcess
def HostHLSMultivariant(port, variants, mimetype=DEFAULT)
  app = flask.Flask(__name__)
  @app.route('/master.m3u8')
  def host_multivariant_playlist():
    playlist = '\n'.join(GenerateMultivariantPlaylist(variants))
    mime = 'video/x-mpegURL' if mimetype is DEFAULT else mimetype
    return flask.Response(playlist, mimetype=mime)
  app.run(host='127.0.0.1', port=port)


@OffProcess
def HostHLSMediaPlaylist(port, duration, segments, mimetype=DEFAULT):
  app = flask.Flask(__name__)
  @app.route('/media.m3u8')
  def host_media_playlist():
    playlist = '\n'.join(GenerateMediaPlaylist(duration, segments))
    mime = 'video/x-mpegURL' if mimetype is DEFAULT else mimetype
    return flask.Response(playlist, mimetype=mime)
  app.run(host='127.0.0.1', port=port)


@OffProcess
def HostHLSSegment(port, mediafiles, mimetype=DEFAULT):
  app = flask.Flask(__name__)
  @app.route('/<segment>')
  def host_segment_data(segment):
    data = os.path.join(mediafiles, segment)
    if mimetype is DEFAULT:
      mimetype = GuessMimeFromExtension(data)
    return flask.send_file(data, mimetype=mimetype)
  app.run(host='127.0.0.1', port=port)


@OffProcess
def HostNGINXProxy(url2port):
  config = tempfile.NamedTemporaryFile()
  config.write('\n'.join(GenerateProxyConfigFromPortmap(url2port)))
  os.system(f'nginx -c {config.name}')


def BipBopCorrectMimes():
  master = 'host1.com/master.m3u8'
  media = 'host2.com/media.m3u8'
  variant = Variant(media, ['mp4a.40.2', 'avc1.4d4015'], 1234)
  segments = [
    Segment(9.97667, 'host3.com/fileSequence0.ts')
    Segment(9.97667, 'host3.com/fileSequence1.ts')
    Segment(9.97667, 'host3.com/fileSequence2.ts')
    Segment(9.97667, 'host3.com/fileSequence3.ts')
    Segment(9.97667, 'host3.com/fileSequence4.ts')
    Segment(9.97667, 'host3.com/fileSequence5.ts')
  ]
  url2port = {
    'host0.com': 8900,
    'host1.com': 8901,
    'host2.com': 8902,
    'host3.com': 8903,
  }
  procs = []
  procs.append(HostHLSMainPage(8900, [master, media]))
  procs.append(HostHLSMultivariant(8901, [variant]))
  procs.append(HostHLSMediaPlaylist(8902, 10, segments))
  procs.append(HostHLSSegment(8903, 'bipbop'))
  procs.append(HostNGINXProxy(url2port))
  return procs



def main():
  signal.signal(signal.SIGINT, signal.SIG_IGN)
  procs = list(BipBopCorrectMimes())
  try:
    for proc in procs:
      proc.join()
  except KeyboardInterrupt:
    for proc in procs:
      proc.terminate()
      proc.join()
