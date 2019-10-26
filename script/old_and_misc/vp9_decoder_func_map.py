#!/usr/bin/python

# Renders the call graph for the vp9 decoder.

import re
import multiparse
import pygraphviz as pgv

vp9 = '/usr/local/google/home/tmathmeyer/chromium/src/media/gpu/vp9_decoder'

vp9_accel_pub_methods = [
  'CreateVP9Picture',
  'SubmitDecode',
  'OutputPicture',
  'IsFrameContextRequired',
  'GetFrameContext',
]

vp9_decoder_methods = [
  'RefreshReferenceFrames',
  'DecodeAndOutputPicture',
  'UpdateFrameContext',
  'SetStream',
  'Flush',
  'Reset',
  'Decode',
  'GetPicSize',
  'GetRequiredNumOfPictures',
  'GetNumReferenceFrames',
]

def GetMethodFinders():
  def itr():
    for m in vp9_decoder_methods:
      @multiparse.object_header(r'(\S+)\s+VP9Decoder::({})'.format(m))
      class VP9DecoderParser(object):
        def __init__(self, ret, method):
          self._method = method
          self._ret = ret
          self._accelerator_calls = []
        def __repr__(self):
          return '{}:{}'.format(self._method, self._accelerator_calls)
        @multiparse.matches(r'accelerator_->([a-zA-Z]+)')
        def add_accelerator_call(self, afn):
          self._accelerator_calls.append(afn)
      VP9DecoderParser.__name__ = 'VP9DecoderParser_{}'.format(m)
      yield VP9DecoderParser
  return list(itr())

def parse_cc(f_name, classes):
  def itr():
    with open(f_name + '.cc') as f:
      f_cont = f.read()
      for finder in classes:
        yield from multiparse.parse_objects(f_cont, finder, False)
  return list(itr())





















def main():
  funcs = parse_cc(vp9, GetMethodFinders())
  print(funcs)

if __name__ == '__main__':
  main()
