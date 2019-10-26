#!/usr/local/bin/python3.8

import sys

from cst_lib import runner, branch_tree


CURRENT_BRANCH = None
YES_VALUES = ('Y', 'y', 'yes', 'Yes')

def setup():
  global CURRENT_BRANCH
  CURRENT_BRANCH = runner.RunSimple('git branch --show-current')
  if not CURRENT_BRANCH:
    raise ValueError('Not in a git repository')


def ask_rebase(branch, *_,):
  if branch.name == 'master':
    return branch
  if branch.checked_out == '+':
    print(f"\"{branch.name}\" is checked out in a different virtual repo. You must rebase there instead.")
    return None
  if input(f'Would you like to rebase {branch.name}? [y/N]') in YES_VALUES:
    return branch
  return None


def main():
  # These commands are non-destructive, so run them regardless
  setup()
  master = branch_tree.Branch.ReadGitRepo().get('master', None)
  if not master:
    raise ValueError('No master branch!')

  for branch in master.TreeItr(fn=ask_rebase, skip_subtrees_on_empty_ret=True):
    if branch.name == 'master':
      continue
    runner.RunSimple(f'git checkout {branch.name}')
    runner.RunSimple(f'git rebase')
    usr = 'N'
    while usr not in YES_VALUES:
      usr = input('Rebase completed? [y/N]: ')
  runner.RunSimple(f'git checkout {CURRENT_BRANCH}')

if __name__ == '__main__':
  main()