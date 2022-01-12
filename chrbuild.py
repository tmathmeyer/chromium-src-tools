#!/usr/bin/env python3

# chromium build script!

import json
import sys
import subprocess
import os
import shutil
import re
import requests
from urllib.parse import urlparse


CONFIG = {}

def GetGomaDir():
  goma_dir = shutil.which('goma_ctl')
  return os.path.join(os.path.dirname(goma_dir), '.cipd_bin')


def WriteDefaultConfig(path):
  home = os.environ['HOME']
  default_varaibles = {
    'goma_root': GetGomaDir(),
    'src_directory': f'/chromium/src',
    'virtualenv': None,
  }
  if not os.path.exists(os.path.dirname(path)):
    os.makedirs(os.path.dirname(path))
  with open(path, 'w+') as f:
    for k,v in default_varaibles.items():
      f.write(f'{k} = {repr(v)}\n')
  global CONFIG
  CONFIG = default_varaibles


def ReadConfig(path):
  environ = {}
  with open(path, 'r') as f:
    exec(compile(f.read(), path, 'exec'), environ)
  del environ['__builtins__']
  global CONFIG
  CONFIG = environ


def SetupEnv():
  env_location = os.environ['HOME']
  if 'CHROMIUM_ROOT' in os.environ:
    env_location = os.environ['CHROMIUM_ROOT']
  config_path = f'{env_location}/.config/chromium/variables.config'
  if not os.path.exists(config_path):
    WriteDefaultConfig(config_path)
    return
  ReadConfig(config_path)


def EnsurePython():
  python_directory = CONFIG['virtualenv']
  if python_directory is None:
    CONFIG['activate'] = 'echo ACTIVATED'
    return
  CONFIG['activate'] = f'source {python_directory}/bin/activate'
  if os.path.exists(python_directory):
    return
  os.system(f'virtualenv -p /usr/bin/python2.7 {python_directory}')
  os.system('python --version')


def RunCommand(command, stream_stdout=False):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=(None if stream_stdout else subprocess.PIPE))


class Complete():
  """Auto complet generator."""
  def __init__(self):
    self.functions = {}

  def __call__(self, name, usage):
    def __wrap__(func):
      self.functions[name] = {
        'func': func,
        'usage': usage
      }
      return func
    return __wrap__

  def run(self):
    if len(sys.argv) == 1:
      self.usage()
    elif sys.argv[1] == '-X':
      for k in self.functions.keys():
        if k.startswith(sys.argv[3]):
          print(k)
    else:
      kwargs = {}
      args = []
      for arg in sys.argv[2:]:
        if arg[0] == '-':
          if '=' in arg:
            key, val = arg[1:].split('=')
            kwargs[key] = val
          else:
            kwargs[arg[1:]] = True
        else:
          args.append(arg)

      # Ensure goma is running
      os.system(f'{CONFIG["goma_root"]}/goma_ctl.py ensure_start 2>/dev/null > /dev/null')
      EnsurePython()
      outcome = self.run_func(self.fail, sys.argv[1], args, kwargs)

  def run_func(self, onfail, name, args, kwargs):
    return self.functions.get(name, onfail())['func'](*args, **kwargs)

  def fail(self):
    return {
      'func': self.usage
    }

  def usage(self, *unused_args):
    for k,v in self.functions.items():
      print('{}:\n\t{}'.format(k, v['usage']))


complete = Complete()


