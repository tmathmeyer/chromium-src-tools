#!/usr/bin/env python3

import json
import os
import sys

from lib import librun

def get_cache(filename):
  home = os.environ['HOME']
  directory = os.path.join(home, '.cache', 'chromium-src')
  if not os.path.exists(directory):
    os.system(f'mkdir {directory}')
  return os.path.join(directory, filename)


def needs_update(files):
  cache = get_cache('files')
  if not os.path.exists(cache):
    return True
  files = set(files)
  with open(cache) as f:
    try:
      prefiles = set(json.loads(f.read()).keys())
      return len(files - prefiles)
    except:
      return True


def update(files, username):
  with open(get_cache('files'), 'w') as f:
    output = {f:{'user':[], 'bug':[]} for f in files}
    for file in files:
      print(f'blaming {file}')
      output[file]['user'], output[file]['bug'] = blame_file(file, username)
    f.write(json.dumps(output))


def blame_file(filename, searchname):
  buglines = []
  userlines = []
  for blameline in librun.OutputOrError(f'git blame {filename}').split('\n'):
    if f'TODO({searchname})' in blameline:
      userlines.append(blameline)
    elif 'TODO(b/' in blameline:
      buglines.append(blameline)
  return userlines, buglines


def display_todo(file, data):
  if not data['user']:
    return

  print(file)
  for line in data['user']:
    num_cont = line.split('+0000')[1].strip()
    num, cont = num_cont.split(')', 1)
    print(f'  {num}: {cont.strip()}')


def grep_4_todo(username):
  files = librun.OutputOrError('git grep -l TODO').split('\n')
  if needs_update(files):
    update(files, username)
  cache = get_cache('files')
  with open(cache) as f:
    for file, data in json.loads(f.read()).items():
      display_todo(file, data)


if __name__ == '__main__':
  grep_4_todo(sys.argv[1] if len(sys.argv) >= 2 else 'tmathmeyer')