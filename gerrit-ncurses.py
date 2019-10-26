#!/usr/bin/env python3

import curses
import re
import subprocess
import sys
import time
import threading

from lib import libgerrit
from lib import libpyterm as UI
from lib import librun


GERRIT_UI = UI.Layout(crstatus=('30x6', 'bordered'),
                      crmessage=('...x10', 'bordered'),
                      tryjobs=('30x...', 'bordered'),
                      crcomments=('...x...', 'bordered', 'padwindow'))






def BotQuery(gui, boturl, botname, window, idx):
  try:
    status = libgerrit.GetBuildbotData(boturl, fields='status').status
    if gui.finished:
      return
    if status == 'SUCCESS':
      window.addstr(idx+1, 1, botname, curses.color_pair(1))
    elif status == 'FAILURE':
      window.addstr(idx+1, 1, botname, curses.color_pair(3))
    elif status == 'STARTED':
      window.addstr(idx+1, 1, botname, curses.color_pair(2))
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
    self.finished = False
    self.restart_job = None
    self.bots = {}

  def Repaint(self):
    first_paint = True
    while not self.finished:
      cr = libgerrit.GetReviewDetail(self.crrev)
      current_revision = cr.revisions[cr.current_revision]
      self._RenderCommitMessage(current_revision.commit.message)
      self._RenderStatus(cr.owner.name, cr.labels['Code-Review'].all)
      self._RenderMessages(cr.messages)
      self._RenderTryJobs(current_revision._number, first_paint)
      if not self.finished:
        for i in range(10):
          time.sleep(1)
      first_paint = False

  def SetUp(self):
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_GREEN)
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(3, curses.COLOR_BLACK, curses.COLOR_RED)
    curses.init_pair(4, 8, 6)
    curses.init_pair(5, 7, 8)
    self.restart_job = threading.Thread(target=self.Repaint)
    self.restart_job.start()

  def ScrollDown(self):
    self.screen.crcomments.ScrollDown()
    self.screen.crcomments.refresh()

  def ScrollUp(self):
    self.screen.crcomments.ScrollUp()
    self.screen.crcomments.refresh()

  def _RenderCommitMessage(self, message):
    for idx, line in enumerate(message.split('\n')):
      if idx > self.screen.crmessage.Height():
        break
      if line:
        self.screen.crmessage.addstr(idx, 2+min(1,idx), line)
    self.screen.crmessage.refresh()

  def _RenderStatus(self, owner, labels):
    if labels:
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
    self.screen.crcomments.scrollok(True)
    comments = libgerrit.GetComments(self.crrev)

    author_revision_file = {}
    for file in comments:
      for comment in comments[file]:
        author = comment.author.name
        author_revision_file[author] = author_revision_file.get(author, {})
        auth_dict = author_revision_file[author]
        auth_dict[comment.patch_set] = auth_dict.get(comment.patch_set, {})
        auth_dict[comment.patch_set][file] = auth_dict[comment.patch_set].get(file, [])
        auth_dict[comment.patch_set][file].append((comment.line, comment.message))

    def WriteLineAndExpand(row, line, hpos, *args):
      if self.screen.crcomments.Height() > 100:
        return row
      if row > self.screen.crcomments.Height() - 2:
        self.screen.crcomments.ExtendDown(5)
      self.screen.crcomments.addstr(row+1, hpos, line, *args)
      return row + 1

    line = 0
    for m in messages[::-1]:
      writelines = len(m.message.split('\n'))
      line = WriteLineAndExpand(line, f'{m.author.name}:', 1, curses.color_pair(4))

      for l in m.message.split('\n'):
        if l.strip():
          line = WriteLineAndExpand(line, l, 1)

      files = author_revision_file.get(m.author.name, {}).get(m._revision_number, {})
      for file, cmts in files.items():
        line = WriteLineAndExpand(line, file + ':', 2, curses.color_pair(5))
        for comment in cmts:
          lnno, msg = comment
          indent = f'Line {lnno}: '
          line = WriteLineAndExpand(line, indent, 4, curses.color_pair(5)) - 1
          for cmtline in msg.split('\n'):
            if cmtline.strip():
              line = WriteLineAndExpand(line, cmtline, 4+len(indent))


      if line < self.screen.crcomments.Height():
        divider='├' + ('─' * (self.screen.crcomments.Width() - 1))
        line = WriteLineAndExpand(line, divider, 0)

    self.screen.crcomments.refresh()

  def _RenderTryJobs(self, revision_number, first_paint):
    cq = libgerrit.GetCQStatus(self.crrev, revision_number)
    if not cq.results.RAW:
      self.screen.tryjobs.addstr(1, 1, 'No tryjobs')
      self.screen.tryjobs.refresh()
      return

    if not self.bots:
      self.bots = {}
      for result in cq.results[::-1]:
        try:
          for idx, p in enumerate(result.fields.jobs.JOB_PENDING):
            self.bots[p.builder] = {
              'url': p.url,
              'line': idx
            }
          break
        except:
          continue

      if not self.bots:
        self.screen.tryjobs.addstr(1, 1, 'No tryjobs')
        self.screen.tryjobs.refresh()

      self.screen.tryjobs.addstr(0, 2, 'Tryjobs')
      for bot, data in self.bots.items():
        line = data['line'] + 1
        if line < self.screen.tryjobs.Height():
          self.screen.tryjobs.addstr(line, 1, bot)
      self.screen.tryjobs.refresh()

    for bot, data in self.bots.items():
      line = data['line'] + 1
      if line < self.screen.tryjobs.Height():
        thr = threading.Thread(target=BotQuery, args=(self,
          data['url'], bot, self.screen.tryjobs, data['line']))
        thr.start()
        self._jobs.append(thr)

  def __del__(self):
    self.join()

  def join(self):
    try:
      self.finished = True
      if self.restart_job:
        self.restart_job.join()
      for job in self._jobs:
        job.join()
    except:
      pass


def GetCLId():
  if len(sys.argv) > 1:
    return sys.argv[1]

  r = librun.RunCommand('git cl issue')
  if r.returncode:
    raise ValueError('Can\'t run `git cl issue` here')

  cl_id_regex = r':\s([0-9]+)\s'
  clid = re.search(cl_id_regex, r.stdout)

  if clid:
    return clid.group(1)
  else:
    raise ValueError('Couldn\'t get bot statuses for {}'.format(clid))


def main():
  gui = None
  with UI.TermWindow(GERRIT_UI) as screen:
    gui = GerritUI(screen, GetCLId())
    gui.SetUp()
    while True:
      key = screen.crmessage.getkey()
      if key == 'q':
        break
      if key == 'j':
        gui.ScrollDown()
      if key == 'k':
        gui.ScrollUp()
      screen.crmessage.refresh()

  if gui:
    print('Waiting for exit... (this can take a few moments)')
    gui.finished = True


if __name__ == '__main__':
  main()