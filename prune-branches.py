#!/usr/bin/env python3

from lib import libargs, librun, libgerrit, libgit, liboutput, colors

RED = colors.Color(colors.RED)
YELLOW = colors.Color(colors.YELLOW)
GREEN = colors.Color(colors.GREEN)
RESET = colors.Color()

def prune_branch(branch, delete_me=True):
  name = branch.Name()
  branch_ahead, branch_behind = branch.GetAheadBehind()
  children = branch.Children()
  if branch_ahead == 0 and branch_behind == 0 and delete_me:
    print(f'{YELLOW}Deleting: {name}{RESET}')
    if librun.RunCommand(f'git branch -D {name}').returncode:
      print(f'  {RED}* Failed to delete branch{RESET}')
      return
    elif len(children):
      print(f'  {YELLOW}Updating children:{RESET}')
      pname = branch.Parent().Name()
      cmd='--set-upstream-to'
      for c in children:
        if librun.RunCommand(f'git branch {cmd}={pname} {c.Name()}'):
          print(f'    {RED}* Failed set {c.Name()} upstream to {pname}{RESET}')
        else:
          print(f'    {GREEN} Removed {name} from {c.Name()}\'s tree{RESET}')

  for c in children:
    prune_branch(libgit.Branch.Get(c.Name()))


def prune():
  librun.RunCommand(f'git checkout main')
  prune_branch(libgit.Branch.Get('main'), False)

if __name__ == '__main__':
  prune()
