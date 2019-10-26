
import git as _git
from git import git

def update_master():
  if git.status('--porcelain'):
    print('current branch is not in a clean state')
    return

  current_branch = git.branch('--show_current')

  git.checkout('master')
  git.pull('--rebase')
  _git.run('gclient', 'sync')
  git.checkout(current_branch)
  git.rebase('master')