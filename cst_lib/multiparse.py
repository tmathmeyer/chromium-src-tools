
import abc
import re
from types import FunctionType


def unregex(str_or_regex_list):
  """Converts [regex|string] into a list of only strings.

  Args:
    str_or_regex_list: (List) A list which can contain either strings or
      regex match objects.

  Yields:
    For each element provided, if it is a string, the string is yielded,
    otherwise if the element is a regex match, then the group(0) is yielded.
  """
  for elem in str_or_regex_list:
    if isinstance(elem, basestring):
      yield elem
    else:
      yield elem.group(0)


def matches(*regexes, exclude_comments=None, exclude_strings=None):
  """Creates a decorator for populating an object.

  Args:
    *regexes: Multiple regex strings which if matched causes this function to be
      called with the match object.

  Returns:
    A decorator function which adds a matching_regexes property to the
      function
  """

  def decorator(func):
    func.match_regex = [re.compile(regex.replace(r'\h', '[a-fA-F0-9]'))
                        for regex in regexes]
    if exclude_strings:
      func.match_exclude_strings = exclude_strings
    if exclude_comments:
      func.match_exclude_comments = exclude_comments
    return func

  return decorator


def object_header(*regexes):
  """A decorator to tag a class constructor with a header regex to match."""
  return _class_prop(regexes, 'header')


def object_footer(*regexes):
  """A decorator to tag a class constructor with a footer regex to match."""
  return _class_prop(regexes, 'footer')


def _class_prop(regexes, regex_location):
  """Creates a decorator with a regex and what property to save it as.

  Args:
    regexes: ([str]) An array of regex strings which should be joined with |.
    regex_location: (str) The name of the property on the constructor to store
      the regex as.

  Returns:
    (Function) A decorator function which sets the regex as the named property.
  """

  def decorator(clazz):
    setattr(clazz, regex_location, re.compile('|'.join(regexes)))
    return clazz

  return decorator


def _object_line_search(line, object_obj):
  """Inserts matched elements into a object object.

  Args:
    line: (str) The line of log file to search in.
    object_obj: An object object to store results in.

  Returns:
    (bool) True if any of the regexes matched.
  """
  has_body = False
  for method in object_obj.__class__.__dict__.values():
    if isinstance(method, FunctionType) and hasattr(method, 'match_regex'):
      if hasattr(method, 'match_exclude_comments'):
        if method.match_exclude_comments in line:
          line = line[:line.index(method.match_exclude_comments)]
      if hasattr(method, 'match_exclude_strings'):
        line = line

      for regex in method.match_regex:
        search_result = re.search(regex, line)
        if search_result:
          method(object_obj, *search_result.groups())
          has_body = True

  return has_body


def parse_objects(log, objecttype, delete_bodyless=True):
  """Creates object objects from a logfile and a collection of regexs.

  Args:
    log: (str) The full log file contents as a single string.
    objecttype: (Constructor) A constructor for a object object.

  Returns:
    A list of object objects.
  """
  object_list = []
  current_object_object = None
  current_object_has_body = not delete_bodyless
  for line in log.splitlines():
    header = re.search(objecttype.header, line)
    # If we've found a new header, make a new object object and save/trash other.
    if header:
      if current_object_object and current_object_has_body:
        object_list.append(current_object_object)
      current_object_object = objecttype(*header.groups())
      current_object_has_body = not delete_bodyless

    # If we've found a footer, save/trash the current object.
    elif hasattr(objecttype, 'footer') and re.search(objecttype.footer, line):
      if current_object_object:
        if current_object_has_body:
          object_list.append(current_object_object)
        current_object_object = None
        current_object_has_body = not delete_bodyless

    # If we're in a object object, try to match the current line.
    if current_object_object:
      current_object_has_body = _object_line_search(
          line, current_object_object) or current_object_has_body

  if current_object_object and current_object_has_body:
    object_list.append(current_object_object)
  return object_list


def parse_objects_no_header(log, objecttype):
  """Creates object objects from a logfile with no header or footer.

  Args:
    log: (str) The full log file contents as a single string.
    objecttype: (Constructor) A constructor for a object object.

  Returns:
    A list of object objects.
  """
  object_object = objecttype()
  object_has_body = False
  for line in log.splitlines():
    object_has_body = _object_line_search(line, object_object) or object_has_body

  if object_has_body:
    return [object_object]

  return []

