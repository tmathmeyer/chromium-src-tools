#!/usr/bin/env python3

import collections
import os
import subprocess
import sys

def RunCommand(command):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)

def CheckCommand(command):
  print(command)
  res = RunCommand(command)
  if res.returncode:
    print(res.stderr)
    raise ValueError(res.returncode)
  else:
    print(res.stdout)

LOF = [
  'chrome',
  'crashpad_handler',
  'chrome_100_percent.pak',
  'chrome_200_percent.pak',
  'chrome_sandbox',
  'icudtl.dat',
  'libEGL.so',
  'libGLESv2.so',
  'resources.pak',
  'v8_context_snapshot.bin',
  'libminigbm.so',
  'chrome_crashpad_handler',
]

LOD = [
  'extensions',
  'locales',
]

def make_zip(name, sofiles):
  if not name.endswith('.zip'):
    name += '.zip'

  zipcontent = ' '.join(LOF + LOD)
  if sofiles is not None:
    CheckCommand(f'zip -q -r {name} {zipcontent} *.so')
  else:
    CheckCommand(f'zip -q -r {name} {zipcontent}')


def parseArgs(*args, **kwargs):
  cmdline = sys.argv
  unlabeled = []
  prev_key = None
  for arg in sys.argv[1:]:
    if arg.startswith('--'):
      if prev_key is not None:
        kwargs[prev_key] = True
      prev_key = arg[2:]
    elif prev_key is not None:
      kwargs[prev_key] = arg
      prev_key = None
    else:
      unlabeled.append(args)
  for k, v in zip(args, unlabeled):
    kwargs[k] = v
  tup = collections.namedtuple('argpack', list(kwargs.keys()))
  return tup(**kwargs)


if __name__ == '__main__':
  args = parseArgs(outdir='Archive', package='chrome_pkg.zip', sofiles=None)
  print(args)

  os.chdir(f'out/{args.outdir}')
  make_zip(f'../../{args.package}', args.sofiles)
  os.chdir('../../')
