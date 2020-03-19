#!/usr/bin/env python3.8

from lib import libhtmlparse as html_parser
import requests
import sys



NO_CLASS = html_parser.ParserFinder(
"""
<tr>
  <td>{{}}</td>
  <td style="{_}">{_}</td>
</tr>
"""
)

WITH_CLASS = html_parser.ParserFinder(
"""
<tr>
  <td class="{_}">{{}}</td>
  <td style="{_}">{_}</td>
</tr>
"""
)

CODE_AREA = html_parser.ParserFinder(
"""
<code class="{_}">{{}}</code>
"""
)

class MSApiPageParser(object):
  def __init__(self, url):
    self._url = url
    self._parser = html_parser.ParserExtracter(WITH_CLASS, NO_CLASS)

  def GetNextMockMethod(self):
    r = requests.get(self._url)
    self._parser.feed(r.text)
    for capture in self._parser:
      data = capture.data[0]
      if data[0].tag == 'a':
        url = data[0].attrs[0][1]
        com = data[1]
        yield self.WriteMockLine(com, url)

  def WriteMockLine(self, com, url):
    ret, args = self.ExtractMethodSignitureFromPage(url)
    com = com.split('::')[1]
    a_cnt = len(args)
    a_str = ', '.join(args)
    return f'MOCK_STDCALL_METHOD{a_cnt}({com}, {ret}({a_str}));'

  def ExtractMethodSignitureFromPage(self, url_end):
    newurl = '/'.join(self._url.split('/')[:-1] + [url_end])
    parser = html_parser.ParserExtracter(CODE_AREA)
    parser.feed(requests.get(newurl).text)
    for code in parser:
      return self.ParseRawHeaderString(code.data[0][0])

  def ParseRawHeaderString(self, code):
    code = code.split('\n')
    rettype = code[0].split(' ')[0].strip()
    args = []
    for l in code[1:]:
      l = l.strip()
      if not l.startswith(')') and l:
        t, n = l.rsplit(' ', 1)
        t = t.strip()
        while n.startswith('*'):
          n = n[1:]
          t += '*'
        args.append(t)
    return rettype, args


p = MSApiPageParser(sys.argv[1])
for mock_method in p.GetNextMockMethod():
  print(mock_method)

