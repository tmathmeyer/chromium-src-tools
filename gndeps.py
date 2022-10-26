
import pydot
import sys
from lib import librun


def GetOutputForTarget(target:str, outdir:str='out/Default') -> [str]:
  output = librun.OutputOrError(f'gn desc {outdir} {target} --tree')
  found_deps = False
  for line in output.split('\n'):
    if line.strip() == 'Dependency tree':
      found_deps = True
    elif found_deps and line.strip().startswith('//'):
      yield line
    else:
      found_deps = False


class Node():
  def __init__(self, name, parent):
    self._name = name
    self._parent = [parent]
    self._children = []
    self._mrp = parent

  def AddChild(self, child):
    self._children.append(child)
    child._AddParent(self)

  def Name(self):
    return self._name

  def Parent(self):
    return self._mrp

  def Children(self):
    yield from self._children

  def _AddParent(self, p):
    self._parent.append(p)
    self._mrp = p

  def Print(self, indent=0, flt=None):
    print(f'{" "*indent*2}{self._name}')
    for child in self._children:
      if (not flt) or flt(child):
        child.Print(indent+1, flt)


def ParseLinesIntoTree(target:str, lines:[str]):
  current = Node(target, None)
  current_indent_level = 0
  trees = {target:current}
  for line in lines:
    indent_level = (len(line) - len(line.lstrip())) / 2
    if indent_level > current_indent_level:
      assert (indent_level - current_indent_level) == 1
      if line.strip().endswith('...'):
        child = trees[line.strip()[:-3]]
      else:
        child = Node(line.strip(), current)
      #print(f'Adding child {child.Name()} to {current.Name()}')
      current.AddChild(child)
      trees[child.Name()] = child
      current = child
      current_indent_level = indent_level
      #print('')
    else:
      #print(f'backing up to find parent! ({line.strip()})')
      while indent_level <= current_indent_level:
        #print(f'current node = {current.Name()}')
        current = current.Parent()
        current_indent_level -= 1
      #print(f'current node = {current.Name()}')
      if line.strip().endswith('...'):
        child = trees[line.strip()[:-3]]
      else:
        child = Node(line.strip(), current)
      #print(f'Adding child {child.Name()} to {current.Name()}')
      current.AddChild(child)
      trees[child.Name()] = child
      current = child
      current_indent_level = indent_level
      #print('')
  return trees[target], trees


def GenerateDOTRepr(trees, root, flt=None):
  graph = pydot.Dot("dependencies", graph_type="digraph")
  #for name, tree in trees.items():
  #  if (not flt) or flt(tree):
  #    graph.add_node(pydot.Node(name.strip(), label=name))

  drawn = set()
  def add2graph(node):
    if (not flt) or flt(node):
      for child in node.Children():
        if (not flt) or flt(child):
          arr = (node.Name().strip(), child.Name().strip())
          if arr not in drawn:
            graph.add_edge(pydot.Edge(arr[0], arr[1], color="blue"))
            drawn.add(arr)
          add2graph(child)
  add2graph(root)
  return graph




def main(target):
  root, tree = ParseLinesIntoTree(target, GetOutputForTarget(target))
  #root.Print(flt=lambda n:'media' in n.Name())
  graph = GenerateDOTRepr(tree, root, flt=lambda n:'media' in n.Name())
  graph.write_png("output.png")

  '''
  with open('/usr/local/google/home/tmathmeyer/Example.txt', 'r') as f:
    root, tree = ParseLinesIntoTree('//media/mojo/services:services', f.readlines())
    root.Print()
    graph = GenerateDOTRepr(tree)
    graph.write_png("output.png")
    #tree.Print(flt=lambda n:n.Name().startswith('//media'))
  '''

if __name__ == '__main__':
  main(*sys.argv[1:])
