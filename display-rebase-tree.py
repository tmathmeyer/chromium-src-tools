#!/usr/bin/env python3

import sys

from lib import libargs, librun, libgerrit, libgit, liboutput, colors


CURRENT_BRANCH = None
COMMAND = libargs.ArgumentParser()


def setup():
  global CURRENT_BRANCH
  CURRENT_BRANCH = librun.RunCommand('git branch --show-current')
  if CURRENT_BRANCH.returncode:
    raise ValueError('Not in a git repository')


def display_help():
  print('highlight options:')
  print('  branch.current')
  print('  branch.merged')


def get_branch_status(issue_number):
  return f'<{libgerrit.GetReviewDetail(issue_number).status}>'


def disp_branch(highlight, nogerrit, quick):
  def _inner(branch):
    color = ''

    if highlight == 'branch.current':
      if branch.Name() == CURRENT_BRANCH.stdout.strip():
        color += colors.Color(colors.GREEN)

    if highlight == 'branch.merged':
      if suffix.endswith('<MERGED>'):
        color += colors.Color(colors.RED)

    if quick:
      return f'  {color}{branch.Name()}{colors.Color()}'

    parent = branch.Parent()
    if type(parent) != str:
      parent = parent.Name()
    else:
      parent = 'UNKNOWN'

    issue_number = None
    if not nogerrit:
      try:
        issue_number = getattr(branch, 'gerritissue', '')
      except:
        pass

    suffix = ''
    if issue_number:
      status = get_branch_status(issue_number)
      suffix = f' [https://crrev.com/c/{issue_number}] {status}'

    branch_ahead, branch_behind = branch.GetAheadBehind()

    prefix = f' ↑{branch_ahead} ↓{branch_behind}'
    if (branch.Name() == 'main'):
      prefix = ''
    return f' {color}{branch.Name()} ({parent}){prefix}{suffix}{colors.Color()}'

  return _inner


@COMMAND
def print_tree(highlight:str='branch.current',
               nogerrit:bool=False,
               quick:bool=False):
  if highlight == 'help':
    display_help()
    return

  setup()
  main = libgit.Branch.Get('main')
  export = ['']

  def _print_to_buffer(s, _, capture=export):
    capture[0] += f'{s}\n'

  liboutput.PrintTree(main,
    render=disp_branch(highlight=highlight, nogerrit=nogerrit, quick=quick),
    charset=liboutput.BOLD_BOX_CHARACTERS,
    output_function=_print_to_buffer,
    child_iterator=lambda b:b.Children())
  print(export[0])


if __name__ == '__main__':
  COMMAND.eval()
