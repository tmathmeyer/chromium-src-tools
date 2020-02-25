
import abc
import curses
import time
import queue
import threading


class Window(object, metaclass=abc.ABCMeta):
  __slots__ = ('_window', '_selected')

  def __init__(self, window):
    self._window = window
    self._selected = False

  @abc.abstractmethod
  def Repaint(self, context):
    pass

  @abc.abstractmethod
  def Redecorate(self):
    pass

  @abc.abstractmethod
  def Width(self):
    pass

  @abc.abstractmethod
  def Height(self):
    pass

  @abc.abstractmethod
  def Resize(self, x, y, w, h):
    pass

  def OnKey(self, keycode):
    return False

  def Paint(self, context):
    self._window.clear()
    try:
      self.Repaint(context)
    except Exception as e:
      self.WriteString(0, 0, str(e))
    self.Redecorate()

  def WriteString(self, x, y, string, *args):
    try:
      self._window.addstr(y, x, string, *args)
    except:
      raise ValueError(f'Cant write string to ({x}, {y}) in window size=({self.Width()}, {self.Height()})')

  def SetSelected(self, selected):
    self._selected = selected


class NormalWindow(Window, metaclass=abc.ABCMeta):
  __slots__ = ('bordered', 'width', 'height')

  def __init__(self, bordered=False):
    super().__init__(curses.newwin(0, 0, 0, 0))
    self.bordered = bordered
    self.width = 0
    self.height = 0

  def Redecorate(self):
    if self.bordered:
      self._window.border()
    self._window.refresh()

  def Resize(self, x, y, w, h):
    self._window.resize(h, w)
    self._window.mvwin(y, x)
    self.width = w
    self.height = h

  def Width(self):
    return self.width

  def Height(self):
    return self.height


class ScrollWindow(Window, metaclass=abc.ABCMeta):
  __slots__ = ('frame_x', 'frame_y', 'frame_w', 'frame_h',
               'scroll_offset_y', 'realheight', 'upkey', 'downkey')

  def __init__(self, up=None, down=None):
    super().__init__(curses.newpad(1, 1))
    self.scroll_offset_y = 0
    self.frame_x = 0
    self.frame_y = 0
    self.frame_w = 0
    self.frame_h = 0
    self.realheight = 1
    self.upkey = ord(up)
    self.downkey = ord(down)

  @classmethod
  def ConvertToKeycode(cls, letter):
    if letter == 'j':
      return 106
    if letter == 'k':
      return 107
    if letter == None:
      return 0

  def Redecorate(self):
    self._window.refresh(
      self.scroll_offset_y, 0,
      self.frame_y, self.frame_x,
      self.frame_h+self.frame_y, self.frame_w+self.frame_x)

  def Resize(self, x, y, w, h):
    self.frame_x = x
    self.frame_y = y
    self.frame_w = w
    self.frame_h = h
    self.realheight = max(self.realheight, h)
    self._window.resize(self.realheight, w)

  def Expand(self, delta):
    self.SetHeight(delta + self.realheight)

  def SetHeight(self, newheight):
    self.realheight = min(newheight, 127)
    self.realheight = max(self.realheight, self.frame_h)
    self._window.resize(self.realheight, self.frame_w)

  def Width(self):
    return self.frame_w

  def Height(self):
    return self.realheight

  def OnKey(self, keycode):
    if keycode == self.upkey:
      self.scroll_offset_y = max(self.scroll_offset_y-1, 0)
      return True
    if keycode == self.downkey:
      self.scroll_offset_y = min(self.scroll_offset_y+1, self.frame_h-1)
      return True
    return False


class TerminalWindowArea(object):
  __slots__ = ('width', 'height', 'x', 'y')

  def __init__(self, x, y, width, height):
    self.x = x
    self.y = y
    self.width = width
    self.height = height

  def __str__(self):
    return f'x={self.x} y={self.y} w={self.width} h={self.height}'

  def __repr__(self):
    return str(self)


def LayoutWindows(layout):
  rf = RenderField(TerminalWindowArea)
  for width, height, wintype in layout:
    yield (rf.AddWindow(width, height), wintype)


