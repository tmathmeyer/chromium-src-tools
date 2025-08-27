

#!/usr/bin/env python3

import os
from lib import colors, libargs, librun, libgit


COMMAND = libargs.ArgumentParser()


@COMMAND
def fetch(url:str, segments:int=None):
  command = f'curl "{url}"'
  hls_manifest_content = librun.OutputOrError(command).strip().split('\n')
  if hls_manifest_content[0] != '#EXTM3U':
    raise Exception(f'First line is not EXTM3U, is {hls_manifest_content[0]}')
  next_line_is_segment = False
  segment_index = 0

  root,manifest_name = url[:url.index('.m3u8')].rsplit('/', 1)


  for line in hls_manifest_content:
    if line.startswith('#EXT-X-MEDIA-SEQUENCE'):
      segment_index = int(line[22:])
    elif line.startswith('#EXTINF'):
      next_line_is_segment = True
    elif next_line_is_segment:
      next_line_is_segment = False
      segment = root + '/' + line
      os.system(f'wget -O {segment_index}.ts "{segment}"')
      segment_index += 1



if __name__ == '__main__':
  COMMAND.eval()
