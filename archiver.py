
import os
import sys
import tempfile
from datetime import datetime
from lib import libgit, librun, libjson


PKG_SCRIPT = '/media/chromium/chromium-src-tools/tools/package.linux.py'
BINARIES = 'ted@192.168.1.230:/media/chrome_binaries/'
DATA_SERVICE = 'ted@tedm.io:/var/www/binary_builds/hashes/'
PATCH_SERVICE = 'ted@tedm.io:/var/www/binary_builds/patches/'


def CollectIssues(branch):
  if branch.GetName() == 'master':
    return []
  try:
    crrev = getattr(branch, 'gerritissue', '')
  except:
    crrev = None
  chain = CollectIssues(branch.Parent())
  if crrev:
    return [crrev] + chain
  return chain


def CalculateFromRepo(git_path):
  with librun.cd(git_path):
    branch = libgit.Branch()
    ahead, behind = branch.AheadBehindMaster()

    if behind != 0:
      raise ValueError(f'Branch {branch} is not rebased on top of master')

    fd, patchfile = tempfile.mkstemp()
    os.close(fd)
    os.system(f'git diff master {branch.GetName()} >> {patchfile}')
    print(patchfile)
    md5 = librun.OutputOrError(f'md5sum {patchfile}').split()[0]

    return md5, patchfile, CollectIssues(branch)

class Archive(object):
  __slots__ = ('build_date', 'hash', 'patch_file', 'revisions', 'gitpath')

  def __init__(self, git_path):
    self.gitpath = git_path
    self.build_date = str(datetime.now())
    self.hash, self.patch_file, self.revisions = CalculateFromRepo(git_path)

  def BuildExists(self):
    json = libjson.JSON.FromURL('https://archives.tedm.io/hashes')
    return self.hash in json

  def PackageAndUpload(self, notes):
    with librun.cd(self.gitpath):
      librun.OutputOrError('b chrelease')
      print('Done Building')
      librun.OutputOrError(f'{PKG_SCRIPT} --package ../{self.hash}.zip')
      librun.OutputOrError(f'scp ../{self.hash}.zip {BINARIES}')
      librun.OutputOrError(f'rm ../{self.hash}.zip')
      librun.OutputOrError(f'echo "{self.build_date}" >> ../{self.hash}')
      librun.OutputOrError(f'echo "{self.hash}" >> ../{self.hash}')
      librun.OutputOrError(f'echo "{self.revisions}" >> ../{self.hash}')
      if notes is not None:
        librun.OutputOrError(f'echo "{notes}" >> ../{self.hash}')
      librun.OutputOrError(f'scp ../{self.hash} {DATA_SERVICE}')
      librun.OutputOrError(f'rm ../{self.hash}')
      librun.OutputOrError(f'scp {self.patch_file} {PATCH_SERVICE}/{self.hash}')


def main():
  a = Archive('/media/chromium/chromium-git/src')
  if not a.BuildExists() or '--force' in sys.argv:
    notes = None
    if '--notes' in sys.argv:
      notes = sys.argv[sys.argv.index('--notes') + 1]
    a.PackageAndUpload(notes)
  else:
    print('build already exists!')
  os.system(f'rm {a.patch_file}')


if __name__ == '__main__':
  try:
    main()
  except Exception as e:
    print(str(e))
    sys.exit(1)
