
import re
import requests
import json


RPC = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild'
FMT = r'https://ci\.chromium\.org/p/(\S+)/builders/(\S+)/(\S+)/([0-9]+)'
PARSER = re.compile(FMT)

def get_request_payload(url):
  groups = PARSER.match(url).groups()
  return {
    'builder': {
      'project': groups[0],
      'bucket': groups[1],
      'builder': groups[2],
    },
    'buildNumber': groups[3],
    'fields': 'steps,id'
  }

class BuildbotEntries(object):
  def __init__(self, url):
    self._compile_targets = []
    self._gn_args = {}
    q = requests.post(
      url=RPC,
      data=json.dumps(get_request_payload(url)),
      headers={
        'content-type': 'application/json',
        'accept': 'application/json'
      })
    if q.status_code != 200:
      self._json = {}
    else:
      self._json = json.loads(q.text[5:])

  def GetCompileTargets(self):
    if self._compile_targets:
      return self._compile_targets
    for step in self._json.get('steps', []):
      if step['name'] == 'compile (with patch)':
        for log in step.get('logs', []):
          if log['name'] == 'stdout':
            return self._GetCompileTargetsFromURL(log['viewUrl'])

  def _GetCompileTargetsFromURL(self, url):
    stdout = str(requests.get(url).content).split('\\n')
    targets = []
    found_targets = 2
    index = 0
    while found_targets:
      if stdout[index] == ' &#39;-j&#39;,' and found_targets == 2:
        found_targets = 1
      elif found_targets == 1:
        line = stdout[index].strip().replace('&#39;', '\'')
        find = re.search(r'\'([a-zA-Z:/_]+)\'', line)
        if find:
          targets.append(find.group(1))
        if line.endswith(']'):
          found_targets = 0
      index += 1
    self._compile_targets = targets
    return targets

  def GetGNArgs(self):
    if self._gn_args:
      return self._gn_args
    for step in self._json.get('steps', []):
      if step['name'] == 'lookup GN args':
        for log in step.get('logs', []):
          if log['name'] == 'stdout':
            return self._GetGnArgsFromURL(log['viewUrl'])

  def _GetGnArgsFromURL(self, url):
    lookup_name = ''
    buildbot_name = ''
    setlookup = 0
    setbuildbot = 0
    for line in str(requests.get(url+'?format=raw').content, 'utf-8').split('\n'):
      if line == " '-m',":
        setlookup = 1
      elif line == " '-b',":
        setbuildbot = 1
      elif setlookup == 1:
        setlookup = 2
        lookup_name = line[2:-2]
      elif setbuildbot == 1:
        setbuildbot = 2
        buildbot_name = line[2:-2]

      if setbuildbot + setlookup == 4:
        command = './tools/mb/mb.py lookup -m {} -b {} --quiet'
        try:
          import subprocess
          stdout = subprocess.check_output(
            command.format(lookup_name, buildbot_name), shell=True)
          for entry in str(stdout, 'utf-8').split('\n'):
            _e = entry.split(' = ')
            if entry:
              self._gn_args[_e[0]] = _e[1]
          return self._gn_args
        except:
          print("Can't get gn args because the command fails:")
          print(command.format(lookup_name, buildbot_name))
          exit()




if __name__ == '__main__':
  import sys
  b = BuildbotEntries(sys.argv[1])
  print(b.GetCompileTargets())
  print(b.GetGNArgs())
