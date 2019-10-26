#!/usr/bin/python

# Renders the call graph for the h264 decoder.

import re
import multiparse
import pygraphviz as pgv

h264 = '/usr/local/google/home/tmathmeyer/chromium/src/media/gpu/h264_decoder'


class Method(object):
  def __init__(self, func_name):
    self._func_name = func_name
    self._calls_names = []

  def generate_graph_node(self, graph):
    graph.add_node(self._func_name, label=self._func_name,
      style='filled', shape='record')

  def generate_graph_edges(self, graph):
    for call in self._calls_names:
      graph.add_edge(self._func_name, call, arrowhead='empty')

  def __repr__(self):
    return self._func_name


class Functions(object):
  def __init__(self):
    self.methods = []

  @multiparse.matches(r'^\s*(\S*)\s+(\S*)\(')
  def addmethods(self, ftype, func):
    if '~' not in func and ftype != '//':
      self.methods.append(func)

  def generate_graph_node(self, graph):
    for method in self.methods:
      method.generate_graph_node(graph)

  def generate_graph_edges(self, graph):
    for method in self.methods:
      method.generate_graph_edges(graph)

  def __repr__(self):
    return str(self.methods)


def CreateClazz(methods):
  methodstr = '|'.join([str(method) for method in methods])
  header = r'\s*\S+\s+H264Decoder::({})\('.format(methodstr)
  call = r'\W({})\('.format(methodstr)

  @multiparse.object_header(header)
  @multiparse.object_footer(r'^}$')
  class FunctionFinder(object):
    def __init__(self, fn):
      self.fn = fn
      self.calls = []

    def __repr__(self):
      return self.fn

    @multiparse.matches(call, exclude_comments='//', exclude_strings='"')
    def addCall(self, fn):
      if fn != self.fn:
        self.calls.append(fn)

    def generate_graph_node(self, graph):
      graph.add_node(self.fn, label=self.fn, style='filled', shape='record')

    def generate_graph_edges(self, graph):
      for call in self.calls:
        graph.add_edge(self.fn, call, arrowhead='empty')

  return FunctionFinder






def parse_header(f_name):
  with open(f_name + '.h') as f:
    f_cont = f.read()
    return multiparse.parse_objects_no_header(f_cont, Functions)

def parse_cc(f_name, objtype):
  with open(f_name + '.cc') as f:
    f_cont = f.read()
    return multiparse.parse_objects(f_cont, objtype, delete_bodyless=False)


def main():
  graph = pgv.AGraph(directed=True, nodesep=2)
  objects = parse_header(h264)
  if not objects:
    print('Failed to parse header!')
    return

  funcs = parse_cc(h264, CreateClazz(objects[0].methods))

  for o in funcs:
    o.generate_graph_node(graph)

  for o in funcs:
    o.generate_graph_edges(graph)

  graph.layout(prog='dot')
  graph.draw('decoder_calls.jpg')

if __name__ == '__main__':
  main()
