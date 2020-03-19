#!/usr/bin/env python3

import sys
import threading

from lib import librun
from lib import libgitbranch
from lib import liboutput
from lib import libpyterm as UI


class ExitMsgError(Exception):
  def __init__(self, msg, err):
    super().__init__()
    self.message = msg
    self.error = err


def exit_msg(msg):
  raise ExitMsgError(msg, 1)


def ensure_git():
  if librun.RunCommand('git branch --show-current').returncode:
    exit_msg('Not in a git repository')


def current_branch_dirty():
  status = librun.RunCommand('git status --porcelain')
  return bool(status.returncode or status.stdout or status.stderr)


def clean_rebase():
  if librun.RunCommand('git rebase --abort').returncode:
    exit_msg('failed to abort rebase')
  if librun.RunCommand('git clean -f -d').returncode:
    exit_msg('failed to clean directory')
  if not current_branch_dirty():
    return
  if librun.RunCommand('git checkout master').returncode:
    exit_msg('failed to switch back to master branch')
  if current_branch_dirty():
    exit_msg('failed to clean branch, please procede manually')


def reparent_branches(upstream, unparented):
  for branch in unparented:
    print(f'reparenting {branch.name}')
    checkout = f'git checkout {branch.name}'
    reparent = f'git branch --set-upstream-to={upstream.name}'
    if librun.RunCommand(checkout).returncode:
      print(f'could not checkout {branch.name}')
      continue
    if librun.RunCommand(reparent).returncode:
      exit_msg(f'could not set branch upstream to {upstream.name}')

def rebase_children(branch, repaint):
  branch.data['rebase_status'] = 'Good'
  repaint()
  for child in branch.children:
    rebase_branch(child, repaint)

def rebase_branch(branch, repaint):
  if '--force-rebase' not in sys.argv:
    if branch.getBehind() == 0:
      rebase_children(branch, repaint)
      return

  if branch.data.get('rebase_status', None) != None:
    exit_msg('rebase encountered strange issue')
  branch.data['rebase_status'] = 'Progress'
  repaint()

  if librun.RunCommand(f'git checkout {branch.name}').returncode:
    branch.data['rebase_status'] = 'Bad'
    repaint()
    return False

  if librun.RunCommand('git rebase').returncode or current_branch_dirty():
    branch.data['rebase_status'] = 'Bad'
    clean_rebase()
    repaint()
    return False

  rebase_children(branch, repaint)


def reparent_and_get_master(branches):
  upstream_mirror = None
  unparented_branches = set()
  for name, branch in branches.items():
    if branch.parent == 'origin/master':
      upstream_mirror = branch
    elif branch.parent == None and branch.name != 'trash':
      unparented_branches.add(branch)
  if not upstream_mirror:
    exit_msg('no local branch has upstream origin/master')
  reparent_branches(upstream_mirror, unparented_branches)
  return upstream_mirror


def rebase_pump(master, repaint):
  for child_of_master in master.children:
    rebase_branch(child_of_master, repaint)


class Context(object):
  __slots__ = ('colors', 'terminal', 'tree', 'color_free')
  def __init__(self, tree, color_free=False):
    self.colors = None
    self.terminal = None
    self.tree = tree
    self.color_free = color_free


class TreeView(UI.NormalWindow):
  def __init__(self):
    super().__init__()
    self.thread = None

  def colorize(self, context):
    def lam(branch):
      GREEN = 'GREEN'
      BLACK = 'BLACK'
      RED = 'RED'
      MAGENTA = 'MAGENTA'
      YELLOW = 'YELLOW'
      if context.color_free:
        BLACK = 'WHITE'
      if branch.data.get('rebase_status', None) == 'Good':
        return context.colors.GetColor(GREEN, BLACK)
      if branch.data.get('rebase_status', None) == 'Bad':
        return context.colors.GetColor(RED, BLACK)
      if branch.data.get('rebase_status', None) == 'Progress':
        return context.colors.GetColor(MAGENTA, BLACK)
      return context.colors.GetColor(YELLOW, BLACK)
    return lam

  def FormatBranch(self, branch):
    return f'{branch.name}'

  def RebaseTree(self, context):
    rebase_pump(context.tree, lambda: context.terminal.PaintWindow(self))

  def Repaint(self, context):
    if self.thread == None:
      self.thread = threading.Thread(target=self.RebaseTree, args=(context,))
      self.thread.start()

    liboutput.RenderOnNCurses(self, liboutput.PrintTree, self.colorize(context),
      context.tree, render=self.FormatBranch, charset=liboutput.ASCII_ONLY)


def main():
  windows = [('...', '...', TreeView)]
  branches = libgitbranch.Branch.ReadGitRepo()
  master = reparent_and_get_master(branches)
  master.data["rebase_status"] = 'Good'

  with UI.Terminal(windows, Context(master, color_free=True)) as c:
    c.Start()
    c.WaitUntilEnded()


if __name__ == '__main__':
  try:
    ensure_git()
    main()
  except ExitMsgError as e:
    print(e.message, file=sys.stderr)
    sys.exit(e.error)
