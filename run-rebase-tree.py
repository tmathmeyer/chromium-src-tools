#!/usr/bin/env python3

from collections import namedtuple
import queue
import threading

from lib import libcurses
from lib import libgit
from lib import librun


class RebaseTask(namedtuple('RebaseTask', ['branch', 'view'])):
  def Run(self):
    if self.branch.Name() == 'main':
      self.view.SetContentColor('GREEN')
      self.view.Repaint()
      return None
    branch_behind = self.branch.GetAheadBehind()[1]
    if branch_behind == 0:
      self.view.SetContentColor('GREEN')
      self.view.Repaint()
      return None
    else:
      self.view.SetContentColor('YELLOW')
      self.view.Repaint()

    self.view.SetContent(f'{self.branch.Name()}: Checkout')
    self.view.Repaint()
    if librun.RunCommand(f'git checkout {self.branch.Name()}').returncode:
      self.view.SetContentColor('RED')
      self.view.Repaint()
      return self.branch.Name()

    self.view.SetContent(f'{self.branch.Name()}: rebasing forward {branch_behind} commits')
    self.view.Repaint()
    if librun.RunCommand('git rebase').returncode or self.current_branch_dirty():
      self.view.SetContentColor('RED')
      self.cleanup()
      self.view.Repaint()
      return self.branch.Name()

    '''
    self.view.SetContent(f'{self.branch.Name()}: gclient sync')
    self.view.Repaint()
    if librun.RunCommand('gclient --sync').returncode:
      self.view.SetContentColor('RED')
      self.cleanup()
      self.view.Repaint()
      return self.branch.Name()
    '''

    self.view.SetContent(f'{self.branch.Name()}: Finished')
    self.view.SetContentColor('GREEN')
    self.view.Repaint()
    return None

  def current_branch_dirty(self):
    status = librun.RunCommand('git status --porcelain')
    return bool(status.returncode or status.stdout or status.stderr)

  def cleanup(self):
    librun.RunCommand('git rebase --abort')
    if not self.current_branch_dirty():
      return
    librun.RunCommand('git clean -f -d')
    if not self.current_branch_dirty():
      return
    librun.RunCommand('git checkout main')
    if not self.current_branch_dirty():
      return
    librun.RunCommand('git reset --hard main')
    if not self.current_branch_dirty():
      return


class StopTask():
  def Run(self):
    libcurses.SendKillKey()


def CreateViewFromBranch(branch, taskQueue):
  panel = TreeViewPanel(branch.Name())
  taskQueue.put(RebaseTask(branch, panel))
  for child in branch.Children():
    panel.AddComponent(CreateViewFromBranch(child, taskQueue))
  return panel


def CreateGitBranchTree(taskQueue):
  return CreateViewFromBranch(libgit.Branch.Get('main'), taskQueue)


class TreeViewLayout(libcurses.Layout):
  def Render(self, graphics, components):
    pushdown = 1
    for idx, component in enumerate(components):
      tree = "├"
      if idx == len(components) - 1:
        tree = "└"
      graphics.WriteString(0, pushdown, f"{tree}")
      for i in range(component.GetHeight()-1):
        graphics.WriteString(0, pushdown+i+1, '│')

      component.PaintComponent(
        graphics.GetChild(1, pushdown, graphics.Width()-1, graphics.Height()-pushdown))
      pushdown += component.GetHeight()


class TreeViewPanel(libcurses.Panel):
  def __init__(self, content):
    super().__init__(TreeViewLayout())
    self._erase_content_len = 0
    self._content = content
    self._color = None

  def PaintComponent(self, graphics):
    super().PaintComponent(graphics)
    graphics.SetForground(self._color)
    graphics.WriteString(0, 0, ' ' * self._erase_content_len)
    graphics.WriteString(0, 0, self._content)
    graphics.SetForground(None)

  def SetContent(self, content):
    self._erase_content_len = len(self._content)
    self._content = content

  def GetHeight(self):
    return 1 + sum(c.GetHeight() for c in self._children)

  def SetContentColor(self, color):
    self._color = color


def RebasePump(taskQueue, fails):
  while not taskQueue.empty():
    if failure := taskQueue.get().Run():
      fails.append(failure)


if __name__ == '__main__':
  libcurses.SetKillKey(113)
  term = libcurses.Terminal(libcurses.RowLayout())
  taskQueue = queue.Queue()
  term.AddComponent(CreateGitBranchTree(taskQueue))
  taskQueue.put(StopTask())
  fails = []
  rebase_thread = threading.Thread(target=RebasePump, args=(taskQueue, fails))
  rebase_thread.start()
  term.Start()
  rebase_thread.join()
  print(f'Failed branches: {fails}')
