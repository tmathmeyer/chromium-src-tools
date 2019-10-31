"""A reimplementation of the pdl parser, because the canonical one sucks."""

from collections import namedtuple
import os

PRIMITIVES = {
  "integer": int,
  "number": float,
  "boolean": bool,
  "string": str,
  "binary": bytes
}


IndentationToken = namedtuple('IndentationToken', ['indentation'])
CommentToken = namedtuple('CommentToken', ['message'])
StrToken = namedtuple('StrToken', ['value'])


class TokenStreamer(object):
  def __init__(self, filecontents):
    self._contents = filecontents.split('\n')

  def Iterate(self):
    for line in self._contents:
      stripline = line.strip()
      indentation = len(line) - len(stripline)
      if not stripline:
        continue

      if stripline.startswith("#"):
        yield CommentToken(stripline[1:].strip())
      else:
        yield IndentationToken(indentation)
        print(stripline)
        for token in stripline.split(' '):
          yield StrToken(token)


def R(C, T, S, ____):
  kill = str(T)
  for _ in range(10):
    kill += f'\n{str(next(S))}'
  raise ValueError(kill + str(C))


def P(*_, **__):
  pass


class IndentationJump(Exception):
  def __init__(self, indent):
    super().__init__(str(indent))
    self.indent = indent


def IterateHandler(stream, directives, base_indent=0):
  print(f'Iterating stream [{base_indent}] {directives}')
  current_stack_context = {}
  read_any_data = False
  current_indent = base_indent
  try:
    while True:
      token = next(stream)
      if type(token) == IndentationToken:
        current_indent = token.indentation
        if current_indent < base_indent:
          raise IndentationJump(current_indent)
      else:
        read_any_data = token
        is_exempt_from_jump = False
        try:
          directives.get(type(token), R)(
            current_stack_context, token, stream, current_indent)
        except IndentationJump as jump:
          print(f'Captured jump({jump.indent}) - {base_indent} {directives}')
          if jump.indent == 0 and base_indent == -1:
            is_exempt_from_jump = True
          elif jump.indent == base_indent:
            is_exempt_from_jump = True
          else:
            raise jump
        except:
          R(current_stack_context, token, stream, current_indent)
  except StopIteration:
    return current_stack_context
  else:
    raise ValueError('Should not have happened...')


def _DropComment(_, token, __, ___):
  #print(f'Comment ===>  {token.message}')
  pass


def SetDefaultFields(ctx, **kwargs):
  for k, v in kwargs.items():
    if k not in ctx:
      ctx[k] = v


def VersionAndDomains(context, token, stream, indent):
  print(token.value)
  if token.value == 'version':
    return ReadVersion(context, stream, indent)
  if token.value == 'experimental':
    assert next(stream).value == 'domain'
    print('domain')
    return ReadDomain(context, stream, indent, is_experimental=True)
  if token.value == 'domain':
    return ReadDomain(context, stream, indent)


def ReadVersion(context, stream, indent):
  def _ReadMMVersion(ctx, tok, stm, idt):
    print(tok.value)
    assert tok.value == 'major' or tok.value == 'minor'
    ctx[tok.value] = int(next(stm).value)
    print(ctx[tok.value])

  context['version'] = IterateHandler(stream, {
    CommentToken: _DropComment,
    StrToken: _ReadMMVersion
  }, indent+2)


def _ReadDomain(context, token, stream, indent):
  SetDefaultFields(context, type=[], command=[], depends=[], event=[])
  print(token.value)
  if token.value == 'experimental':
    next_token = next(stream)
    domain_name = _ReadDomain(context, next_token, stream, indent)
    context[domain_name][-1]['experimental'] = True
    return domain_name
  if token.value == 'deprecated':
    next_token = next(stream)
    domain_name = _ReadDomain(context, next_token, stream, indent)
    context[domain_name][-1]['deprecated'] = True
    return domain_name

  assert token.value != 'domain'

  context[token.value].append({
    'type': ReadType,
    'command': ReadCommand,
    'depends': ReadDepends,
    'event': ReadEvent,
  }[token.value](stream, indent))

  return token.value


def ReadDomain(context, stream, indent, is_experimental=False):
  DomainName = next(stream).value
  print(DomainName)
  context[DomainName] = IterateHandler(stream, {
    CommentToken: _DropComment,
    StrToken: _ReadDomain
  }, indent)


def ReadType(stream, indent):
  result = {}
  result['typename'] = next(stream).value
  print(result['typename'])
  assert next(stream).value == 'extends'
  result['extends'] = next(stream).value
  result.update(IterateHandler(stream, {
    CommentToken: _DropComment,
    StrToken: P
  }, indent))
  return result


def ReadCommand(stream, indent):
  result = {}
  result['commandname'] = next(stream).value
  print(result['commandname'])
  result.update(IterateHandler(stream, {
    CommentToken: _DropComment,
    StrToken: P
  }, indent))
  return result

def ReadEvent(stream, indent):
  result = {}
  result['eventname'] = next(stream).value
  print(result['eventname'])
  result.update(IterateHandler(stream, {
    CommentToken: _DropComment,
    StrToken: P
  }, indent))
  return result


def ReadDepends(stream, indent):
  result = {}
  assert next(stream).value == 'on'
  print('on')
  result['depends_on'] = next(stream).value
  print(result['depends_on'])
  return result


def GetPDLContext(filecontents):
  return IterateHandler(TokenStreamer(filecontents).Iterate(), {
    CommentToken: _DropComment,
    StrToken: VersionAndDomains,
  })


if __name__ == '__main__':
  chrsrc = '/usr/local/google/home/tmathmeyer/chromium/src'
  pdlpath = 'third_party/blink/renderer/core/inspector/browser_protocol.pdl'
  with open(os.path.join(chrsrc, pdlpath), 'r') as f:
    print(GetPDLContext(f.read()))