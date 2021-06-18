
import collections
import curses
import queue
import threading
import time


KILLKEY = 27
ALIVE = False


def SendKillKey():
  if ALIVE:
    curses.ungetch(KILLKEY)


def SetKillKey(killkey):
  global KILLKEY
  KILLKEY = killkey


class Event(object):
  def __init__(self, cls):
    self.etype = cls
  def GetType(self):
    return self.etype


class EndedEvent(Event):
  def __init__(self, error=None):
    super().__init__(EndedEvent)
    self._error = error
  def GetError(self):
    return self._error


class RepaintEvent(Event):
  def __init__(self, graphics):
    super().__init__(RepaintEvent)
    self._graphics = graphics
  def GetGraphics(self):
    return self._graphics


class KeyEvent(Event):
  def __init__(self, key):
    super().__init__(KeyEvent)
    self._key = key
  def GetKey(self):
    return self._key


class Component():
  __slots__ = ('_parent')

  def __init__(self):
    self._parent = None

  def _OnReparent(self, parent):
    self._parent = parent

  def PaintComponent(self, graphics):
    pass

  def Repaint(self):
    if self._parent:
      self._parent.Repaint()


class ColorProxy():
  ColorPair = collections.namedtuple('ColorPair', ['fg', 'bg'])

  def __init__(self):
    self._mapping = {}
    self._pair = ColorProxy.ColorPair(None, None)

  def SetForground(self, fg):
    self._pair = ColorProxy.ColorPair(fg, self._pair.bg)

  def SetBackground(self, bg):
    self._pair = ColorProxy.ColorPair(self._pair.fg, bg)

  def Query(self):
    if self._pair in self._mapping:
      return self._mapping.get(self._pair)

    if self._pair.fg is None and self._pair.bg is None:
      return curses.color_pair(0)

    fg = self._pair.fg
    bg = self._pair.bg
    if fg == None:
      fg = 0
    if bg == None:
      bg = 0
    if type(fg) is str:
      fg = getattr(curses, f'COLOR_{fg}')
    if type(bg) is str:
      bg = getattr(curses, f'COLOR_{bg}')
    pairno = len(self._mapping)+1
    curses.init_pair(pairno, fg, bg)
    color = curses.color_pair(pairno)
    self._mapping[self._pair] = color
    return color


class Graphics():
  __slots__ = ('_w', '_h', '_offsetX', '_offsetY', '_context', '_window')
  def __init__(self, w, h, offset_x, offset_y, context, window):
    self._w = w
    self._h = h
    self._offsetX = offset_x
    self._offsetY = offset_y
    self._context = context
    self._window = window

  def Width(self):
    return self._w

  def Height(self):
    return self._h

  def GetChild(self, offset_x, offset_y, width, height):
    assert offset_x + width <= self.Width()
    assert offset_y + height <= self.Height()
    return Graphics(width, height,
      self._offsetX + offset_x, self._offsetY + offset_y,
      self._context, self._window)

  def WriteString(self, x, y, string):
    try:
      self._window.addstr(
        y+self._offsetY, x+self._offsetX, string, self._context.colors.Query())
    except:
      raise ValueError(f'Failed to write "{string}" at {(y+self._offsetY, x+self._offsetX)}')

  def SetForground(self, colorstr):
    self._context.colors.SetForground(colorstr)

  def SetBackground(self, colorstr):
    self._context.colors.SetBackground(colorstr)

  def ResetColor(self):
    self._context.colors.SetForground(None)
    self._context.colors.SetBackground(None)


class Panel(Component):
  __slots__ = ('_layout', '_children')

  def __init__(self, layout, *panels):
    super().__init__()
    self._layout = layout
    self._children = list(panels)

  def PaintComponent(self, graphics):
    self._layout.Render(graphics, self._children)

  def AddComponent(self, panel):
    self._children.append(panel)
    panel._OnReparent(self)


class Layout():
  def Render(self, graphics, components):
    raise NotImplementedError()


