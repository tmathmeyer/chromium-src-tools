#!/usr/bin/python3

import os
import sys
import tempfile
import json
import requests
from datetime import datetime
from lib import libgit, librun, libjson


TOOLS = os.path.dirname(__file__)
BINARIES = 'ted@50.47.216.50:/media/chrome_binaries/'
DATA_SERVICE = 'ted@tedm.io:/var/www/binary_builds/hashes/'
PATCH_SERVICE = 'ted@tedm.io:/var/www/binary_builds/patches/'


def CollectIssues(branch:libgit.Branch) -> [str]:
  if branch.Name() == 'main':
    return []
  result = CollectIssues(branch.Parent())
  try:
    result.append(getattr(branch, 'gerritissue', ''))
  except:
    pass
  return result


def GenerateDiffAndHash() -> (str, str):
  try:
    branch = libgit.Branch.Current()
    ahead, behind = branch.AheadBehindBranch('main')

    if behind != 0:
      raise ValueError(f'Branch {branch} is not rebased to tip-of-tree')

    fd, patchfile = tempfile.mkstemp()
    os.close(fd)
    os.system(f'git diff main {branch} >> {patchfile}')
    md5 = librun.OutputOrError(f'md5sum {patchfile}').split()[0].strip()
    return md5, patchfile
  except:
    fd, patchfile = tempfile.mkstemp()
    os.close(fd)
    os.system(f'echo BACKDATE >> {patchfile}')
    md5 = librun.OutputOrError(f'md5sum {patchfile}').split()[0].strip()
    return md5, patchfile


class CommandLineArgs():
  help:bool = False
  dryrun:bool = True
  verbose:bool = False
  force:bool = False
  notes:str = ''
  os:str = 'linux'

  @classmethod
  def PrintHelp(cls):
    helpstr = 'archiver.py'
    for key in ['help', 'dryrun', 'verbose', 'force', 'notes', 'os']:
      helpstr += f' [--{key}={getattr(cls, key)}]'
    print(helpstr)

  def _parse_value(self, t:type, value:str):
    if t is bool:
      if value in ('true', 'True'):
        return True
      if value in ('false', 'False'):
        return False
    return t(value)

  def _parse_arg(self, arg:str, following:str):
    must_parse = False
    if '=' in arg:
      must_parse = True
      arg, following = arg.split('=', 1)
    if not must_parse and following and not following.startswith('--'):
      must_parse = True
    flag_value = arg[2:]  # drop the leading --
    flag_type = type(getattr(self, flag_value))
    if flag_type is not bool or must_parse:
      setattr(self, flag_value, self._parse_value(flag_type, following))
    else:
      setattr(self, flag_value, True)

  def __repr__(self):
    return str(self)

  def __str__(self):
    keys = ['dryrun', 'verbose', 'force', 'notes', 'os', 'help']
    attrs = [f'{v}={getattr(self, v)}' for v in keys]
    return ', '.join(attrs)

  def __init__(self, opts:[str]):
    for idx, opt in enumerate(opts):
      if opt.startswith('--'):
        following = opts[idx+1] if idx+1 < len(opts) else ''
        self._parse_arg(opt, following)


class ToolOptions():
  packager:str = ''
  binary:str = ''
  build:str = ''
  cli:CommandLineArgs = None
  hash_value = ''

  def __init__(self, cli, hash_value):
    self.cli = cli
    self._setupOs(hash_value)
    self.hash_value = hash_value

  def _setupOs(self, hash_value):
    if self.cli.os == 'linux':
      self.binary = f'{hash_value}.zip'
      self.packager = f'{TOOLS}/tools/package.linux.py --package {self.binary}'
      self.build = 'autoninja -C out/Release chrome'
    elif self.cli.os == 'win':
      self.binary = f'{hash_value}_mini_installer.exe'
      self.packager = f'mv out/Windows/mini_installer.exe {self.binary}'
      self.build = 'autoninja -C out/Windows mini_installer'
    else:
      raise ValueError ('--os must be one of [linux|win]')

  def log(self, value):
    if not self.cli.verbose:
      return
    print(value)

  def run(self, cmd):
    if not self.cli.dryrun:
      librun.OutputOrError(cmd)
    else:
      print(cmd)


class ApiInterfaces():
  @staticmethod
  def BuildExists(hash_value:str) -> bool:
    return hash_value in libjson.JSON.FromURL('https://archives.tedm.io/hashes')

  @staticmethod
  def UploadArchive(opts:ToolOptions):
    staging = 'ted@nas.lan.tedm.io:/raid/array0/chromearchives/staging/'
    opts.run(f'scp {opts.binary} {staging}')
    opts.run(f'rm {opts.binary}')

  @staticmethod
  def UploadMetadata(opts:ToolOptions, patchfile:str):
    with open(patchfile, 'r') as f:
      return requests.post('https://chrome.lan.tedm.io/api/notify', data=json.dumps({
        'signature': opts.hash_value,
        'patches': [f.read()],
        'notes': '---',
        'operating_system': opts.cli.os,
      }))

  @staticmethod
  def GenerateMetadataFile(hash_value:str, binary:str, notes:str=None) -> str:
    try:
      revisions = CollectIssues(libgit.Branch.Current())
    except:
      revisions = []

    with open(hash_value, 'w') as f:
      f.write(f'{str(datetime.now())}\n')
      f.write(f'{hash_value}\n')
      f.write(f'[{",".join(revisions)}]\n')
      f.write(f'{binary}\n')
      if notes:
        f.write(f'{notes}')
    return hash_value

  @staticmethod
  def UploadFiles(opts:ToolOptions, metadata:str, patch:str):
    opts.run(f'scp {metadata} {DATA_SERVICE}')
    opts.run(f'chmod 644 {opts.binary}')
    opts.run(f'scp {opts.binary} {BINARIES}')
    opts.run(f'scp {patch} {PATCH_SERVICE}{metadata}')
    opts.run(f'rm {opts.binary} {patch} {metadata}')


def main():
  cli = CommandLineArgs(sys.argv[1:])
  if cli.help:
    return CommandLineArgs.PrintHelp()

  hash_value, patchfile = GenerateDiffAndHash()

  opts = ToolOptions(cli, hash_value)
  opts.log(cli)
  opts.log('Starting build')
  opts.run(opts.build)
  opts.log('Packaging')
  opts.run(opts.packager)
  opts.log('Collecting metadata')

  ApiInterfaces.UploadArchive(opts)
  response = ApiInterfaces.UploadMetadata(opts, patchfile)
  print(response)
  print(response.text)

  opts.log('Done.')


if __name__ == '__main__':
  main()