class Event(object):
  def __init__(self, cls):
    self.etype = cls

  def GetType(self):
    return self.etype


class EndedEvent(Event):
  def __init__(self):
    super().__init__(EndedEvent)


class KeyEvent(Event):
  def __init__(self, keycode):
    super().__init__(KeyEvent)
    self.keycode = keycode


class ResizeEvent(Event):
  def __init__(self, height, width):
    super().__init__(ResizeEvent)
    self.width = width
    self.height = height

  def Width(self):
    return self.width

  def Height(self):
    return self.height


class StartupEvent(Event):
  def __init__(self, height, width):
    super().__init__(StartupEvent)
    self.width = width
    self.height = height

  def Width(self):
    return self.width

  def Height(self):
    return self.height


class RepaintRequestedEvent(Event):
  def __init__(self, windows):
    super().__init__(RepaintRequestedEvent)
    self.windows = windows


class Colorizer(object):
  def __init__(self):
    self.colors = {}
    self.next_idx = 1

  def GetColor(self, fg=None, bg=None):
    if fg == None and bg == None:
      return curses.color_pair(0)

    if fg == None:
      fg = 0

    if bg == None:
      bg = 0

    if type(fg) is str:
      fg = getattr(curses, f'COLOR_{fg}')

    if type(bg) is str:
      bg = getattr(curses, f'COLOR_{bg}')

    fgmap = self.colors.get(fg, None)
    if not fgmap:
      self.colors[fg] = {}
      fgmap = self.colors[fg]

    bgmap = fgmap.get(bg, None)
    if not bgmap:
      fgmap[bg] = self.next_idx
      bgmap = self.next_idx
      curses.init_pair(self.next_idx, fg, bg)
      self.next_idx += 1

    return curses.color_pair(bgmap)