class Terminal(Panel):
  __slots__ = ('_screen', '_key_thread', '_event_thread',
               '_event_queue', '_ended_event', '_colors')

  def __init__(self, layout):
    super().__init__(layout)
    self._key_thread = None
    self._screen = None
    self._event_thread = None
    self._event_queue = None
    self._ended_event = None

  def Repaint(self):
    if self._screen:
      self._OnTerminalWindowSizeChange()

  def _MakeWindowGraphics(self, width, height):
    context = collections.namedtuple('ctx', ['colors'])(self._colors)
    return Graphics(width, height, 0, 0, context, self._screen)

  def _StartKeyThread(self):
    self._key_thread = threading.Thread(target=self._ListenKeysPress)
    self._key_thread.start() 

  def _ListenKeysPress(self):
    try:
      while True:
        inp = self._screen.getch()
        if inp != curses.ERR:
          print(inp)
        if inp == curses.KEY_RESIZE:
          self.Repaint()
        elif inp == KILLKEY:
          self._event_queue.put(EndedEvent())
          return
        elif inp == curses.ERR:
          continue
        else:
          self._event_queue.put(KeyEvent(inp))
    except Exception as e:
      self._event_queue.put(EndedEvent(e))
      return

  def _StartEventThread(self):
    self._event_queue = queue.Queue()
    self._event_thread = threading.Thread(target=self._EventLoop)
    self._event_thread.start() 

  def _EventLoop(self):
    try:
      while True:
        event = self._event_queue.get()
        if event.GetType() == EndedEvent:
          self._ended_event = event
          return
        if event.GetType() == RepaintEvent:
          pass
          self.PaintComponent(event.GetGraphics())
        if event.GetType() == KeyEvent:
          pass
    except Exception as e:
      self._ended_event = EndedEvent(e)
      return

  def _SetUpCurses(self):
    self._screen = curses.initscr()
    curses.noecho()
    curses.cbreak()
    self._screen.keypad(True)
    self._screen.timeout(100)
    self._colors = ColorProxy()
    curses.start_color()
    curses.use_default_colors()

  def _OnTerminalWindowSizeChange(self):
    y, x = self._screen.getmaxyx()
    self._screen.resize(y, x)
    self._event_queue.put(RepaintEvent(self._MakeWindowGraphics(x-1, y-1)))

  def _AwaitFinished(self):
    self._event_thread.join()
    SendKillKey()
    self._key_thread.join()
    curses.nocbreak()
    self._screen.keypad(False)
    curses.echo()
    curses.endwin()

    assert self._ended_event is not None
    if exception := self._ended_event.GetError():
      raise exception

  def Start(self):
    self._SetUpCurses()
    self._StartEventThread()
    self._StartKeyThread()
    global ALIVE
    ALIVE = True
    self._OnTerminalWindowSizeChange()
    self._AwaitFinished()


class ColumnLayout(Layout):
  def Render(self, graphics, components):
    if not components:
      return
    width = int(graphics.Width() / len(components))
    remainder = graphics.Width() - (width * len(components))
    offset = 0
    for component in components:
      subwidth = width
      if remainder:
        remainder -= 1
        subwidth += 1
      component.PaintComponent(
        graphics.GetChild(offset, 0, subwidth, graphics.Height()))
      offset += subwidth


class RowLayout(Layout):
  def Render(self, graphics, components):
    if not components:
      return
    height = int(graphics.Height() / len(components))
    remainder = graphics.Height() - (height * len(components))
    offset = 0
    for component in components:
      subheight = height
      if remainder:
        remainder -= 1
        subheight += 1
      component.PaintComponent(
        graphics.GetChild(0, offset, graphics.Width(), subheight))
      offset += subheight


class BorderLayout(Layout):
  def _vline(self, graphics, x, ys, dist):
    for y in range(dist):
      graphics.WriteString(x, ys+y, "┃")

  def _hline(self, graphics, y, xs, dist):
    for x in range(dist):
      graphics.WriteString(xs+x, y, "━")

  def Render(self, graphics, components):
    assert len(components) <= 1
    w = graphics.Width()
    h = graphics.Height()
    if w == 0 or h == 0:
      return
    if w == 1 and h == 1:
      graphics.WriteString(0, 0, "╋")
      return
    if w == 1:
      self._vline(graphics, 0, 0, h)
      return
    if w == 1:
      self._hline(graphics, 0, 0, w)
      return
    graphics.WriteString(0, 0, "┏")
    graphics.WriteString(w-1, 0, "┓")
    graphics.WriteString(w-1, h-1, "┛")
    graphics.WriteString(0, h-1, "┗")
    self._hline(graphics, 0, 1, w-2)
    self._vline(graphics, w-1, 1, h-2)
    self._hline(graphics, h-1, 1, w-2)
    self._vline(graphics, 0, 1, h-2)
    
    for component in components:
      component.PaintComponent(
        graphics.GetChild(1, 1, w-2, h-2))


class BorderBox(Panel):
  def __init__(self, layout):
    super().__init__(BorderLayout())
    self._interior = Panel(layout)
    super().AddComponent(self._interior)

  def AddComponent(self, panel):
    self._interior.AddComponent(panel)
