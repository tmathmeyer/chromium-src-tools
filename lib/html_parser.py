from html.parser import HTMLParser
from collections import namedtuple


class Tag(namedtuple('Tag', ['tag', 'attrs'])):
  def close(self):
    return Tag('/'+self.tag, None)

  def __eq__(self, other):
    if not isinstance(other, Tag):
      return False

    if self.tag != other.tag:
      return False

    mine = {a:b for a, b in self.attrs or []}
    for attr, val in other.attrs or []:
      m = mine.get(attr, None)
      if m != val and m not in ('{_}', '{{}}'):
        return False
      if m:
        del mine[attr]

    if mine:
      return False

    return True

class CaptureSection(object):
  def __init__(self):
    pass

  def print(self, indent=0):
    print(' '*indent, '{{CAPTURE}}')

  def flatten(self):
    yield self


CAPTURE_SECTION = CaptureSection()


class ParserFinder(HTMLParser):
  def __init__(self, content):
    super(ParserFinder, self).__init__()
    self._stream = []
    self.feed(content)

  def get_stream(self):
    return self._stream

  def handle_starttag(self, tag, attrs):
    self._stream.append(Tag(tag, attrs))

  def handle_endtag(self, tag):
    self._stream.append(Tag(tag, None).close())

  def handle_data(self, data):
    if data == '{{}}':
      self._stream.append(CAPTURE_SECTION)

  def __repr__(self):
    return str(self._stream)


class CaptureGroup(object):
  def __init__(self):
    self._in_group = False
    self.data = []

  def addToCurrentGroup(self, data):
    if not self._in_group:
      raise ValueError('Cant add to capture when not in group')
    self.data[-1].append(data)

  def newGroup(self):
    self.data.append([])
    self._in_group = True

  def doneGroup(self):
    self._in_group = False

  def __str__(self):
    return str(tuple(self.data))


class ParserExtracter():
  def __init__(self, *finders):
    self._extractors = [_ParserExtracter(f) for f in finders]
    self._feed = None

  def feed(self, txt):
    self._feed = str(txt)

  def __iter__(self):
    for extractor in self._extractors:
      extractor.feed(self._feed)
      yield from extractor


class _ParserExtracter(HTMLParser):
  def __init__(self, finder):
    super().__init__()
    self._in_order = list(finder.get_stream())
    self._capturing = False
    self._capture_depth = 0
    self._has_unfinished_capture = False
    self._captures = []
    self._reset_expected_tag()

  def __iter__(self):
    if self._has_unfinished_capture:
      self._captures.pop()
    for capture in self._captures:
      yield capture

  def _increment_expected_tag(self, re_entrant=False):
    self._index += 1
    if self._index == len(self._in_order):
      self._has_unfinished_capture = False
      self._reset_expected_tag()
      return
    if self._index > len(self._in_order):
      raise ValueError('index should never have gotten this long!')

    self._next_expected_tag = self._in_order[self._index]
    if self._next_expected_tag == CAPTURE_SECTION:
      if re_entrant:
        raise ValueError('Cant capture two groups in a row')
      self._increment_expected_tag(True)
      self._capturing = True
      self._capture_depth = 0
      self._captures[-1].newGroup()
      return
    elif not re_entrant:
      if self._capture_depth:
        raise ValueError('Cant stop capturing while there are unclosed tags')
      self._capturing = False
      self._captures[-1].doneGroup()

  def _reset_expected_tag(self):
    self._index = 0
    self._next_expected_tag = self._in_order[self._index]
    if self._has_unfinished_capture:
      self._captures.pop()

    self._has_unfinished_capture = True
    self._capturing = False
    self._captures.append(CaptureGroup())

  def handle_starttag(self, tag, attrs):
    tag = Tag(tag, attrs)
    if self._capturing:
      self._captures[-1].addToCurrentGroup(tag)
      if tag.tag != 'br':
        self._capture_depth += 1
      return
    if self._next_expected_tag == tag:
      self._increment_expected_tag()
    else:
      self._reset_expected_tag()

  def handle_endtag(self, tag):
    tag = Tag(tag, None).close()
    if self._capturing:
      if self._capture_depth:
        self._captures[-1].addToCurrentGroup(tag)
        self._capture_depth -= 1
        return
    if tag == self._next_expected_tag:
      self._increment_expected_tag()
    else:
      self._reset_expected_tag()

  def handle_data(self, data):
    if self._capturing:
      data = data.replace('\\n', '\n')
      data = data.strip()
      if data:
        self._captures[-1].addToCurrentGroup(data)



