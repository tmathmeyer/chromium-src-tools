#!/usr/bin/python

# Renders the box structure for the MP4 definitions by parsing the headers

import re
import multiparse
import pygraphviz as pgv

BOX_DEFS = '/usr/local/google/home/tmathmeyer/chromium/src/media/formats/mp4/box_definitions.h'
GENERIC_TYPE = re.compile(r'(\S+?)<(\S+)>')


@multiparse.object_header(r'struct\s+MEDIA_EXPORT\s+(\S+)\s+\:\s+Box\s+\{')
@multiparse.object_footer(r'\};')
class BoxStruct():

  def __init__(self, classname):
    self.classname = classname
    self.fields = []

  @multiparse.matches(r'(\S+)\s+(\S+);')
  def field(self, field_type, field_name):
    plurality = 1
    while('<' in field_type):
      outer, field_type = GENERIC_TYPE.match(field_type).groups()
      if 'vector' in outer:
        plurality = 2

    self.fields.append((field_type, plurality, field_name))

  def __repr__(self):
    return self.classname

  def generate_graph_node(self, graph):
    graph.add_node(self.classname, label=self.classname, style='filled', shape='record')

  def generate_graph_edges(self, types, graph):
    for field in self.fields:
      if field[0] in types:
        if field[1] == 1:
          graph.add_edge(self.classname, field[0], arrowhead='empty')
        else:
          graph.add_edge(self.classname, field[0], arrowhead='empty', color='red')


def parse_file(f_name):
  with open(f_name) as f:
    f_cont = f.read()
    return multiparse.parse_objects(f_cont, BoxStruct)

def main():
  graph = pgv.AGraph(directed=True, nodesep=2)
  objects = parse_file(BOX_DEFS)
  types = [o.classname for o in objects]
  for o in objects:
    o.generate_graph_node(graph)

  for o in objects:
    o.generate_graph_edges(types, graph)

  graph.layout(prog='dot')
  graph.draw('boxes.jpg')

if __name__ == '__main__':
  main()
