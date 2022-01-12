#!/usr/bin/env python3

import json
import os
import re
import requests
import subprocess
import sys
from dataclasses import dataclass
from urllib.parse import urlparse


RPC = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild'


def find_by_name(entries, name):
  for entry in entries:
    if entry['name'].endswith(name):
      return entry
  avail = [e['name'] for e in entries]
  raise ValueError(f'name "{name}" not found in {avail}')


def once(fn):
  fn.__data = None
  def replacement(*args, **kwargs):
    if fn.__data is not None:
      return fn.__data
    fn.__data = fn(*args, **kwargs)
    return fn.__data
  return replacement


@dataclass
class CIBuild:
  url: str
  project: str
  bucket: str
  builder: str
  buildid: str

  @staticmethod
  def from_bot_url(url: str) -> 'CIBuild':
    parsed = urlparse(url)
    if parsed.netloc != 'ci.chromium.org':
      raise ValueError('Please provide the ci.chromium.org url')
    url_pattern = re.compile(
      r'https://ci\.chromium\.org/ui/p/(\S+)/builders/(\S+)/(\S+)/([b]*[0-9]+)')
    match = url_pattern.match(url)
    if not match:
      raise ValueError(f'URL must be in the format: {url_pattern}')
    return CIBuild(url, *match.groups())

  def _get_self_json(self) -> str:
    return json.dumps({
      'builder': {
        'project': self.project,
        'bucket': self.bucket,
        'builder': self.builder,
      },
      'buildNumber': self.buildid,
      'fields': 'steps,id',
    })

  @once
  def _make_rpc(self) -> 'JSON':
    q = requests.post(
      url=RPC,
      data=self._get_self_json(),
      headers={
        'content-type': 'application/json',
        'accept': 'application/json'
      })
    if q.status_code != 200:
      raise ValueError(f'RPC to {RPC} failed')
    return json.loads(q.text[5:])

  def outdir_exists(self) -> bool:
    return os.path.exists(f'out/BOT_{self.builder}')

  def snag_gn_args(self) -> {str, str}:
    lookup_args = find_by_name(self._make_rpc().get('steps'), 'lookup GN args')
    url = find_by_name(lookup_args.get('logs'), 'execution details')['viewUrl']
    raw = str(requests.get(f'{url}?format=raw').content, 'utf-8').split('\n')
    m_flag, b_flag = None, None
    for i, line in enumerate(raw):
      line = line.strip()[1:-2]
      if line == '-m':
        m_flag = raw[i+1].strip()[1:-2]
      elif line == '-b':
        b_flag = raw[i+1].strip()[1:-2]
      if None not in (m_flag, b_flag):
        print(f'./tools/mb/mb.py lookup -m {m_flag} -b {b_flag} --quiet')
        raw_flags = str(subprocess.check_output(
          f'./tools/mb/mb.py lookup -m {m_flag} -b {b_flag} --quiet',
          shell=True), 'utf-8').split('\n')
        split_flags = [f.split(' = ') for f in raw_flags]
        return {e[0]:e[1] for e in split_flags if len(e) > 1}
    raise ValueError('Couldnt get the args for mb.py')

  def create_outdir(self):
    if self.outdir_exists():
      return
    gn_args = self.snag_gn_args()

    if 'coverage_instrumentation_input_file' in gn_args:
      gn_args.pop('coverage_instrumentation_input_file')

    if 'goma_dir' in gn_args or gn_args.get('use_goma') == 'true':
      root = os.environ['PWD']
      gn_args['goma_dir'] = f'"{root}/third_party/depot_tools/.cipd_bin"'

    args = '\n'.join(f'{k}={v}' for k,v in gn_args.items())
    cmd = f'gn gen out/BOT_{self.builder} -check --args=\'{args}\''
    os.system(cmd)

  def _get_targets_gbf(self):
    steps = self._make_rpc().get('steps')
    gen = find_by_name(steps, 'generate_build_files (with patch)')
    swarming = find_by_name(gen.get('logs'), 'swarming-targets-file.txt')
    url = f'{swarming["viewUrl"]}?format=raw'
    targets = str(requests.get(url).content, 'utf-8').split('\n')
    return set(t.strip() for t in targets if t.strip())

  def _get_targets_comp(self):
    steps = self._make_rpc().get('steps')
    gen = find_by_name(steps, 'compile')
    exec_details = find_by_name(gen.get('logs'), 'execution details')
    url = f'{exec_details["viewUrl"]}?format=raw'
    cmd = str(requests.get(url).content, 'utf-8').split('\n')
    cmd = [c.strip() for c in cmd]
    targets = None
    for c in cmd:
      if c == "'80',":
        targets = []
        continue
      if c == ']':
        return targets
      if targets is not None:
        targets.append(c[1:-2])

  def get_targets(self):
    try:
      return self._get_targets_gbf()
    except:
      pass
    try:
      return self._get_targets_comp()
    except:
      pass
    return ['all']

  def build_targets(self, targets):
    failcount = 0
    while targets:
      if failcount == 10:
        targets = ['all']
      print(f'ninja -C out/BOT_{self.builder} -j5000 {{{len(targets)} targets}}')
      output = subprocess.run(
        ['ninja', '-C', f'out/BOT_{self.builder}', '-j5000', *targets],
        stderr=subprocess.PIPE, stdout=None)
      if output.returncode != 0:
        error = str(output.stderr)
        if 'unknown target' in error:
          bad_target = error.split('unknown target')[1].split('\'')[1]
          targets.remove(bad_target)
          print(f'cant build target: {bad_target}')
          failcount += 1
          continue
        raise ValueError(error)
      return

  def pull_and_build(self):
    self.create_outdir()
    self.build_targets(self.get_targets())


if __name__ == '__main__':
  build = CIBuild.from_bot_url(sys.argv[1])
  args = build.pull_and_build()

