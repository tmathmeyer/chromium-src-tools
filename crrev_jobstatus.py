#!/usr/bin/env python3

# Example status page:
# https://chromium-cq-status.appspot.com/query/codereview_hostname=chromium-review.googlesource.com/issue=1875549/patchset=1

import colors
import json
import numbers
import re
import requests
import subprocess
import sys


CRREV_DETAIL = 'https://chromium-review.googlesource.com/changes/{}/detail'
BOTS_INFO = 'https://chromium-cq-status.appspot.com/query/codereview_hostname=chromium-review.googlesource.com/issue={}/patchset={}'


class JSON(object):
  def __init__(self, json_obj):
    self.json_obj = json_obj
    self.type = None
    if type(self.json_obj) == str:
      self.type = 'str'
    elif type(self.json_obj) == list:
      self.type = 'list'
    elif type(self.json_obj) == dict:
      self.type = 'dict'
    elif isinstance(self.json_obj, numbers.Number):
      self.type = 'int'

  def __getattr__(self, attr):
    if self.type == 'dict':
      return JSON._Create(self.json_obj.get(attr))
    raise AttributeError

  def __getitem__(self, index):
    if self.type == 'list':
      return JSON._Create(self.json_obj[index])
    if self.type == 'dict':
      return JSON._Create(self.json_obj[index])
    raise KeyError

  def __repr__(self):
    return self.json_obj

  def __str__(self):
    return str(self.json_obj)

  def __iter__(self):
    if self.type == 'list':
      for index in self.json_obj:
        yield JSON._Create(index)
    elif self.type == 'dict':
      for index in self.json_obj.keys():
        yield index
    else:
      raise TypeError('type is {}'.format(self.type))

  @classmethod
  def _Create(cls, obj):
    if type(obj) == list:
      return JSON(obj)
    elif type(obj) == dict:
      return JSON(obj)
    else:
      return obj

  @classmethod
  def Create(cls, url):
    q = requests.get(url=url)
    if q.status_code != 200:
      return None
    elif q.text[0:4] == ')]}\'':
      return JSON._Create(json.loads(q.text[5:]))
    else:
      return JSON._Create(json.loads(q.text))


def GetBots(crrev):
  cl = JSON.Create(CRREV_DETAIL.format(crrev))
  m = max(m._revision_number for m in cl.messages)
  print(BOTS_INFO.format(crrev, m))
  bots = JSON.Create(BOTS_INFO.format(crrev, m))
  return bots


def show_bot_job_statii(crrev):
  bots = GetBots(crrev)
  botstatuses = {}

  for res in bots.results:
    fields = None
    try:
      fields = res["fields"]["jobs"]
    except:
      continue
    running = []
    succeeded = []
    failed = []
    try:
      running = fields["JOB_RUNNING"]
    except:
      pass
    try:
      succeeded = fields["JOB_SUCCEEDED"]
    except:
      pass
    try:
      failed = fields["JOB_FAILED"]
    except:
      pass
    for job in running:
      botstatuses[job.builder] = botstatuses.get(job.builder, 'running')
    for job in succeeded:
      botstatuses[job.builder] = 'success'
    for job in failed:
      botstatuses[job.builder] = 'failure'

  for name, status in botstatuses.items():
    if status == 'success':
      print("{}: {}{}{}".format(name, colors.OKGREEN, status, colors.ENDC))
    elif status == 'failure':
      print("{}: {}{}{}".format(name, colors.FAIL, status, colors.ENDC))
    elif status == 'running':
      print("{}: {}{}{}".format(name, colors.WARNING, status, colors.ENDC))


def RunCommand(self, command):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)


if __name__ == '__main__':
  if len(sys.argv) > 1:
    print('bot statuses for crrev.com/{}'.format(sys.argv[1]))
    show_bot_job_statii(sys.argv[1])
    return

  r = RunCommand('git cl issue')
  if r.returncode:
    print('Can\'t run `git cl issue` here')
    return

  cl_id_regex = r':\s([0-9]+)\s'
  clid = re.search(r.stdout, cl_id_regex)

  if clid:
    print('bot statuses for crrev.com/{}'.format(clid))
    show_bot_job_statii(clid)
  else:
    print('Couldn\'t get bot statuses for {}'.format(clid))
