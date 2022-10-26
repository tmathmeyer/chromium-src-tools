#!/usr/bin/python
import os
import sys
import tempfile
from datetime import datetime
from lib import libgit, librun, libjson


TOOLS = os.path.dirname(__file__)
BINARIES = 'ted@50.35.80.74:/media/chrome_binaries/'
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

  def __init__(self, cli, hash_value):
    self.cli = cli
    self._setupOs(hash_value)

  def _setupOs(self, hash_value):
    if self.cli.os == 'linux':
      self.binary = f'{hash_value}.zip'
      self.packager = f'{TOOLS}/tools/package.linux.py --package {self.binary}'
      self.build = 'ninja -C out/Release chrome -j2000'
    elif self.cli.os == 'win':
      self.binary = f'{hash_value}_mini_installer.exe'
      self.packager = f'mv out/Windows/mini_installer.exe {self.binary}'
      self.build = 'ninja -C out/Windows mini_installer -j2000'
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
    opts.run(f'scp {patch} {PATCH_SERVICE}')
    opts.run(f'rm {opts.binary} {patch} {metadata}')


def main():
  cli = CommandLineArgs(sys.argv[1:])
  if cli.help:
    return CommandLineArgs.PrintHelp()

  hash_value, patchfile = GenerateDiffAndHash()
  if ApiInterfaces.BuildExists(hash_value) and not cli.force:
    print(cli)
    print('Build exists! not re-packaging')
    return

  opts = ToolOptions(cli, hash_value)

  opts.log(cli)
  opts.log('Starting build')
  opts.run(opts.build)
  opts.log('Packaging')
  opts.run(opts.packager)
  opts.log('Collecting metadata')
  metadata = ApiInterfaces.GenerateMetadataFile(
    hash_value, opts.binary, cli.notes)
  ApiInterfaces.UploadFiles(opts, metadata, patchfile)
  opts.log('Done.')


if __name__ == '__main__':
  main()
