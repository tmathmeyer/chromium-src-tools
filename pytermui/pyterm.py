

import curses
import time


class Layout(object):
  def __init__(self, **windows):
    self.__dict__.update(windows)
    self.keys = list(windows.keys())


class Window(object):
  __slots__ = ('width', 'height', 'x', 'y', 'bordered', 'cursesWin', 'realdims')

  def __init__(self, x, y, width, height):
    self.width = width
    self.height = height
    self.x = x
    self.y = y
    self.bordered = False
    self.cursesWin = None
    self.realdims = (0, 0)

  def __str__(self):
    return f'{{{self.x}, {self.y}, {self.width}, {self.height}}}'

  def createWindow(self, rows, cols):
    if not self.cursesWin:
      x = self.x.fixed + cols * self.x.ratio
      y = self.y.fixed + rows * self.y.ratio
      height = min(self.height.fixed + rows * self.height.ratio + 1, rows - y)
      width = min(self.width.fixed + cols * self.width.ratio + 1, cols - x)
      self.cursesWin = curses.newwin(height, width, y, x)
      if self.bordered:
        self.cursesWin.border()
        self.realdims = (width-2, height-2)
      else:
        self.realdims = (width, height)

  def Width(self):
    return self.realdims[0]

  def Height(self):
    return self.realdims[1]

  def __getattr__(self, attr):
    return getattr(self.cursesWin, attr)



class TermWindow(object):
  __slots__ = ('screen', 'layout', 'windows')

  def __init__(self, layout):
    self.screen = []
    self.layout = layout
    self.windows = {}
    self.RenderLayout()

  def __enter__(self):
    self.screen = curses.initscr()
    curses.noecho()
    curses.cbreak()
    curses.start_color()
    curses.use_default_colors()
    self.screen.keypad(True)
    rows, cols = self.screen.getmaxyx()
    for name, win in self.windows.items():
      win.createWindow(rows, cols)
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    curses.nocbreak()
    self.screen.keypad(False)
    curses.echo()
    curses.endwin()

  def __getattr__(self, attr):
    try:
      return getattr(self.screen, attr)
    except:
      return self.windows[attr]

  def RenderLayout(self):
    rf = RenderField()
    for windowname in self.layout.keys:
      params = getattr(self.layout, windowname)
      resx,resy = params[0].split('x')
      self.windows[windowname] = rf.AddWindow(resx, resy)
      for attr in params[1:]:
        setattr(self.windows[windowname], attr, True)


class Location(object):
  def __init__(self, fixed, ratio):
    self.fixed = fixed
    self.ratio = ratio

  def __add__(self, other):
    return Location(self.fixed+other.fixed, self.ratio+other.ratio)

  def __eq__(self, other):
    return self.fixed == other.fixed and self.ratio == other.ratio

  def __repr__(self):
    return str(self)

  def __str__(self):
    return f'({self.fixed}+p{self.ratio})'

  def __lt__(self, o):
    if self.ratio == o.ratio:
      return self.fixed < o.fixed
    return self.ratio < o.ratio

  def __gt__(self, o):
    if self.ratio == o.ratio:
      return self.fixed > o.fixed
    return self.ratio > o.ratio

  def OOB(self):
    if self.ratio > 1:
      return True
    if self.ratio == 1 and self.fixed != 0:
      return True
    return False


def FIXED(i):
  return Location(i, 0)


def RATIO(i):
  return Location(0, i)


class RenderField(object):
  def __init__(self):
    self.bounds = list([[FIXED(0), FIXED(0)],
                        [RATIO(1), FIXED(0)],
                        [RATIO(1), RATIO(1)],
                        [FIXED(0), RATIO(1)]])

  def CoalesceBounds(self):
    newbounds = []
    if len(self.bounds) % 2 != 0:
      raise ValueError(f'Invalid Bounds: {self.bounds}')

    if len(self.bounds) == 2:
      if (self.bounds[0][0] != self.bounds[1][0]) and (self.bounds[0][1] != self.bounds[1][1]):
        raise ValueError(f'Invalid Bounds: {self.bounds}')
      self.bounds = []
      return

    for bound in self.bounds:
      if newbounds and (newbounds[-1] == bound):
        newbounds = newbounds[:-1]
      else:
        newbounds.append(bound)

    if len(self.bounds) != len(newbounds):
      self.bounds = newbounds
      self.CoalesceBounds()
    else:
      self.ResortBounds()

  def ResortBounds(self):
    upperleft = self.bounds[0]
    for b in self.bounds:
      if b[1] < upperleft[1]:
        upperleft = b
      elif b[1] == upperleft[1] and b[0] < upperleft[0]:
        upperleft = b
    if upperleft == self.bounds[0]:
      return
    else:
      oldorder = []
      newbeginning = []
      addto = oldorder
      for b in self.bounds:
        if b == upperleft:
          addto = newbeginning
        addto.append(b)
      self.bounds = newbeginning + oldorder

  def isFixed(self, v):
    try:
      int(v)
      return True
    except:
      return False

  def AddWindow(self, width, height):
    if not self.bounds:
      raise ValueError('Can\'t add a new window, screen is filled')
    if width=='...' and height=='...':
      # This is where the box starts
      x,y = self.bounds[0]
      if self.bounds[1][0].ratio == 1:
        # remove top two coords, second to last now points to third
        self.bounds = self.bounds[2:]
        # shift third X coord to position of last coord
        self.bounds[0][0] = self.bounds[-1][0]
        self.CoalesceBounds()
        return Window(x=x, y=y, width=RATIO(1), height=RATIO(1))
      else:
        width = FIXED(self.bounds[1][0].fixed - self.bounds[0][0].fixed)
        height = RATIO(1)
        self.bounds = self.bounds[2:]
        self.bounds[-1][0] = self.bounds[0][0]
        self.CoalesceBounds()
        return Window(x=x,y=y,width=width,height=height)


    if width=='...' and self.isFixed(height):
      height = FIXED(int(height))
      x,y = self.bounds[0]
      potentialY = self.bounds[0][1] + height
      self.bounds[0][1] = potentialY
      self.bounds[1][1] = potentialY
      w = self.bounds[1][0]
      self.CoalesceBounds()
      return Window(x=x, y=y, width=w, height=height)

    if self.isFixed(width) and height=='...':
      width = FIXED(int(width))
      x,y = self.bounds[0]
      if len(self.bounds) != 4: # Any non-rectangular shape just handle easily
        return self.AddWindow('...', '...')
      self.bounds[0][0] = self.bounds[0][0]+width
      self.bounds[-1][0] = self.bounds[-1][0]+width
      self.CoalesceBounds()
      return Window(x=x, y=y, width=width, height=RATIO(1))


    if self.isFixed(width) and self.isFixed(height):
      width = FIXED(int(width))
      height = FIXED(int(height))
      upper_left = self.bounds[0]
      upper_right = self.bounds[1]
      self.bounds = ([[upper_left[0]+width, upper_left[1]]] +
                     self.bounds[1:] +
                     [[upper_left[0], upper_left[1]+height],
                      [upper_left[0]+width, upper_left[1]+height]])
      return Window(x=upper_left[0], y=upper_left[1], width=width, height=height)