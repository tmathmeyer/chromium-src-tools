#!/usr/bin/env python3

import sys
from lib import libargs

COMMAND = libargs.ArgumentParser()

@COMMAND
def run(commit:str):
  commit_no = 0
  try:
    commit_no = int(commit)
    commit = f'https://chromium-review.googlesource.com/c/chromium/src/+/{commit_no}'
  except:
    commit_no = re.search('[0-9]*$', url).group(0)

  




if __name__ == '__main__':
  COMMAND.eval()