class Build():
  """General builder class."""
  def default_args(self):
    return {
      'is_component_build': 'true',
      'proprietary_codecs': 'true',
      'enable_nacl': 'false',
      'dcheck_always_on': 'true',
      'use_goma': 'true',
      'goma_dir': '"{}"'.format(CONFIG['goma_root']),
      'is_clang': 'true',
      'symbol_level': '1',
      'enable_mse_mpeg2ts_stream_parser': 'true',
      'ffmpeg_branding': '"ChromeOS"'
    }

  def __init__(self, target='chrome', base='Default', gn_args=None, j=1000):
    self.target = target
    self.base = base
    self.gn_args = self.default_args()
    self.gn_args.update(gn_args or {})
    self.j = j

  def args(self):
    return '\n'.join('{}={}'.format(k,v) for k,v in self.gn_args.items() if v != None)

  def run(self, *args, **kwargs):
    if not os.path.isdir('{}/out/{}'.format(CONFIG['src_directory'], self.base)):
      os.system('gn gen out/{} --check --args=\'{}\''.format(self.base, self.args()))
    # TODO: return the stdout here!
    self.__dict__.update(kwargs)
    ninja = f'ninja -C out/{self.base} {self.target} -j{self.j}'
    print(ninja)
    res = RunCommand(ninja, stream_stdout=True)
    return res



class NoBuild(Build):
  def run(self, *args, **kwargs):
    pass






RPC = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild'
FMT = r'https://ci\.chromium\.org/ui/p/(\S+)/builders/(\S+)/(\S+)/([b]*[0-9]+)'
PARSER = re.compile(FMT)

def get_request_payload(url):
  try:
    groups = PARSER.match(url).groups()
    return {
      'builder': {
        'project': groups[0],
        'bucket': groups[1],
        'builder': groups[2],
      },
      'buildNumber': groups[3],
      'fields': 'steps,id'
    }
  except AttributeError:
    raise ValueError(f'{FMT} could not match {url}')

class BuildbotEntries(object):
  def __init__(self, url):
    self._compile_targets = []
    self._gn_args = {}
    q = requests.post(
      url=RPC,
      data=json.dumps(get_request_payload(url)),
      headers={
        'content-type': 'application/json',
        'accept': 'application/json'
      })
    if q.status_code != 200:
      raise ValueError(f'RPC to {RPC} failed')
      self._json = {}
    else:
      self._json = json.loads(q.text[5:])

  def GetCompileTargets(self):
    if self._compile_targets:
      return self._compile_targets
    for step in self._json.get('steps', []):
      if step['name'] == 'generate_build_files (with patch)':
        for log in step.get('logs', []):
          if log['name'] == 'swarming-targets-file.txt':
            return self._GetCompileTargetsFromTargetsFileUrl(
              log['viewUrl']+'?format=raw')
    return ['all']

  def _GetCompileTargetsFromTargetsFileUrl(self, url):
    return str(requests.get(url).content)[2:-1].strip().split('\\n')[:-1]

  def _GetCompileTargetsFromURL(self, url):
    stdout = str(requests.get(url).content).split('\\n')
    targets = []
    found_targets = 2
    index = 0
    while found_targets:
      if stdout[index] == ' &#39;-j&#39;,' and found_targets == 2:
        found_targets = 1
      elif found_targets == 1:
        line = stdout[index].strip().replace('&#39;', '\'')
        find = re.search(r'\'([a-zA-Z:/_]+)\'', line)
        if find:
          targets.append(find.group(1))
        if line.endswith(']'):
          found_targets = 0
      index += 1
    self._compile_targets = targets
    return targets

  def GetGNArgs(self):
    if self._gn_args:
      return self._gn_args
    for step in self._json.get('steps', []):
      if step['name'] == 'compilator steps (with patch)|lookup GN args':
        for log in step.get('logs', []):
          if log['name'] == 'execution details':
            return self._GetGnArgsFromURL(log['viewUrl'])
        raise ValueError('Could not get \'logs\' json entry for gn args')
    raise ValueError(f'Could Not Find GN Args')

  def _GetGnArgsFromURL(self, url):
    master = ''
    builder = ''
    cmd = str(requests.get(url+'?format=raw').content, 'utf-8').split('\n')
    if (cmd[0]) != 'Executing command [':
      raise ValueError(f'Could not get command from {url}')

    def yield_until_closebracket():
      for line in cmd[1:]:
        if line.strip() == ']':
          return
        yield line.strip()[1:-2]

    cmd = list(yield_until_closebracket())
    for i, arg in enumerate(cmd):
      if arg == "-m":
        master = cmd[i+1]
      if arg == "-b":
        builder = cmd[i+1]

      if master and builder:
        print(master, builder)
        command = './tools/mb/mb.py lookup -m {} -b {} --quiet'
        try:
          import subprocess
          stdout = subprocess.check_output(
            command.format(master, builder), shell=True)
          for entry in str(stdout, 'utf-8').split('\n'):
            _e = entry.split(' = ')
            if entry:
              self._gn_args[_e[0]] = _e[1]
          return self._gn_args
        except:
          print("Can't get gn args because the command fails:")
          print(command.format(master, builder))
          exit()


