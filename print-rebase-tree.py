#!/usr/local/bin/python3.8

import sys

from lib import librun, libgitbranch, liboutput, colors


CURRENT_BRANCH = None
YES_VALUES = ('Y', 'y', 'yes', 'Yes')

def setup():
  global CURRENT_BRANCH
  CURRENT_BRANCH = librun.RunCommand('git branch --show-current')
  if CURRENT_BRANCH.returncode:
    raise ValueError('Not in a git repository')

def disp_branch(branch):
  result = ''
  if branch.checked_out:
    result += colors.Color(colors.GREEN)

  if branch.getAhead() == 0:
    result += colors.Color(colors.PURPLE)

  gerrit = getattr(branch, 'gerritissue', '')
  result += branch.name
  result += f' [{gerrit}]'

  result += colors.Color()
  return result


def main():
  # These commands are non-destructive, so run them regardless
  setup()
  master = libgitbranch.Branch.ReadGitRepo().get('master', None)
  liboutput.PrintTree(
    master, render=disp_branch, charset=liboutput.BOLD_BOX_CHARACTERS)

if __name__ == '__main__':
  main()