#!/usr/bin/env python3

import sys
import re
import os
from lib import librun

def SymbolizeLinez(file):
  matcher = r'#\d+ 0x[a-f0-9]+  \(([\/A-Za-z\.0-8\-_]+)\.so\+0x([a-f0-9]+).+'
  with open(file) as f:
    for line in f.readlines():
      while line and line[-1] == '\n':
        line = line[:-1]
      m = re.match(matcher, line.strip())
      if not m:
        print(line)
        continue
      file, address = m.groups()
      value = librun.OutputOrError(f'addr2line -e {file}.so 0x{address}')
      repl = f'{file}.so+0x{address}'
      line = line.replace(repl, value)
      print(f'    {os.path.basename(value)}')
      #while line and line[-1] == '\n':
      #  line = line[:-1]
      #print(line)


if __name__ == '__main__':
  SymbolizeLinez(sys.argv[1])
