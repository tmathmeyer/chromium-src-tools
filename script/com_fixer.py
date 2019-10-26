
import collections
import os
import re
import subprocess

COM_PTR_STRING = 'Microsoft::WRL::ComPtr'
AG_COMMAND = 'ag {}'.format(COM_PTR_STRING).split(' ')


def get_ag_output():
  result = subprocess.run(AG_COMMAND, stdout=subprocess.PIPE)
  return result.stdout.decode('utf-8')

def culprits():
  regex = re.compile(r'(\S+):(\d+):\s+Microsoft::WRL::ComPtr<I(D3D11\S+)>')
  files = collections.defaultdict(set)
  for line in get_ag_output().split('\n'):
    found = regex.search(line)
    if found:
      filename, _, comtype = found.groups()
      files[filename].add(comtype)
  return dict(files)

def sedcmds():
  sedcmd = 'sed -i s/Microsoft::WRL::ComPtr\\<I{type}\\>/Com{type}/g {file}'
  comreplacements = set()
  for file, entries in culprits().items():
    for entry in entries:
      comreplacements.add(entry)
      yield sedcmd.format(type=entry, file=file)

  echocmd = 'echo using Com{type} = COM\\<I{type}\\>'
  for cr in comreplacements:
    yield echocmd.format(type=cr)


for sedcmd in sedcmds():
  os.system('{}'.format(sedcmd))