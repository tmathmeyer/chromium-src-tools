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


def GenerateDiffAndHash():
  branch = libgit.Branch.Current()
  ahead, behind = branch.AheadBehindMaster












if __name__ == '__main__':
  print(CollectIssues(libgit.Branch.Current()))



def CalculateFromRepo(git_path):
  with librun.cd(git_path):
    branch = libgit.Branch.Current()
    ahead, behind = branch.AheadBehindMaster()

    if behind != 0:
      raise ValueError(f'Branch {branch} is not rebased on top of master')

    fd, patchfile = tempfile.mkstemp()
    os.close(fd)
    os.system(f'git diff main {branch.Name()} >> {patchfile}')
    print(patchfile)
    md5 = librun.OutputOrError(f'md5sum {patchfile}').split()[0]

    return md5, patchfile, CollectIssues(branch)


class Options(object):
  __slots__ = ('dry', 'verbose', 'force', 'notes', 'build', 'packager', 'binary')
  def __init__(self, opts):
    self._checkHelp(opts)
    self.verbose = '--debug' in opts
    self.dry = '--wet' not in opts
    self.force = '--force' in opts
    self.notes = None
    if '--notes' in opts:
      self.notes = opts[opts.index('--notes') + 1]

    # Default linux tools and commands
    self.binary = '{hash}.zip' # needs to be formatted
    self.packager = f'{TOOLS}/tools/package.linux.py --package ../{self.binary}'
    self.build = 'ninja -C out/Archive chrome -j1000'
    self.determineOS(opts)

  def _checkHelp(self, opts):
    if '--help' in opts:
      print('usage:')
      print('  --debug: enable verbose debug logging')
      print('  --wet: dry run by default, this enables actual building and archiving')
      print('  --force: force upload even if there is already a patch')
      print('  --notes "note content": add notes that appear on the web ui')
      print('  --os [win / linux]: build for windows or for linux')
      raise 0

  def useHash(self, h):
    self.binary = self.binary.format(hash=h)
    self.packager = self.packager.format(hash=h)

  def determineOS(self, opts):
    try:
      os = opts[opts.index('--os')+1]
      if os == 'win':
        self.build = 'ninja -C out/Windows mini_installer -j60'
        self.binary = '{hash}_mini_installer.exe'
        self.packager = f'mv out/Windows/mini_installer.exe ../{self.binary}'
      elif os == 'linux':
        pass
      else:
        self.vlog(f'OS <{os}> unknown')
    except ValueError as e:
      pass

  def vlog(self, *args, **kwargs):
    if not self.verbose:
      return
    for arg in args:
      print(arg)
    for k, v in kwargs.items():
      print(f'{k} = {v}')

  def runOrDry(self, cmd):
    if self.dry:
      print(cmd)
    else:
      librun.OutputOrError(cmd)


class Archive(object):
  __slots__ = ('build_date', 'hash', 'patch_file', 'revisions', 'gitpath')

  def __init__(self, git_path):
    self.gitpath = git_path
    self.build_date = str(datetime.now())
    self.hash, self.patch_file, self.revisions = CalculateFromRepo(git_path)

  def BuildExists(self):
    json = libjson.JSON.FromURL('https://archives.tedm.io/hashes')
    return self.hash in json

  def PackageAndUpload(self, opts):
    with librun.cd(self.gitpath):
      opts.vlog('Starting build: ')
      opts.runOrDry(opts.build)
      opts.vlog('Finished building', 'Packaging:')
      opts.runOrDry(opts.packager)

      package_content = f'{self.build_date}\n{self.hash}\n{self.revisions}'
      package_file = f'../{self.hash}'
      with open(package_file, 'w') as f:
        f.write(f'{self.build_date}\n')
        f.write(f'{self.hash}\n')
        f.write(f'{self.revisions}\n')
        f.write(f'{opts.binary}\n')
        if opts.notes:
          f.write(f'{opts.notes}\n')

      opts.vlog('done packaging', 'Uploading:')
      opts.runOrDry(f'scp ../{opts.binary} {BINARIES}')
      opts.runOrDry(f'scp {package_file} {DATA_SERVICE}')
      opts.runOrDry(f'scp {self.patch_file} {PATCH_SERVICE}/{self.hash}')

      opts.vlog('Done uploading', 'Cleaning up')
      opts.runOrDry(f'rm ../{opts.binary}')
      opts.runOrDry(f'rm {self.patch_file}')
      opts.runOrDry(f'rm {package_file}')

      opts.vlog('Done')


'''
def main(opts):
  a = Archive('/chromium/chromium-git/src')
  if not a.BuildExists() or opts.force:
    opts.useHash(a.hash)
    a.PackageAndUpload(opts)
  else:
    print(f'build already exists! (hash: {a.hash})')


if __name__ == '__main__':
  try:
    main(Options(sys.argv))
  except Exception as e:
    raise
    print(str(e))
    sys.exit(1)
'''
