#!/usr/bin/env python3

import threading
import time

from lib import libpyterm as UI
from lib import libgerrit


class CRMessage(UI.NormalWindow):
  def __init__(self):
    super().__init__(bordered=True)

  def Repaint(self, context):
    revision = context.cr.revisions[context.cr.current_revision]
    for idx, line in enumerate(revision.commit.message.split('\n')):
      if idx > self.Height() - 2:
        break
      if line:
        self.WriteString(2+min(1, idx+1), idx+1, line)


class CRStatus(UI.NormalWindow):
  def __init__(self):
    super().__init__()

  def Repaint(self, context):
    owner = context.cr.owner.name
    reviews = context.cr.labels['Code-Review'].all
    if reviews:
      self.WriteString(2, 1, f'Owner: {owner}')
      self.WriteString(1, 2, 'Reviews:')
      for idx, l in enumerate(reviews):
        color = context.colors.GetColor()
        if l.value == 1:
          color = context.colors.GetColor('BLACK', 'GREEN')
        self.WriteString(10, idx+2, f'{l.name}: {l.value}', color)


class CRTryjobs(UI.NormalWindow):
  def __init__(self):
    super().__init__(bordered=True)
    self.tryjobs = {}
    self.setupthread = None

  def BotQuery(self, buildername, terminal):
    try:
      boturl = self.tryjobs[buildername]['url']
      status = libgerrit.GetBuildbotData(boturl, fields='status').status
      self.tryjobs[buildername]['status'] = status
    except:
      self.tryjobs[buildername]['name'] = 'ERROR'
      self.tryjobs[buildername]['status'] = 'ERROR'
    terminal.PaintWindow(self)

  def ColorForStatus(self, context, status):
    if status == 'PENDING':
      return context.colors.GetColor('BLACK', 7)
    if status == 'SUCCESS':
      return context.colors.GetColor('BLACK', 'GREEN')
    if status == 'FAILURE':
      return context.colors.GetColor('BLACK', 'RED')
    if status == 'STARTED':
      return context.colors.GetColor('BLACK', 'YELLOW')
    if status == 'ERROR':
      return context.colors.GetColor('BLACK', 'RED')
    return context.colors.GetColor()

  def GetTryjobsList(self, cq, context):
    for result in cq.results[::-1]:
      try:
        for idx, p in enumerate(result.fields.jobs.JOB_PENDING):
          self.tryjobs[p.builder] = {
            'url': p.url,
            'name': p.builder,
            'line': idx,
            'status': 'UNKNOWN',
            'thread': threading.Thread(
              target=self.BotQuery, args=(p.builder, context.terminal))
          }
          self.tryjobs[p.builder]['thread'].start()
        return
      except:
        continue

  def RepaintInitial(self, context):
    revision = context.cr.revisions[context.cr.current_revision]
    cq = libgerrit.GetCQStatus(context.crnumber, revision._number)
    if not cq.results.RAW:
      self.WriteString(1, 1, 'No tryjobs')
      return

    if not self.tryjobs:
      self.GetTryjobsList(cq, context)

    self.setupthread = 'Finished'
    context.terminal.PaintWindow(self)


  def Repaint(self, context):
    if self.setupthread is None:
      self.setupthread = threading.Thread(
        target=self.RepaintInitial, args=(context,))
      self.setupthread.start()
      self.WriteString(1, 1, 'Querying CQ')
      return

    if self.setupthread == 'Finished':
      if not self.tryjobs:
        self.WriteString(1, 1, 'No tryjobs')
        return

      for bot, data in self.tryjobs.items():
        line = data['line'] + 1
        if line < self.Height():
          self.WriteString(1, line, data['name'], self.ColorForStatus(
            context, data['status']))


class CRComments(UI.ScrollWindow):
  def __init__(self):
    super().__init__(up='k', down='j')
    self.comments_lines = []
    self.fetcher_thread = None
    self.fetch_message = 'Pending'

  def PaintComments(self, context):
    lineno = 1
    self.SetHeight(len(self.comments_lines))
    for l, hpos, args in self.comments_lines:
      if lineno < self.Height():
        self.WriteString(hpos, lineno, l, *args)
        lineno += 1
      else:
        return

  def FetchComments(self, context):
    comments = libgerrit.GetComments(context.crnumber)
    try:
      author_revision_file = {}
      for file in comments:
        for comment in comments[file]:
          author = comment.author.name
          author_revision_file[author] = author_revision_file.get(author, {})
          auth_dict = author_revision_file[author]
          auth_dict[comment.patch_set] = auth_dict.get(comment.patch_set, {})
          auth_dict[comment.patch_set][file] = auth_dict[comment.patch_set].get(file, [])
          auth_dict[comment.patch_set][file].append((comment.line, comment.message))
      self.fetch_message = 'Parsed Files And Revision'
    except:
      self.fetch_message = 'File & Revision Parsing Failed'
      context.terminal.PaintWindow(self)
      return

    def WriteLineAndExpand(line, hpos, *args):
      self.comments_lines.append((line, hpos, args))

    for m in context.cr.messages[::-1]:
      try:
        writelines = len(m.message.split('\n'))
        WriteLineAndExpand(f'{m.author.name}:', 1, context.colors.GetColor(8, 6))
        for l in m.message.split('\n'):
          if l.strip():
            WriteLineAndExpand(l, 1)
      except:
        self.fetch_message = 'Failed to expand comments'
        context.terminal.PaintWindow(self)
        return

      try:
        files = author_revision_file.get(m.author.name, {}).get(m._revision_number, {})
        for file, cmts in files.items():
          WriteLineAndExpand(file + ':', 2, context.colors.GetColor(7, 8))
          for comment in cmts:
            lnno, msg = comment
            indent = f'Line {lnno}: '
            WriteLineAndExpand(indent, 4, context.colors.GetColor(7, 8))
            for cmtline in msg.split('\n'):
              if cmtline.strip():
                WriteLineAndExpand(cmtline, 4+len(indent))
      except:
        self.fetch_message = 'Failed to get comments for file'
        context.terminal.PaintWindow(self)
        return

    self.fetcher_thread = 'Finished'
    context.terminal.PaintWindow(self)

  def Repaint(self, context):
    if self.fetcher_thread is None:
      self.WriteString(1, 1, 'Fetching Comments')
      self.fetcher_thread = threading.Thread(target=self.FetchComments,
        args=(context,))
      self.fetcher_thread.start()
    elif self.fetcher_thread == 'Finished':
      self.PaintComments(context)
    else:
      self.WriteString(1, 1, f'Fetching Comments: {self.fetch_message}')


class Context(object):
  __slots__ = ('crnumber', 'cr', 'colors', 'terminal')
  def __init__(self):
    self.crnumber = 1875517
    self.cr = libgerrit.GetReviewDetail(f'{self.crnumber}')
    self.colors = None
    self.terminal = None


windows = (('30', '6', CRStatus),
           ('...', '10', CRMessage),
           ('30', '...', CRTryjobs),
           ('...', '...', CRComments))


with UI.Terminal(windows, Context()) as c:
  c.Start()
  c.WaitUntilEnded()