
from . import librun

class Branch(object):
  @classmethod
  def Current(cls):
    branchname = librun.OutputOrError('git symbolic-ref -q HEAD')
    if not branchname.startswith('refs/heads/'):
      raise ValueError(f'{branchname} is not a valid branch')
    return cls.Get(branchname[11:])

  @classmethod
  def Get(cls, branchname):
    if not hasattr(cls, '__cache'):
      setattr(cls, '__cache', {})
    cache = getattr(cls, '__cache')
    if branchname in cache:
      return cache[branchname]
    branch = cls(branchname)
    cache[branchname] = branch
    return branch

  @classmethod
  def GetAllBranches(cls):
    branches = librun.OutputOrError(
      'git branch --format "%(refname:short)"').split('\n')
    for branch in branches:
      yield cls.Get(branch)

  @classmethod
  def Default(cls):
    default_name = librun.OutputOrError(
      'git symbolic-ref refs/remotes/origin/HEAD')
    return cls.Get(default_name[20:])

  __slots__ = ('_branchname', '_children')

  def __init__(self, branchname:str):
    self._branchname = branchname
    self._children = None

  def __getattr__(self, attr:str):
    return librun.OutputOrError(
      f'git config --get branch.{self._branchname}.{attr}')

  def Name(self):
    return self._branchname

  def Children(self):
    if self._children is None:
      self._children = []
      for branch in Branch.GetAllBranches():
        if branch.Parent() and branch.Parent().Name() == self.Name():
          self._children.append(branch)
    return self._children

  def Parent(self):
    try:
      parent = librun.OutputOrError(
        f'git rev-parse --abbrev-ref {self._branchname}@{{u}}')
      return Branch.Get(parent)
    except ValueError:
      if self.Name() == 'heads/origin/main':
        return None
      return Branch.Default()
  
  def GetAheadBehind(self):
    return self.AheadBehindBranch(self.Parent().Name())

  def AheadBehindBranch(self, branch:str):
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