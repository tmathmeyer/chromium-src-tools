#!/usr/bin/env python3

import sys
from lib import libargs, librun, libgerrit, libgit, liboutput, colors

COMMAND = libargs.ArgumentParser()

@COMMAND
def up():
  current = libgit.Branch.Current()
  if librun.RunCommand(f'git checkout {current.Parent().Name()}').returncode:
    print('CHECKED OUT PARENT')


@COMMAND
def down():
  pass


if __name__ == '__main__':
  COMMAND.eval()