class MultiBuild():
  def __init__(self, targets, together=False):
    self.targets = targets
    self.base = 'Misc'
    self.gn_args = Build().default_args()
    self._together = together

  def run(self, *args, **kwargs):
    if self._together:
      self._run_together(*args, **kwargs)
    else:
      self._run_apart(*args, **kwargs)

  def _run_together(self, *args, **kwargs):
    target = ' '.join(self.targets)
    x = complete.run_func(lambda:{
        'func': goma_build(lambda *args: Build(
          target=target,
          base=self.base,
          gn_args=self.gn_args,
          j=getattr(self, 'j', 1000)))
    }, target, [], {})
    if x.returncode == 1:
      if x.stderr.startswith('ninja: error: unknown target'):
        drop = x.stderr[30:-2]
        print(f'Invalid target: {drop} --- retrying without it')
        self.targets = set(self.targets)
        self.targets.remove(drop)
        self._run_together(*args, **kwargs)
      else:
        print(x.stderr)

  def _run_apart(self, *args, **kwargs):
    total = len(self.targets)
    for i, target in enumerate(self.targets):
      print('Building: [{}/{}] {}'.format(i, total, target))
      complete.run_func(lambda:{
          'func': goma_build(lambda *args: Build(
            target=target,
            base=self.base,
            gn_args=self.gn_args,
            j=getattr(self, 'j', 1000)))
      }, target, [], {})


class goma_build():
  def __init__(self, func):
    self.func = func

  def __call__(self, *args, **kwargs):
    return self.func(*args).run(*args, **kwargs)


@complete('bot', 'build the targets the way a bot does')
@goma_build
def buildbot(url, *jobs):
  parsed = urlparse(url)
  if parsed.netloc == 'logs.chromium.org' and parsed.path.endswith('stdout'):
    raise ValueError('Please provide the ci bot args')

  bb = BuildbotEntries(url)
  jobs = jobs or bb.GetCompileTargets()
  multibuild = MultiBuild(jobs, together=True)
  multibuild.gn_args.update(bb.GetGNArgs())
  outdir = parsed.path.split('/')[-3].replace('_', '').upper()
  multibuild.base = 'BOT-' + outdir
  return multibuild



"""
Meta Builders - they can apply to other rules!
"""
def metabuilder(func):
  def _wrapper(name, *args):
    builder = complete.functions[name]['func'].func(*args)
    builder = func(builder, name, *args)
    builder.base = '-'.join([func.__name__, builder.base])
    builder.run(*args)
  return _wrapper

def check_is_linux(builder, rule):
  if 'target_os' in builder.gn_args:
    if builder.gn_args['target_os'] != 'Linux':
      raise Exception('{} only supports linux!')

@complete('debugme', 'build any target as debuggable')
@metabuilder
def debugme(builder, *_):
  check_is_linux(builder, 'debugme')
  builder.gn_args.update({
    'strip_absolute_paths_from_debug_symbols': 'true',
    'is_debug': 'true',
    'use_debug_fission': 'false',
    'symbol_level': '2',
  })
  return builder

