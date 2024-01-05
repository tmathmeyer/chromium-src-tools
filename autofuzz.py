#!/usr/bin/env python3

import apiclient
import httplib2
import sys

from oauth2client.file import Storage


PROJECT_URL = 'https://bugs.chromium.org/_ah/api/discovery/v1/apis'


def GetAuthorizedMonorailInterface():
  global PROJECT_URL
  storage = Storage('/chromium/custom_tooling/.oauth_creds')
  credentials = storage.get()
  http = credentials.authorize(httplib2.Http())
  return apiclient.discovery.build('monorail', 'v1',
    discoveryServiceUrl=f'{PROJECT_URL}/{{api}}/{{apiVersion}}/rest',
    http=http)


def CheckIssue(monorail, issue_id:int, project='chromium'):
  comments = monorail.issues().comments().list(
    projectId=project,
    issueId=issue_id,
    maxResults=1)
  print(comments)


def main():
  issue = sys.argv[1]
  monorail = GetAuthorizedMonorailInterface()
  CheckIssue(monorail, int(issue))


if __name__ == '__main__':
  main()
