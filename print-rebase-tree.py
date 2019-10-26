#!/usr/local/bin/python3.8

import sys

from lib import librun, libgitbranch


CURRENT_BRANCH = None
YES_VALUES = ('Y', 'y', 'yes', 'Yes')

def setup():
  global CURRENT_BRANCH
  CURRENT_BRANCH = librun.RunCommand('git branch --show-current')
  if CURRENT_BRANCH.returncode:
    raise ValueError('Not in a git repository')


def branch_to_string(branch, i, counts):
  if i == 0:
    return branch.name
  preline = '│ ' * (i - 1)
  if counts.Num == counts.Of:
    preline += '└'
  else:
    preline += '├'
  preline += '─'
  return preline + branch.name


def main():
  # These commands are non-destructive, so run them regardless
  setup()
  master = libgitbranch.Branch.ReadGitRepo().get('master', None)
  if not master:
    raise ValueError('No master branch!')

  for branch in master.TreeItr(fn=branch_to_string, skip_subtrees_on_empty_ret=True):
    print(branch)

if __name__ == '__main__':
  main()