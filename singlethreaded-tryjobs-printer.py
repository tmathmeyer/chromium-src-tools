#!/usr/bin/env python3

# Example status page:
# https://chromium-cq-status.appspot.com/query/codereview_hostname=chromium-review.googlesource.com/issue=1875549/patchset=1

import colors
import re
import requests
import subprocess
import sys
import traceback

import libgerrit


def GetBots(crrev):
  cr = libgerrit.GetReviewDetail(crrev)
  return libgerrit.GetCQStatus(
    crrev, max(m._revision_number for m in cr.messages))


def GetBotsAndURLs(crrev):
  bots = GetBots(crrev)
  if not bots.results.RAW:
    raise ValueError('Could not get bot results')

  bots_and_urls = {}
  for result in bots.results[::-1]:
    try:
      for p in result.fields.jobs.JOB_PENDING:
        bots_and_urls[p.builder] = p.url
      return bots_and_urls
    except:
      continue

  return bots_and_urls


def GetBotStatuses(crrev):
  bots_and_urls = GetBotsAndURLs(crrev)
  for bot,url in bots_and_urls.items():
    try:
      yield (bot, libgerrit.GetBuildbotData(url, fields='status').status)
    except:
      yield (bot, 'SCRIPT_ERROR')


def RunCommand(command):
  return subprocess.run(command,
                        encoding='utf-8',
                        shell=True,
                        stderr=subprocess.PIPE,
                        stdout=subprocess.PIPE)


def ColorOf(status):
  if status == 'SCRIPT_ERROR':
    return colors.Color(bg=colors.PURPLE, fg=colors.BLACK)
  if status == 'SUCCESS':
    return colors.Color(bg = colors.GREEN, fg=colors.BLACK)


def FormatBotStatuses(bots_and_statuses):
  lines = RunCommand('tput cols')
  if lines.returncode:
    lines = 999999999
  else:
    lines = int(lines.stdout)

  remaining = lines
  output = ''
  for bot, status in bots_and_statuses:
    printname = bot
    if status == 'SCRIPT_ERROR':
      printname = f'*{bot}*'

    if len(printname) > remaining:
      remaining = lines
      print('')
      output += '\n\n'

    remaining -= (len(printname) + 1)
    print(f'{ColorOf(status)}{printname}{colors.Color()} ', end='')
    sys.stdout.flush()

  print('\n')


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
  crrev = GetCLId()
  print('bot statuses for crrev.com/{}'.format(crrev))

  FormatBotStatuses(GetBotStatuses(crrev))


if __name__ == '__main__':
  main()