# libgerrit.py provides tools for RO access to gerrit & the CQ.


import json
import numbers
import re
import requests

from . import libjson


CRREV_DETAIL_URL = 'https://chromium-review.googlesource.com/changes/{}/detail'
CRREV_COMMENTS_URL = 'https://chromium-review.googlesource.com/changes/{}/comments'
CRREV_DETAIL_URL_O = 'https://chromium-review.googlesource.com/changes/{}/detail?O=16314'
PATCHSET_STATUS_URL = ('https://chromium-cq-status.appspot.com/query/codereview'
                       '_hostname=chromium-review.googlesource.com/issue={}/'
                       'patchset={}')
HOSTNAME_REGEX = re.compile(r'https://([a-zA-Z0-9\.\-]+)/.*')
BUILDBOT_URL_REGEX = re.compile(r'p/(\S+)/builders/(\S+)/(\S+)/([0-9]+)')
BUILDBOT_GENID_REGEX = re.compile(r'https://ci.chromium.org/b/([0-9]+)')
BUILDBOT_RPC_URL = 'https://cr-buildbucket.appspot.com/prpc/buildbucket.v2.Builds/GetBuild'


def GetReviewDetail(crrev_id):
  """Get JSON representation of a cr."""
  return libjson.JSON.FromURL(CRREV_DETAIL_URL_O.format(crrev_id))


def GetCQStatus(crrev_id, patchset):
  """Get JSON data for a cq job."""
  return libjson.JSON.FromURL(PATCHSET_STATUS_URL.format(crrev_id, patchset))


def GetComments(crrev_id):
  return libjson.JSON.FromURL(CRREV_COMMENTS_URL.format(crrev_id))


def GetRedirectUrl(url):
  q = requests.get(url = url, allow_redirects=False)
  if q.status_code == 301 or q.status_code == 302:
    return q.headers['Location']
  raise ValueError(f'{url} did not redirect (code={q.status_code})')

def GetHostname(url):
  hostname_match = HOSTNAME_REGEX.search(url)
  if not hostname_match:
     raise ValueError(f'couldnt extract hostname from {url}')
  return hostname_match.groups()[0]


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

  hostname = GetHostname(url)
  if hostname == 'cr-buildbucket.appspot.com':
    url = GetRedirectUrl(url)

  hostname = GetHostname(url)
  if hostname != 'ci.chromium.org':
    raise ValueError('Redirect didnt lead to a ci.chromium.org url')

  if BUILDBOT_GENID_REGEX.search(url):
    url = GetRedirectUrl(url)

  parsed = BUILDBOT_URL_REGEX.search(url)
  if not parsed:
    raise ValueError(f'URL {url} not matched by {BUILDBOT_URL_REGEX}')

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
  return libjson.JSON.FromObj(json.loads(q.text[5:]))



