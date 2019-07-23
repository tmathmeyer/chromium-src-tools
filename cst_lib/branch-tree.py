
import collections
from enum import Enum
import re
from typing import Callable, Dict, Generic, Iterable, TypeVar

from . import runner


BRANCH_NAME = re.compile(
  r'^(\S)?\s*(\S+)\s*\S*\s*(\(.*\)\s*)*(\[(\S*):\s*(.*)\])*(.*)$')


class ItrOrder(Enum):
  POSTFIX = 1
  PREFIX = 2

T = TypeVar('T')
class Branch(Generic[T], collections.namedtuple('Branch', [
  'name', 'parent', 'children', 'checked_out'])):

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
    parent = all_branches.get(self.parent[0], None)
    if parent:
      parent.children.append(self)
      self.parent[0] = parent

  def TreeItr(self, fn:Callable[['Branch', int], T]=lambda b,_:b,
                    order:ItrOrder=ItrOrder.PREFIX,
                    depth:int=0) -> Iterable[T]:
    value = fn(self, depth)
    if order == ItrOrder.PREFIX:
      yield value
    for child in self.children:
      yield from child.TreeItr(fn, order=order, depth=depth+1)
    if order == ItrOrder.POSTFIX:
      yield value

  @classmethod
  def Parse(cls, line:str) -> 'Branch':
    checked_out, name, _, _, parent, _, _ = BRANCH_NAME.search(line).groups()
    return cls(name or 'master', [parent], [], checked_out)


  @classmethod
  def ReadGitRepo(cls) -> Dict[str, 'Branch']:
    branches = {}
    for line in runner.RunSimple('git branch -vv').splitlines():
      b = cls.Parse(line)
      branches[b.name] = b
    for branch in branches.values():
      branch.reparent(branches)
    return branches
