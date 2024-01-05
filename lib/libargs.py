

import abc
import argparse
import inspect
import sys
import typing

from . import librun

ArgType = typing.TypeVar('ArgType')

class ArgComplete(metaclass=abc.ABCMeta):
  """Base class for types which have special completion rules"""
  def __init__(self, wrapped: ArgType):
    self.wrapped = wrapped

  @classmethod
  @abc.abstractmethod
  def getCompletionList(cls, stub: str) -> typing.Generator[str, None, None]:
    raise NotImplementedError()


class Directory(ArgComplete):
  """Auto-completion for directories."""
  @classmethod
  def getCompletionList(cls, stub:str) -> typing.Generator[str, None, None]:
    dirs = list(cls._getDirectories(stub))
    if len(dirs) == 1:
      yield dirs[0]
      yield dirs[0] + '/'  #TODO replace with os agnostic separator.
    else:
      yield from dirs

  @classmethod
  def _getDirectories(cls, stub:str) -> typing.Generator[str, None, None]:
    shell = '/bin/sh'
    if not os.path.exists(shell):
      return []
    if not os.path.islink(shell):
      return []

    cmd = f'compgen -o bashdefault -o default -o nospace -F _cd {stub}'
    result = librun.RunCommand(cmd)
    if result.statuscode:
      return []

    for line in result.stdout.split('\n'):
      f = line.decode().replace('\n', '').replace('//', '/')
      if os.path.isdir(f):
        yield f


class ArgumentParser(object):
  """Argument parsing class and auto-caller"""

  def __init__(self, complete=True):
    self._parser = argparse.ArgumentParser()
    self._methods = {}
    self._complete = complete

  def __call__(self, func) -> None:
    """Decorator call method - captures the function for call decisions."""
    methodname = func.__name__
    methodhelp = func.__doc__ or methodname
    methodargs = inspect.getfullargspec(func)[0]
    typespec = func.__annotations__

    self._methods[methodname] = {
      'func': func,
      'help': methodhelp.splitlines()[0],
      'args': {},
      'setup': []
    }
    self._setMethodParameters(func, self._methods[methodname])
    return func

  def _setMethodParameters(self, func, detail) -> None:
    def MakeCall(name, *args, **kwargs):
      return (name, args, kwargs)

    for arg, info in inspect.signature(func).parameters.items():
      argtype = info.annotation
      default = info.default
      action = 'store'
      argmap = detail['args']
      setup = detail['setup']

      if argtype == inspect.Parameter.empty:
        self._invalid_syntax(func, arg, 'type annotation')

      if argtype == bool:
        action = 'store_true'
        if default == inspect.Parameter.empty:
          self._invalid_syntax(func, arg, 'a default value')

      if default == inspect.Parameter.empty:
        argmap[arg] = argtype
        setup.append(MakeCall('add_argument', arg, type=argtype, action=action))
      elif argtype == bool:
        argmap['--'+arg] = None
        setup.append(MakeCall('add_argument', '--'+arg, default=default, action=action))
      else:
        argmap['--'+arg] = argtype
        setup.append(MakeCall('add_argument', '--'+arg, type=argtype, default=default))

  def _evaluateSetup(self) -> None:
    if len(self._methods) == 1:
      for name, args, kwargs in list(self._methods.values())[0]['setup']:
        getattr(self._parser, name)(*args, **kwargs)
    else:
      subparser = self._parser.add_subparsers(title='tasks')
      for methodname, methoddecl in self._methods.items():
        task = subparser.add_parser(methodname, help=methoddecl['help'])
        task.set_defaults(task=methodname)
        for name, args, kwargs in methoddecl['setup']:
          getattr(task, name)(*args, **kwargs)

  def _evaluateExecute(self):
    parsed_args = self._parser.parse_args()
    if len(self._methods) == 1:
      self._executeFunc(list(self._methods.values())[0], parsed_args)
    elif 'task' in parsed_args:
      self._executeFunc(self._methods[parsed_args.task], parsed_args)
    else:
      self._parser.print_help(sys.stderr)

  def _executeFunc(self, methoddecl, parsed_args):
    _args = {}
    for arg in inspect.signature(methoddecl['func']).parameters.keys():
      if hasattr(parsed_args, arg):
        _args[arg] = getattr(parsed_args, arg)
    methoddecl['func'](**_args)

  def eval(self):
    self._evaluateSetup()
    self._evaluateExecute()
