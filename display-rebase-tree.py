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


def disp_branch(highlight):
  def _inner(branch):
    color = ''
    try:
      issue_number = getattr(branch, 'gerritissue', '')
    except:
      issue_number = None

    suffix = ''
    if issue_number:
      status = get_branch_status(issue_number)
      suffix = f' [https://crrev.com/c/{issue_number}] {status}'

    branch_ahead, branch_behind = branch.GetAheadBehind()

    prefix = f' ↑{branch_ahead} ↓{branch_behind}'
    if (branch.Name() == 'master'):
      prefix = ''

    if highlight == 'branch.current':
      if branch.Name() == CURRENT_BRANCH.stdout.strip():
        color += colors.Color(colors.GREEN)

    if highlight == 'branch.merged':
      if suffix.endswith('<MERGED>'):
        color += colors.Color(colors.GREEN)

    parent = branch.Parent()
    if type(parent) != str:
      parent = parent.Name()
    else:
      parent = 'UNKNOWN'
    return f' {color}{branch.Name()} ({parent}){prefix}{suffix}{colors.Color()}'

  return _inner


@COMMAND
def print_tree(highlight:str='branch.current'):
  if highlight == 'help':
    display_help()
    return

  setup()
  master = libgit.Branch.Get('master')
  export = ['']

  def _print_to_buffer(s, _, capture=export):
    capture[0] += f'{s}\n'

  liboutput.PrintTree(master, render=disp_branch(highlight=highlight),
                      charset=liboutput.BOLD_BOX_CHARACTERS,
                      output_function=_print_to_buffer,
                      child_iterator=lambda b:b.Children())
  print(export[0])


if __name__ == '__main__':
  COMMAND.eval()
