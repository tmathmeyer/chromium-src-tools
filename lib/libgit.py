
from . import librun

class Branch(object):
  def __init__(self, branchname=None):
    if not branchname:
      self._branchname = librun.OutputOrError('git symbolic-ref -q HEAD')
      if not self._branchname.startswith('refs/heads/'):
        raise ValueError(f'{self._branchname} is not a valid branch')
      self._branchname = self._branchname[11:]
    else:
      self._branchname = branchname

  def __getattr__(self, attr):
    return librun.OutputOrError(
      f'git config --get branch.{self._branchname}.{attr}')

  def Parent(self):
    parent = librun.OutputOrError(
      f'git rev-parse --abbrev-ref {self._branchname}@{{u}}')
    return Branch(parent)

  def GetUpstreamBranch(self):
    return librun.OutputOrError(
      f'git rev-parse --abbrev-ref {self._branchname}@{{u}}')
  
  def GetAheadBehind(self):
    return self.AheadBehindBranch(self.GetUpstreamBranch())

  def AheadBehindBranch(self, branch):
    values = librun.OutputOrError(f'''git rev-list --left-right \
      {self._branchname}...{branch} --count''')
    values = values.split()
    return int(values[0]), int(values[1])

  def AheadBehindMaster(self):
    return self.AheadBehindBranch('master')

  def GetFilesChanged(self):
    #TODO fix this doesn't work with constructed branch names
    ahead = self.GetAheadBehind()[0]
    if not ahead:
      raise ValueError('No files changed between this branch and master')
    return librun.OutputOrError(
      f'git diff --name-only HEAD HEAD~{ahead}').split('\n')

  def GetName(self):
    return self._branchname

  @classmethod
  def ConfigFor(clz, branchname, attr):
    return librun.OutputOrError(f'git config --get branch.{branchname}.{attr}')