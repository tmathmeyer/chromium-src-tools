
import os
import sys
import tempfile


CMD_TEMPLATE = 'clang++ --emit-llvm -S {} -o {} -I{} -I{}'


def get_include_template():
  definclude = os.path.join(os.environ['CHROMIUM_ROOT'], 'chromium-git', 'src')
  mockinclude = os.path.join(os.environ['CHROMIUM_ROOT'], 'mockheaders')
  return CMD_TEMPLATE.format('{}', '{}', definclude, mockinclude)


def get_gen_command():
  if len(sys.argv) < 3:
    raise ValueError('missing arguments')
  input_file = sys.argv[1]
  output_file = tempfile.mkstemp()
  return output_file, get_include_template().format(input_file, output_file)


def 