@complete('fuzzme', 'build any target as fuzzzzzzzable')
@metabuilder
def fuzzme(builder, *_):
  check_is_linux(builder, 'fuzzme')
  builder.gn_args.update({
    'is_asan': 'true',
    'enable_nacl': 'false',
    'is_asan': 'true',
    'is_debug': 'false',
    'optimize_for_fuzzing': 'true',
    'pdf_enable_xfa': 'true',
    'proprietary_codecs': 'true',
    'use_libfuzzer': 'true',
  })
  return builder

@complete('asanify', 'build any target with asan')
@metabuilder
def asanify(builder, *_):
  builder.gn_args.update({
    'is_asan' :'true',
    'is_debug' :'false'
  })
  return builder

@complete('tsanify', 'build any target with tsan')
@metabuilder
def tsanify(builder, *_):
  builder.gn_args.update({'is_tsan': 'true'})
  return builder

@complete('msanify', 'build any target with msan')
@metabuilder
def msanify(builder, *_):
  builder.gn_args.update({
    'is_msan': 'true',
    'is_debug': 'false',
    'msan_track_origins': '2'
  })
  return builder

@complete('Windows', 'build a target for windows')
@metabuilder
def Windows(builder, *_):
  builder.gn_args.update({
    'target_os': '"win"',
    'use_goma': 'true',
    'proprietary_codecs': 'true',
    'ffmpeg_branding': '"Chrome"',
    'is_debug': 'true',
  })
  builder.j = 60
  return builder


"""
Default build targets!
"""
@complete('chromium', 'build standard chromium')
@goma_build
def chromium():
  return Build()

@complete('devtools', 'build chromium with debug devtools')
@goma_build
def devtools():
  return Build(base='Inspector', gn_args={
    'debug_devtools': 'true',
  })

@complete('chrelease', 'build standard chromium (in release)')
@goma_build
def chromium():
  return Build(base='Release', gn_args={
    'proprietary_codecs': 'true',
    'enable_nacl': 'false',
    'use_goma': 'true',
    'is_official_build': 'true',
    'is_clang': 'true',
    'symbol_level': '0',
    'ffmpeg_branding': '"Chrome"',
    'use_vaapi': 'true',
    'is_debug': 'false',
  })

@complete('apk', 'build chrome for android')
@goma_build
def android():
  return Build(target='chrome_public_apk', base='Android', gn_args={
    'target_os': '"android"',
    'proprietary_codecs': 'true',
    'ffmpeg_branding': '"Chrome"',
  })

@complete('cast_shell', 'build the cast shell for linux (android TV)')
@goma_build
def cast_shell():
  return Build(target='cast_shell', base='Release', gn_args={
    'target_os': '"android"',
    'is_chromecast': 'true',
    'ffmpeg_branding': '"Chrome"'
  })

@complete('content_unit_tests', 'build the content unit tests')
@goma_build
def content_unittests():
  return Build(target='content_unittests', base='Tests')

@complete('web_tests', 'build the content unit tests')
@goma_build
def web_tests():
  targets = ['content_shell', 'image_diff', 'minidump_stackwalk', 'dump_syms']
  multibuild = MultiBuild(targets)
  multibuild.base = 'Tests'
  return multibuild

  return Build(target='content_shell', base='Tests')

@complete('media_unit_tests', 'build the media unit tests')
@goma_build
def media_unittests():
  return Build(target='media_unittests', base='Tests', gn_args={
    'is_debug': 'true',
  })

@complete('ffmpeg_regression_tests', 'build the ffmpeg regression tests')
@goma_build
def media_unittests():
  return Build(target='ffmpeg_regression_tests', base='Tests', gn_args={
    'is_debug': 'true',
  })

@complete('content_browser_tests', 'build the content browser tests')
@goma_build
def content_unittests():
  return Build(target='content_browsertests', base='Tests')

@complete('browser_tests', 'build the browser tests')
@goma_build
def browsertests():
  return Build(target='browser_tests', base='Tests')

@complete('blink_tests', 'build the blink layout tests')
@goma_build
def browsertests():
  return Build(target='blink_tests', base='Tests')

