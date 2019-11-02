"""A reimplementation of the pdl parser, because the canonical one sucks."""

from collections import namedtuple
import os

PRIMITIVES = {
  "integer": int,
  "number": float,
  "boolean": bool,
  "binary": bytes,
  "string": None,
  "object": None,
  "array": None
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
        for token in stripline.split(' '):
          yield StrToken(token)


def BuildTreeFromFile(filecontents):
  return BuildTree(TokenStreamer(filecontents).Iterate())


def BuildTree(stream, indent=0):
  nodes = []
  current_line = []
  try:
    while True:
      token = next(stream)
      if type(token) == CommentToken:
        continue
      elif type(token) == StrToken:
        current_line.append(token.value)
      elif type(token) == IndentationToken:
        nextindent = token.indentation
        if nextindent > indent:
          nextindent, subtree = BuildTree(stream, token.indentation)
          current_line.append(subtree)
        if nextindent <= indent:
          if current_line:
            nodes.append(current_line)
          current_line = []
        if nextindent < indent:
          return nextindent, nodes
      else:
        raise ValueError(str(token))
  except StopIteration:
    if current_line:
      nodes.append(current_line)
    return indent, nodes
  else:
    raise ValueError('Should not have happened...')


class Container(type):
  def __new__(cls, name, bases, dct):
    x = super().__new__(cls, name, bases, dct)
    x.Construct = cls.Construct(name)
    cls.name = name
    return x

  def __or__(cls, other):
    return GreedyTypeSelector([cls(), other()])

  def Construct(name):
    def _Construct(self, **kwargs):
      return namedtuple(name, kwargs.keys())(**kwargs)
    return _Construct


class GreedyTypeSelector(object):
  def __init__(self, types):
    self.types = types

  def __or__(self, other):
    if isinstance(other, GreedyTypeSelector):
      return GreedyTypeSelector(self.types + other.types)
    if type(other) == Container:
      return GreedyTypeSelector(self.types + [other()])

  def __call__(self):
    return self

  def Parse(self, tree, debug=False):
    result = {}
    for t in self.types:
      result[t.__class__.__name__] = []

    for each in tree:
      computed = self._Parse(each, debug=debug)
      result[computed.__class__.__name__].append(computed)

    for t in list(result.keys()):
      if result[t] == []:
        del result[t]
    return result

  def _Parse(self, tree, debug=False):
    for t in self.types:
      x = t.Parse(tree, debug=debug)
      if x is not None:
        return x
    raise ValueError(f'Unparsable - {tree} - {self.types}')


class KeyValue(metaclass=Container):
  def __init__(self, expected=None):
    self.expected = expected

  def Parse(self, tree, debug=False):
    if len(tree) != 2:
      return None
    elif self.expected and tree[0] != self.expected:
      return None
    elif self.expected:
      return self.Construct(value=tree[1])
    else:
      return self.Construct(key=tree[0], value=tree[1])


class PDLContainer(metaclass=Container):
  def __init__(self, name, subtypes, predicates=(), postfact=()):
    if type(subtypes) == GreedyTypeSelector:
      self.subtypes = subtypes
    elif subtypes is not None:
      self.subtypes = GreedyTypeSelector([subtypes()])
    else:
      self.subtypes = None
    self.name = name
    self.predicates = predicates
    self.postfact = postfact

  def GetPredicateMap(self, preds):
    result = {}
    for pred in preds:
      if pred in self.predicates:
        result[pred] = True
      else:
        raise ValueError(
          f'Unparsable - {pred} not in {self.predicates}')
    return result

  def ParsePostfactData(self, settings, postfact_data):
    if len(postfact_data) > len(self.postfact):
      if type(self.postfact[-1]) == SaveAs:
        postfact_data = postfact_data[:len(self.postfact)-1] + [
          postfact_data[len(self.postfact)-1:]
        ]
      else:
        raise ValueError('postfact misalignment')

    for data, wants in zip(postfact_data, self.postfact):
      if type(wants) == str:
        if data != wants:
          print(f'{data} != {wants}')
          print(f'{postfact_data} --- {self.postfact}')
          return False
      elif type(wants) == SaveAs:
        settings[wants.name] = data
      else:
        return False
    return True

  def DDEBUG(self, dbg, msg):
    if dbg:
      print(msg)

  def Parse(self, tree, debug=False):
    if len(tree) == 0:
      self.DDEBUG(debug, 'zero length tree')
      return None

    if type(tree[-1]) == list:
      subtypes = tree[-1]
      tree = tree[:-1]
    else:
      subtypes = None

    postfact_length = len(self.postfact)
    minimum_viable_length = 1 + postfact_length

    if len(tree) < minimum_viable_length:
      self.DDEBUG(debug, 'Below minimum viable length')
      return None
    try:
      nameindex = tree.index(self.name)
    except ValueError:
      self.DDEBUG(debug, f'{self.name} not found in {tree}')
      return None

    postfact_data = tree[nameindex+1:]
    tree = tree[:1+nameindex]

    settings = self.GetPredicateMap(tree[:-1])
    if postfact_data:
      if not self.ParsePostfactData(settings, postfact_data):
        self.DDEBUG(debug, f'Couldnt parse postfact data {postfact_data}')
        return None
    if subtypes:
      if not self.subtypes:
        raise ValueError(f'{self.__class__.__name__} needs subtypes!')
      settings.update(self.subtypes.Parse(subtypes))
    return self.Construct(**settings)


class SaveAs(object):
  def __init__(self, name):
    self.name = name


class Token(metaclass=Container):
  def Parse(self, tree, debug=False):
    if len(tree) == 1 and type(tree[0]) == str:
      return self.Construct(value=tree[0])
    return None


class TokenString(metaclass=Container):
  def Parse(self, tree, debug=False):
    return self.Construct(values=tree)


class VersionMajor(KeyValue):
  def __init__(self):
    super().__init__('major')


class VersionMinor(KeyValue):
  def __init__(self):
    super().__init__('minor')


class PDLVersion(PDLContainer):
  def __init__(self):
    super().__init__('version',
      VersionMajor|VersionMinor)


class DomainDepends(PDLContainer):
  def __init__(self):
    super().__init__('depends', None,
      postfact=('on', SaveAs('depends')))


class DomainTypeEnum(PDLContainer):
  def __init__(self):
    super().__init__('enum', Token)


class DomainTypeProperties(PDLContainer):
  def __init__(self):
    super().__init__('properties', TokenString)


class DomainType(PDLContainer):
  def __init__(self):
    super().__init__('type', DomainTypeEnum|DomainTypeProperties,
      predicates=('experimental', 'deprecated'),
      postfact=(SaveAs('name'), 'extends', SaveAs('extends')))


class Parameters(PDLContainer):
  def __init__(self):
    super().__init__('parameters', TokenString)


class Returns(PDLContainer):
  def __init__(self):
    super().__init__('returns', TokenString)


class Redirect(PDLContainer):
  def __init__(self):
    super().__init__('redirect', None,
      postfact=(SaveAs('redirect'),))


class DomainCommand(PDLContainer):
  def __init__(self):
    super().__init__('command', Parameters|Returns|Redirect,
      predicates=('experimental', 'deprecated'),
      postfact=(SaveAs('name'),))


class DomainEvent(PDLContainer):
  def __init__(self):
    super().__init__('event', Parameters,
      predicates=('experimental', 'deprecated'),
      postfact=(SaveAs('name'),))


class PDLDomain(PDLContainer):
  def __init__(self):
    super().__init__('domain',
      DomainDepends|DomainType|DomainCommand|DomainEvent,
      predicates=('experimental', 'deprecated'),
      postfact=(SaveAs('name'),))


class PDLDomainWrapper(object):
  def __init__(self, pdl_domain):
    remap = ('DomainType', 'DomainCommand', 'DomainEvent')
    for key in pdl_domain._fields:
      if key == 'DomainDepends':
        self.depends_on = pdl_domain.DomainDepends
      elif key == 'DomainType':
        for command in pdl_domain.DomainType:
          setattr(self, command.name, command)  # TODO remap here!
      elif key == 'DomainCommand':
        for command in pdl_domain.DomainCommand:
          setattr(self, command.name, command)  # TODO remap here!
      elif key == 'DomainEvent':
        for command in pdl_domain.DomainEvent:
          setattr(self, command.name, command)  # TODO remap here!
      else:
        self.key = getattr(pdl_domain, key)



class PDLFile(object):
  def __init__(self):
    self._pdl_version = None
    self._pdl_domains = None

  def ParseFileContents(self, cont):
    _, tree = BuildTreeFromFile(cont)
    self.ParseTree(tree)

  def ParseFilePath(self, loc):
    with open(loc, 'r') as f:
      self.ParseFileContents(f.read())

  def ParseTree(self, tree):
    pdl_contents = (PDLVersion|PDLDomain).Parse(tree)
    self._pdl_version = pdl_contents['PDLVersion'][0]
    self._pdl_domains = {
      dom.name: dom for dom in pdl_contents['PDLDomain']
    }

  def __getattr__(self, attr):
    if attr == 'version':
      return self._pdl_version
    return PDLDomainWrapper(self._pdl_domains[attr])




class Defaults(object):
  def __init__(self):
    self.src = '/usr/local/google/home/tmathmeyer/chromium/src'
    self.pdl = 'third_party/blink/renderer/core/inspector/browser_protocol.pdl'
    #chrsrc = '/home/tmathmeyer/git/devtools/devtools-frontend/'

  def Parse(self):
    result = PDLFile()
    result.ParseFilePath(os.path.join(self.src, self.pdl))
    return result


if __name__ == '__main__':
  pdl = Defaults().Parse()
