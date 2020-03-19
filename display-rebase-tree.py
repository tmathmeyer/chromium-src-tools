#!/usr/bin/env python3

import sys

from lib import libargs, librun, libgitbranch, liboutput, colors


CURRENT_BRANCH = None
COMMAND = libargs.ArgumentParser()


def setup():
  global CURRENT_BRANCH
  CURRENT_BRANCH = librun.RunCommand('git branch --show-current')
  if CURRENT_BRANCH.returncode:
    raise ValueError('Not in a git repository')


def disp_branch(highlight):
  def _inner(branch):
    result = ''
    gerrit = getattr(branch, 'gerritissue', '')

    if highlight == 'branch.current':
      if branch.name == CURRENT_BRANCH.stdout.strip():
        result += colors.Color(colors.GREEN)
    elif highlight == 'branch.merged':
      if branch.getAhead() == 0 and branch.getBehind() == 0:
        result += colors.Color(colors.GREEN)

    result += branch.name
    if gerrit:
      result += f' [https://crrev.com/c/{gerrit}]'

    return result + colors.Color()
  return _inner


@COMMAND
def print_tree(highlight:str='branch.current'):
  setup()
  master = libgitbranch.Branch.ReadGitRepo().get('master', None)
  export = ['']

  def _print_to_buffer(s, _, capture=export):
    capture[0] += f'{s}\n'

  liboutput.PrintTree(master, render=disp_branch(highlight=highlight),
                      charset=liboutput.BOLD_BOX_CHARACTERS,
                      output_function=_print_to_buffer)
  print(export[0])


if __name__ == '__main__':
  COMMAND.eval()