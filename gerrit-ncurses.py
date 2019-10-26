#!/usr/local/bin/python3.8

import curses
import re
import subprocess
import sys
import time
import threading

from lib import libgerrit
import pytermui.pyterm as UI


GERRIT_UI = UI.Layout(crstatus=('30x6', 'bordered'),
                      crmessage=('...x10', 'bordered'),
                      tryjobs=('30x...', 'bordered'),
                      crcomments=('...x...', 'bordered'))



def BotQuery(boturl, botname, window, idx):
  try:
    status = libgerrit.GetBuildbotData(boturl, fields='status').status
    if status == 'SUCCESS':
      window.addstr(idx+1, 1, botname, curses.color_pair(1))
    elif status == 'FAILURE':
      window.addstr(idx+1, 1, botname, curses.color_pair(3))
    else:
      window.addstr(idx+1, 1, status, curses.color_pair(0))
  except:
    window.addstr(idx+1, 1, 'ERR', curses.color_pair(3))
  window.refresh()



class GerritUI(object):
  def __init__(self, screen, crrev):
    self.screen = screen
    self.crrev = crrev
    self._jobs = []

  def SetUp(self):
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(4, 8, 6)
    cr = libgerrit.GetReviewDetail(self.crrev)
    current_revision = cr.revisions[cr.current_revision]
    self._RenderCommitMessage(current_revision.commit.message)
    self._RenderStatus(cr.owner.name, cr.labels['Code-Review'].all)
    self._RenderMessages(cr.messages)
    self._RenderTryJobs(current_revision._number)

  def _RenderCommitMessage(self, message):
    for idx, line in enumerate(message.split('\n')):
      if idx > self.screen.crmessage.Height():
        break
      if line:
        self.screen.crmessage.addstr(idx, 2+min(1,idx), line)
    self.screen.crmessage.refresh()

  def _RenderStatus(self, owner, labels):
    self.screen.crstatus.addstr(0, 2, f'Owner: {owner}')
    self.screen.crstatus.addstr(1, 1, 'Reviews:')
    for idx, l in enumerate(labels):
      color = 0
      if l.value == 1:
        color = 1
      self.screen.crstatus.addstr(idx+1, 10, f'{l.name}: {l.value}',
        curses.color_pair(color))
    self.screen.crstatus.refresh()

  def _RenderMessages(self, messages):
    line = 1
    for m in messages[::-1]:
      writelines = len(m.message.split('\n'))
      if line+writelines > self.screen.crcomments.Height():
        self.screen.crcomments.refresh()
        return

      self.screen.crcomments.addstr(line, 2, f'{m.author.name}:',
        curses.color_pair(4))
      for l in m.message.split('\n'):
        if l.strip():
          self.screen.crcomments.addstr(line+1, 1, l)
          line += 1

      if line < self.screen.crcomments.Height():
        divider='├' + ('─' * (self.screen.crcomments.Width())) + '┤'
        self.screen.crcomments.addstr(line+1, 0, divider)
        line += 1

      line += 1

    self.screen.crcomments.refresh()

  def _RenderTryJobs(self, revision_number):
    cq = libgerrit.GetCQStatus(self.crrev, revision_number)
    if not cq.results.RAW:
      self.screen.tryjobs.addstr(1, 1, 'No tryjobs')
      self.screen.tryjobs.refresh()
      return

    bots = {}
    for result in cq.results[::-1]:
      try:
        for idx, p in enumerate(result.fields.jobs.JOB_PENDING):
          bots[p.builder] = {
            'url': p.url,
            'line': idx
          }
        break
      except:
        continue

    if not bots:
      self.screen.tryjobs.addstr(1, 1, 'No tryjobs')
      self.screen.tryjobs.refresh()

    self.screen.tryjobs.addstr(0, 2, 'Tryjobs')
    for bot, data in bots.items():
      line = data['line'] + 1
      if line < self.screen.tryjobs.Height():
        self.screen.tryjobs.addstr(line, 1, bot)
        thr = threading.Thread(target=BotQuery, args=(
          data['url'], bot, self.screen.tryjobs, data['line']))
        thr.start()
        self._jobs.append(thr)
    self.screen.tryjobs.refresh()

  def __del__(self):
    try:
      for job in self._jobs:
        job.join()
    except:
      pass


def RunCommand(command):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)


def GetCLId():
  if len(sys.argv) > 1:
    return sys.argv[1]

  r = RunCommand('git cl issue')
  if r.returncode:
    raise ValueError('Can\'t run `git cl issue` here')

  cl_id_regex = r':\s([0-9]+)\s'
  clid = re.search(cl_id_regex, r.stdout)

  if clid:
    return clid.group(1)
  else:
    raise ValueError('Couldn\'t get bot statuses for {}'.format(clid))


def main():
  with UI.TermWindow(GERRIT_UI) as screen:
    gui = GerritUI(screen, GetCLId())
    gui.SetUp()

    while True:
      key = screen.crmessage.getkey()
      if key == 'q':
        break
      screen.crmessage.refresh()


if __name__ == '__main__':
  main()