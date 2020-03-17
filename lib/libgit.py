
from . import librun

def _ErrorOr(cmd):
  print(cmd)
  result = librun.RunCommand(cmd)
  if result.returncode:
    raise ValueError(f'|{cmd}|:\n {result.stderr}')
  return result.stdout.strip()

class Branch(object):
  def __init__(self):
    self._branchname = _ErrorOr('git symbolic-ref -q HEAD')
    if not self._branchname.startswith('refs/heads/'):
      raise ValueError(f'{self._branchname} is not a valid branch')
    self._branchname = self._branchname[11:]

  def GetUpstreamBranch(self):
    return _ErrorOr(
      f'git rev-parse --abbrev-ref {self._branchname}@{{u}}')
  
  def GetAheadBehind(self):
    values = _ErrorOr(f'''git rev-list --left-right \
      {self._branchname}...{self.GetUpstreamBranch()} --count''')
    values = values.split()
    return int(values[0]), int(values[1])

  def GetFilesChanged(self):
    ahead = self.GetAheadBehind()[0]
    if not ahead:
      raise ValueError('No files changed between this branch and master')
    return _ErrorOr(f'git diff --name-only HEAD HEAD~{ahead}').split('\n')