class Terminal(object):
  __slots__ = ('windows', 'screen', 'keythread', 'eventqueue',
               'repaintqueue', 'repaintthread',
               'windowsCreated', 'context', 'finished')

  def __init__(self, layout, context):
    self.windows = list(LayoutWindows(layout))
    self.context = context
    self.context.terminal = self
    self.windowsCreated = False
    self.eventqueue = queue.Queue()
    self.repaintqueue = queue.Queue()

    self.finished = False

  def Start(self):
    self.eventqueue.put(StartupEvent(*self.screen.getmaxyx()))

  def SetupColors(self):
    curses.start_color()
    curses.use_default_colors()
    self.context.colors = Colorizer()

  def __enter__(self):
    self.screen = curses.initscr()
    self.SetupColors()
    curses.noecho()
    curses.cbreak()
    self.screen.keypad(True)
    self.startKeyListenerThread()
    return self

  def __exit__(self, exc_type, exc_val, exc_tb):
    self.finished = True
    curses.ungetch(27)
    self.joinKeyListenerThread()
    curses.nocbreak()
    self.screen.keypad(False)
    curses.echo()
    curses.endwin()

  def WaitUntilEnded(self):
    while True:
      event = self.eventqueue.get()
      if event.GetType() == ResizeEvent:
        self.ResizeWindows(event.Width(), event.Height())
      elif event.GetType() == StartupEvent:
        self.ResizeWindows(event.Width(), event.Height())
        self.PaintWindows()
      elif event.GetType() == EndedEvent:
        self.repaintqueue.put(event)
        return
      elif event.GetType() == KeyEvent:
        self.PassKey(event.keycode)
      elif event.GetType() == RepaintRequestedEvent:
        self.repaintqueue.put(event)

  def _RepaintInternal(self, event):
    self.screen.refresh()
    if event.windows:
      for win in event.windows:
        win.Paint(self.context)
    else:
      for _, win in self.windows:
        win.Paint(self.context)

  def _RepaintThreadInternal(self):
    while True:
      event = self.repaintqueue.get()
      with self.repaintqueue.mutex:
        self.repaintqueue.queue.clear()
      if event.GetType() == EndedEvent:
        return
      if event.GetType() == RepaintRequestedEvent:
        self._RepaintInternal(event)

  def PaintWindows(self):
    if not self.finished:
      self.eventqueue.put(RepaintRequestedEvent(None))

  def PaintWindow(self, window):
    if not self.finished:
      self.eventqueue.put(RepaintRequestedEvent([window]))

  def PassKey(self, keycode):
    if not self.finished:
      windows = []
      for _, win in self.windows:
        if win.OnKey(keycode):
          windows.append(win)
      if windows:
        self.eventqueue.put(RepaintRequestedEvent(windows))

  def startKeyListenerThread(self):
    self.keythread = threading.Thread(target=self.KeyListener)
    self.repaintthread = threading.Thread(target=self._RepaintThreadInternal)
    self.keythread.start()
    self.repaintthread.start()

  def joinKeyListenerThread(self):
    self.keythread.join()
    self.repaintthread.join()

  def KeyListener(self):
    while True:
      inp = self.screen.getch()
      if inp == curses.KEY_RESIZE:
        self.eventqueue.put(ResizeEvent(*self.screen.getmaxyx()))
      elif inp == 27:
        self.eventqueue.put(EndedEvent())
        return
      else:
        self.eventqueue.put(KeyEvent(inp))

  def ResizeWindows(self, width, height):
    if not self.windowsCreated and not self.finished:
      self.windows = [(area, win()) for (area, win) in self.windows]
      self.windowsCreated = True
      for _, win in self.windows:
        win.SetSelected(True)
        break

    #curses.resizeterm(height, width)
    for area, win in self.windows:
      x = area.x.fixed + (width * area.x.ratio)
      y = area.y.fixed + (height * area.y.ratio)
      h = area.height.fixed + (height * area.height.ratio)
      w = area.width.fixed + (width * area.width.ratio)
      h = min(h, height - y - 2)
      w = min(w, width - x - 2)
      win.Resize(x, y, w, h)
      self.screen.resize(h, w)
      win.Paint(self.context)


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
  def __init__(self, AreaType):
    self.bounds = list([[FIXED(0), FIXED(0)],
                        [RATIO(1), FIXED(0)],
                        [RATIO(1), RATIO(1)],
                        [FIXED(0), RATIO(1)]])
    self.AreaType = AreaType

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
        return self.AreaType(
          x=x, y=y,
          width=Location(0-x.fixed, 1),
          height=Location(0-y.fixed, 1))
      else:
        width = FIXED(self.bounds[1][0].fixed - self.bounds[0][0].fixed)
        height = RATIO(1)
        self.bounds = self.bounds[2:]
        self.bounds[-1][0] = self.bounds[0][0]
        self.CoalesceBounds()
        return self.AreaType(x=x,y=y,width=width,height=height)


    if width=='...' and self.isFixed(height):
      height = FIXED(int(height))
      x,y = self.bounds[0]
      potentialY = self.bounds[0][1] + height
      self.bounds[0][1] = potentialY
      self.bounds[1][1] = potentialY
      w = self.bounds[1][0]
      self.CoalesceBounds()
      return self.AreaType(x=x, y=y, width=w, height=height)

    if self.isFixed(width) and height=='...':
      width = FIXED(int(width))
      x,y = self.bounds[0]
      if len(self.bounds) != 4: # Any non-rectangular shape just handle easily
        return self.AddWindow('...', '...')
      self.bounds[0][0] = self.bounds[0][0]+width
      self.bounds[-1][0] = self.bounds[-1][0]+width
      self.CoalesceBounds()
      return self.AreaType(x=x, y=y, width=width, height=RATIO(1))


    if self.isFixed(width) and self.isFixed(height):
      width = FIXED(int(width))
      height = FIXED(int(height))
      upper_left = self.bounds[0]
      upper_right = self.bounds[1]
      self.bounds = ([[upper_left[0]+width, upper_left[1]]] +
                     self.bounds[1:] +
                     [[upper_left[0], upper_left[1]+height],
                      [upper_left[0]+width, upper_left[1]+height]])
      return self.AreaType(x=upper_left[0], y=upper_left[1], width=width, height=height)