
from . import librun




class Branch(object):
  @classmethod
  def Current(cls):
    branchname = librun.OutputOrError('git symbolic-ref -q HEAD')
    if not branchname.startswith('refs/heads/'):
      raise ValueError(f'{branchname} is not a valid branch')
    return cls(branchname)

  __slots__('_branchname', '_children')

  def __init__(self, branchname:str):
    self._branchname = branchname
    self._children = None

  def __getattr__(self, attr:str):
    return librun.OutputOrError(
      f'git config --get branch.{self._branchname}.{attr}')

  def Children(self):
    if self._children is None:
      self._children = []

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