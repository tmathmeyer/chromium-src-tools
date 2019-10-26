
BLACK  = '0'
RED    = '1'
GREEN  = '2'
YELLOW = '3'
PURPLE = '5'

def Color(fg=None, bg=None):
  if fg and bg:
    return f'\033[3{fg};4{bg}m'
  if fg:
    return f'\033[3{fg}m'
  if bg:
    return f'\033[4{bg}m'
  return '\033[0m'