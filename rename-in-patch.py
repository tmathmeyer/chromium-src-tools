#!/usr/bin/env python3

from lib import colors, libargs, librun, libgit

COMMAND = libargs.ArgumentParser()

@COMMAND
def run(pattern:str, replace:str=None):
  if '/' in pattern or (replace is not None and '/' in replace):
    raise ValueError('No slashes in pattern or replace!')

  if replace is not None:
    cmd = f"sed -i 's/{pattern}/{replace}/g'"
  else:
    cmd = f"grep --color=always {pattern}"
  
  branch = libgit.Branch.Current()
  for x in branch.GetFilesChanged():
    with_arg = f"{cmd} {x}"
    result = librun.RunCommand(with_arg)
    if result.returncode:
      print(f'{colors.Color(colors.RED)}${with_arg}{colors.Color()}')
    else:
      print(f'{colors.Color(colors.GREEN)}{with_arg}{colors.Color()}')
      if replace is None:
        print(result.stdout)

if __name__ == '__main__':
  COMMAND.eval()
