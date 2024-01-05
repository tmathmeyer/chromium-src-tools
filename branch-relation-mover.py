#!/usr/bin/env python3

import sys
import os
from lib import libargs, librun, libgerrit, libgit, liboutput, colors

COMMAND = libargs.ArgumentParser()

@COMMAND
def up(count:int = 1):
  assert count > 0 or count == -1
  def continue_up(current_branch):
    if count > 0:
      return True
    if count < 0:
      return current_branch.Parent().Name() != 'main'
    return False

  current = libgit.Branch.Current()
  while continue_up(current):
    parent = current.Parent()
    count -= 1
    if not librun.RunCommand(f'git checkout {parent.Name()}').returncode:
      print(f'Checked out {parent.Name()}')
    else:
      print(f'Checking out {parent.Name()} failed')
      return
    current = parent


@COMMAND
def autosquash():
  up(-1)
  while True:
    current = libgit.Branch.Current()
    rebase_count = current.GetAheadBehind()[0]
    count = 1
    print(f'Squashing all commits on {current.Name()}')
    while current.GetAheadBehind()[0] > 1:
      print(f'  rebasing {count} of {rebase_count}')
      upcommit = librun.OutputOrError('git log --pretty=%P -1 HEAD')
      librun.OutputOrError(f'git commit --amend -m "squash! {upcommit}"')
      crange = f'HEAD~{current.GetAheadBehind()[0]}'
      os.environ['GIT_SEQUENCE_EDITOR'] = ':'
      os.environ['GIT_EDITOR'] = ':'
      librun.OutputOrError(f'git rebase --autosquash -i {crange}')
      count += 1

    children = current.Children()
    if len(children) == 0:
      print('Finished!')
      return

    if len(children) != 1:
      print('Multiple child branches! Cant continue the autosquash')
      return

    current = children[0]
    librun.OutputOrError(f'git checkout {current.Name()}')

    print('Rebasing child branch')
    librun.OutputOrError('git rebase')



@COMMAND
def down(name:str = None):
  current = libgit.Branch.Current()
  children = current.Children()
  if len(children) == 0:
    print(f'Branch {current.Name()} has no children')
  elif len(children) == 1:
    branch = children[0]
    if not librun.RunCommand(f'git checkout {branch.Name()}').returncode:
      print(f'Checked out {branch.Name()}')
    else:
      print(f'Checking out {branch.Name()} failed.')
  elif name is None:
    print('Specify a child branch to move to with --name')
  else:
    print('--name not implemented')


@COMMAND
def make_child(name:str):
  current = libgit.Branch.Current()
  if librun.RunCommand(f'git checkout -b {name}').returncode:
    print(f'Could not create branch {name}')
    return
  cmd = f'git branch --set-upstream-to={current.Name()}'
  if librun.RunCommand(cmd).returncode:
    print('Could not set upstream')
    return
  print(f'Set Upstream for {name} to {current.Name()}')


@COMMAND
def insert(name:str):
  current = libgit.Branch.Current()
  children = current.Children()
  if librun.RunCommand(f'git checkout -b {name}').returncode:
    print(f'Could not create branch {name}')
    return
  cmd = f'git branch --set-upstream-to={current.Name()}'
  if librun.RunCommand(cmd).returncode:
    print('Could not set upstream')
    return
  cmd = f'git branch --set-upstream-to={name}'
  for child in children:
    if librun.RunCommand(f'git checkout {child.Name()}').returncode:
      print(f'Could not check out {child.Name()}')
      return
    if librun.RunCommand(cmd).returncode:
      print(f'could not set upstream of {child.Name()} to {name}')
      return
  if librun.RunCommand(f'git checkout {name}').returncode:
    print(f'Could not check out {name}')
    return
  print(f'Injected Branch {name} after {current.Name()}')


if __name__ == '__main__':
  COMMAND.eval()
