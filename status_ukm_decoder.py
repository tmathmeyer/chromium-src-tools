#!/usr/bin/env python3

import sys
import re


def StatusCodesExtractor(file:str, parse:str):
  groups = parse.split(' > ')
  brace_level = 0
  enum_entries = []
  def CouldMatch(ps, line):
    vt, vn = ps.split('.')
    seek = {
      's': 'struct',
      'e': 'enum',
      'ec': 'enum class',
    }[vt] + f' {vn}'
    return seek in line

  def ExtractEnumEntries(defls):
    for line in defls:
      line = line.strip()
      if not line or line.startswith('//'):
        continue
      cont = re.match(r'(\w+)\s+=\s+(\d+)', line)
      if cont:
        yield int(cont.groups()[1]), cont.groups()[0]

  with open(file) as f:
    for line in f.readlines():
      if brace_level and not groups:
        if '};' in line:
          brace_level = 0
          continue
        # We're inside the enum we're looking for!
        enum_entries.append(line)
      elif not brace_level and not groups:
        return dict(ExtractEnumEntries(enum_entries))
      elif CouldMatch(groups[0], line):
        groups = groups[1:]
        brace_level += 1
      elif brace_level and '};' in line:
        brace_level -= 1
  raise ValueError('Couldnt parse header!')


TYPEMAP = {
  'DecoderStatus': {
    'crc': 62537,
    'header': 'media/base/decoder_status.h',
    'parse': 's.DecoderStatusTraits > ec.Codes',
  },

  'PipelineStatus': {
    'crc': 15065,
    'header': 'media/base/pipeline_status.h',
    'parse': 'e.PipelineStatusCodes',
  }
}

def PrintStatusInfo(packed):
  packed = int(packed)
  group = packed & 0xFFFF
  code = (packed >> 16) & 0xFFFF
  extra_data = (packed >> 32) & 0xFFFFFFFF
  for st, inf in TYPEMAP.items():
    if inf['crc'] == group:
      codes = StatusCodesExtractor(inf['header'], inf['parse'])
      print(f'{st}::{codes[code]}')
      print('extra data: ')
      print(f'\t{extra_data}')
      return
  print(f'Unknown CRC: {group}')


def main(status_packed, root_cause_packed):
  print('Status:')
  PrintStatusInfo(status_packed)
  print('\nRootCause:')
  PrintStatusInfo(root_cause_packed)


if __name__ == '__main__':
  main(*sys.argv[1:])
