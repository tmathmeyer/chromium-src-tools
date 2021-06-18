
import collections
from enum import Enum
import re
from typing import Callable, Dict, Generic, Iterable, TypeVar

from . import librun


class ItrOrder(Enum):
  POSTFIX = 1
  PREFIX = 2


class BranchIndex(collections.namedtuple('BranchIndex', ['Num', 'Of'])):
  pass


X = TypeVar('X')
class Box(Generic[X]):
  def __init__(self, value: X):
    self._value = value

  def get(self) -> X:
    return self._value

  def set(self, value: X) -> X:
    old = self._value
    self._value = value
    return old

  def __bool__(self):
    return bool(self._value)

  def __repr__(self):
    return repr(self._value)

  def __str__(self):
    return str(self._value)

  def __eq__(self, o):
    return o == self._value


T = TypeVar('T')
class Branch(Generic[T], collections.namedtuple('Branch', [
  'name', 'parent', 'children', 'checked_out', 'data'])):

  def __hash__(self) -> str:
    return hash(self.name)

  def __eq__(self, other:'Branch') -> bool:
    return type(other) == Branch and other.name == self.name

  def __add__(self, other:'Branch') -> 'Branch':
    if other == self:
      return Branch(self.name,
        self.parent or other.parent,
        self.children | other.children)
    raise ValueError(
      "Can't add type {} to instance of class Branch".format(type(other)))

  def __iadd__(self, other:'Branch'):
    if other == self:
      self.parent = self.parent or other.parent
      self.children |= other.children
    raise ValueError(
      "Can't add type {} to instance of class Branch".format(type(other)))

  def reparent(self, all_branches):
    if self.parent.get() == self.name:
      return
    parent = all_branches.get(self.parent.get(), None)
    if parent:
      parent.children.append(self)
      self.parent.set(parent)

  def getAhead(self):
    return self._getAheadBehind().ahead

  def getBehind(self):
    return self._getAheadBehind().behind

  def _getAheadBehind(self):
    AheadBehind = collections.namedtuple('AheadBehind', ['ahead', 'behind'])
    if not self.parent:
      return AheadBehind(-1, -1)
    if not hasattr(self.parent.get(), 'name'):
      return AheadBehind(-2, -2)
    r = librun.RunCommand(
      f'git rev-list --left-right {self.name}...{self.parent.get().name} --count')
    if r.returncode:
      return AheadBehind(r.stderr, r.stdout)
    result = r.stdout.split()
    return AheadBehind(int(result[0]), int(result[1]))

  def TreeItr(self, fn:Callable[['Branch', int, BranchIndex], T]=lambda b,_:b,
                    order:ItrOrder=ItrOrder.PREFIX,
                    skip_subtrees_on_empty_ret:bool=False,
                    depth:int=0,
                    idx:BranchIndex=BranchIndex(1, 1)) -> Iterable[T]:
    value = fn(self, depth, idx)
    if value is None and skip_subtrees_on_empty_ret:
      return
    if order == ItrOrder.PREFIX:
      yield value
    for i, child in enumerate(self.children):
      yield from child.TreeItr(
        fn=fn, order=order, depth=depth+1,
        skip_subtrees_on_empty_ret=skip_subtrees_on_empty_ret,
        idx=BranchIndex(i+1, len(self.children)))
    if order == ItrOrder.POSTFIX:
      yield value

  def __getattr__(self, attr):
    r = librun.RunCommand(f'git config --get branch.{self.name}.{attr}')
    if r.returncode:
      raise AttributeError()
    return r.stdout.strip()

  @classmethod
  def Parse(cls, line:str) -> 'Branch':
    name, parent = line.split('~')
    return cls(name, Box(parent or 'master'), [], False, {})


  @classmethod
  def ReadGitRepo(cls) -> Dict[str, 'Branch']:
    branches = {}
    r = librun.RunCommand(
      'git branch --format "%(refname:short)~%(upstream:short)"')
    if r.returncode:
      return branches
    for line in r.stdout.splitlines():
      b = cls.Parse(line)
      branches[b.name] = b
    for branch in branches.values():
      branch.reparent(branches)
    return branches