@complete('blink_tests', 'build the webkit layout tests')
@goma_build
def webkit_layout_tests():
  return Build(target='blink_tests', base='Tests')

@complete('webkit_smoke_tests', 'build the webkit smoke tests')
@goma_build
def webkit_layout_tests():
  return Build(target='webkit_smoke_tests', base='Tests')

@complete('chromedriver', 'build chromedriver')
@goma_build
def chromedriver():
  return Build(target='chromedriver', base='Chromedriver')

@complete('android_telemetry_tests', 'build the android telemetry tests')
@goma_build
def webkit_layout_tests():
  return Build(target='telemetry_perf_unittests', base='Android', gn_args={
    'target_os': '"android"',
    'proprietary_codecs': 'true',
    'ffmpeg_branding': '"Chrome"',
  })

@complete('windows_chrome', 'build chrome for windows')
@goma_build
def windows_chrome():
  return Build(base='Windows', gn_args={
    'target_os': '"win"',
    'is_component_build': 'true',
    'use_goma': 'false',
    'proprietary_codecs': 'true',
    'ffmpeg_branding': '"Chrome"',
    'is_component_build': 'true',
    'is_debug': 'false',
  }, j=60)

@complete('mini_installer', 'build chrome for windows')
@goma_build
def windows_chrome():
  return Build(target='mini_installer', base='Win', gn_args={
    'target_os': '"win"',
    'is_component_build': 'true',
    'use_goma': 'true',
    'proprietary_codecs': 'true',
    'ffmpeg_branding': '"Chrome"',
    'is_component_build': 'true',
    'is_debug': 'true',
  }, j=60)

@complete('linux_chromium_rel_ng', 'linux_chromium_rel_ng')
@goma_build
def webkit_layout_tests():
  return Build(target='linux_chromium_rel_ng', base='Tests')


@complete('fuchsia_media_unit_tests', 'media unittests for fuchsia')
@goma_build
def fuchsia_mut():
  return Build(target='media_unittests', base='Fuchsia', gn_args={
    'target_os': '"fuchsia"',
    'dcheck_always_on': 'true',
    'is_debug': 'true',
    'is_component_build': 'false'
    })

@complete('build_many', 'build a bunch of targets')
@goma_build
def build_many(*args):
  return MultiBuild(args)


# TODO uugh get rid of this
@complete('winfuzz', 'build fuzzer tests for windows')
@goma_build
def winfuzz(target):
  print('building fuzzer: {}'.format(target))
  return Build(target=target, base='WinFuzz', gn_args={
    'target_os': '"win"',
    'enable_nacl': 'false',
    'use_goma': 'false',
    'ffmpeg_branding': '"Chrome"',
    'is_asan': 'true',
    'is_component_build': 'false',
    'is_debug': 'false',
    'pdf_enable_xfa': 'true',
    'proprietary_codecs': 'true',
    'strip_absolute_paths_from_debug_symbols': 'true',
    'symbol_level': '1',
    'use_libfuzzer': 'true'
    })

@complete('update', 'update chromium')
def update():
  branch = subprocess.check_output(['git', 'rev-parse', '--apprev-ref', 'HEAD'])
  if str(branch).strip() != 'master':
    os.system('git stash')
  os.system('git checkout master')
  os.system('git pull --rebase')
  os.system('gclient sync')
  if branch != 'master':
    os.system('git checkout %s' % branch)

@complete('clusterfuzz', 'run a clusterfuzz!')
def clusterfuzz(*args):
  CF_BINARY = '/google/data/ro/teams/clusterfuzz-tools/releases/clusterfuzz'
  for cf_testcase in args:
    cmd = f'{CF_BINARY} reproduce {cf_testcase} --current'
    os.system(cmd)



if __name__ == '__main__':
  SetupEnv()
  if os.getcwd() != CONFIG['src_directory']:
    raise Exception('only works in //chromium/src directory!')
  complete.run()
