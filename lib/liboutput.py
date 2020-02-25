
from collections import namedtuple as nt


CharSet = nt('CharSet', ['vstem', 'branch', 'lastbranch', 'indent'])


DEFAULT_CHARSET = CharSet('│', '├', '└', '─')
BOLD_BOX_CHARACTERS = CharSet('┃', '┣', '┗', '━')
ASCII_ONLY = CharSet('|', '|', '`', '-')


def PrintTree(tree, render=str, child_iterator=None, charset=DEFAULT_CHARSET,
                    output_function=lambda l,_:print(l)):
  SPACES = ' ' * len(charset.indent)
  def _print_internal2(_tree, substr, stemmed=True, last=False):
    children = list(child_iterator(_tree) if child_iterator else _tree.children)
    indent = substr
    if stemmed:
      indent += SPACES
      indent += (charset.lastbranch if last else charset.branch)
      indent += charset.indent
    output_function(indent + render(_tree), _tree)

    if stemmed:
      substr += SPACES
      substr += (' ' if last else charset.vstem)

    for child in children[:-1]:
      _print_internal2(child, substr)

    if children:
      _print_internal2(children[-1], substr, True, True)

  _print_internal2(tree, '', False)


def RenderOnNCurses(window, fn, colorizer, *args, **kwargs):
  class printfn(object):
    def __init__(self):
      self.lineno = 0
    def __call__(self, line, tree):
      window.WriteString(1, self.lineno, line, colorizer(tree))
      self.lineno += 1
  fn(*args, **kwargs, output_function=printfn())
