
import json
import numbers
import requests


class JSONError(Exception):
  def __init__(self, msg):
    super().__init__(msg)

class JSON(object):
  def __init__(self, json_obj):
    self.json_obj = json_obj
    self.type = None
    if type(self.json_obj) == str:
      self.type = 'str'
    elif type(self.json_obj) == list:
      self.type = 'list'
    elif type(self.json_obj) == dict:
      self.type = 'dict'
    elif isinstance(self.json_obj, numbers.Number):
      self.type = 'int'

  def __bool__(self):
    return bool(self.json_obj)

  def __getattr__(self, attr):
    try:
      if self.type == 'dict':
        return JSON.FromObj(self.json_obj.get(attr))
      if attr == 'RAW':
        return self.json_obj
    except:
      raise JSONError(f'__getattr__({attr})')
    raise JSONError(f'__getattr__({attr})')

  def __getitem__(self, index):
    if self.type == 'list':
      return JSON.FromObj(self.json_obj[index])
    if self.type == 'dict':
      return JSON.FromObj(self.json_obj[index])
    raise JSONError(f'__getitem__({index})')

  def __repr__(self):
    return self.json_obj

  def __str__(self):
    return str(self.json_obj)

  def __iter__(self):
    if self.type == 'list':
      for index in self.json_obj:
        yield JSON.FromObj(index)
    elif self.type == 'dict':
      for index in self.json_obj.keys():
        yield index
    else:
      raise JSONError(f'__iter__({self.type})')

  @classmethod
  def FromObj(cls, obj):
    if type(obj) == list:
      return JSON(obj)
    elif type(obj) == dict:
      return JSON(obj)
    elif obj == None:
      return JSON(obj)
    else:
      return obj

  @classmethod
  def FromURL(cls, url):
    q = requests.get(url=url)
    if q.status_code != 200:
      raise ValueError(f'status code [{url}] = {q.status_code}')
      return None
    elif q.text[0:4] == ')]}\'':
      return JSON.FromObj(json.loads(q.text[5:]))
    else:
      return JSON.FromObj(json.loads(q.text))
