# libgerrit.py provides tools for RO access to gerrit & the CQ.


import json
import numbers
import re
import requests


CRREV_DETAIL_URL = 'https://chromium-review.googlesource.com/changes/{}/detail'
CRREV_COMMENTS_URL = 'https://chromium-review.googlesource.com/changes/{}/comments'
CRREV_DETAIL_URL_O = 'https://chromium-review.googlesource.com/changes/{}/detail?O=16314'
PATCHSET_STATUS_URL = ('https://chromium-cq-status.appspot.com/query/codereview'
                       '_hostname=chromium-review.googlesource.com/issue={}/'
                       'patchset={}')
BUILDBOT_URL_REGEX = re.compile(r'p/(\S+)/builders/(\S+)/(\S+)/([0-9]+)')
BUILDBOT_RPC_URL = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild'


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
      return None
    elif q.text[0:4] == ')]}\'':
      return JSON.FromObj(json.loads(q.text[5:]))
    else:
      return JSON.FromObj(json.loads(q.text))


def GetReviewDetail(crrev_id):
  """Get JSON representation of a cr."""
  return JSON.FromURL(CRREV_DETAIL_URL_O.format(crrev_id))


def GetCQStatus(crrev_id, patchset):
  """Get JSON data for a cq job."""
  return JSON.FromURL(PATCHSET_STATUS_URL.format(crrev_id, patchset))


def GetComments(crrev_id):
  return JSON.FromURL(CRREV_COMMENTS_URL.format(crrev_id))


def GetRedirectUrl(url):
  q = requests.get(url = url, allow_redirects=False)
  if q.status_code == 301:
    return q.headers['Location']
  raise ValueError(url)


# builtbots can be represented in a bunch of ways:
#  - buildbot(project, type, builder_name, build_number)
#  - buildbot(unique_build_number_url)
#  - buildbot(name_number_url)
# We need to support them all.
def GetBuildbotData(*args, **kwargs):
  if len(args) == 4:
    return _GetBuildbotData(*args, **kwargs)

  if len(args) != 1:
    raise ValueError('Only supports full args or url')

  url = str(args[0])
  if not url.startswith('http'):
    raise ValueError('Only supports full args or url')

  url_parts = url.split('/')
  if len(url_parts) == 5:
    url = GetRedirectUrl(url)

  parsed = BUILDBOT_URL_REGEX.search(url)
  if not parsed:
    raise ValueError(f'URL {url} was invalid')

  groups = parsed.groups()
  return _GetBuildbotData(groups[0], groups[1], groups[2], groups[3], **kwargs)

def _GetBuildbotData(project, bucket, builder, buildNumber, fields='steps,id'):
  rpc_payload = {
    'builder': {
      'project': project,
      'bucket': bucket,
      'builder': builder,
    },
    'buildNumber': buildNumber,
    'fields': fields
  }
  q = requests.post(
    url = BUILDBOT_RPC_URL,
    data = json.dumps(rpc_payload),
    headers = {
      'content-type': 'application/json',
      'accept': 'application/json',
    })
  if q.status_code != 200:
    raise ValueError('Couldn\'t make RPC for buildbot data')
  return JSON.FromObj(json.loads(q.text[5:]))



