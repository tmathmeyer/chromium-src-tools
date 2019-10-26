import subprocess


def run(*cmd):
  result = subprocess.run(list(cmd), stdout=subprocess.PIPE)
  return result.stdout.decode('utf-8').strip()


class Executable(object):
  def __init__(self, *cmd):
    self._args = list(cmd)

  def __getattr__(self, val):
    return Executable(*self._args, 'val')

  def __call__(self, *flags):
    return run(*self._args, *flags)


class Git(Executable):
  def __init__(self):
    super().__init__('git')


git = Git()
