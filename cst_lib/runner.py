
import subprocess


_DEBUG_MODE_ = False


def SetDebugMode():
  global _DEBUG_MODE_
  _DEBUG_MODE_ = True


def RunSimple(cmd: str) -> str:
  if _DEBUG_MODE_:
    print(cmd)
    return 'NO STDOUT - DEBUG MODE'
  else:
    result = subprocess.run(list(cmd.split()), stdout=subprocess.PIPE)
    return result.stdout.decode('utf-8').strip()