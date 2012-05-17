# -*- coding: utf-8 -*-
from buildbot.scheduler import Scheduler
from twisted.python import log


class SVNScheduler(Scheduler):
    """Extend Scheduler to allow multiple projects"""

    def __init__(self, name, builderNames, repository):
        """Override Scheduler.__init__
        Add a new parameter : repository
        """
        Scheduler.__init__(self, name, None, 120,
                           builderNames, fileIsImportant=None)
        self.repository = repository

    def addChange(self, change):
        """Call Scheduler.addChange only if the branch name (eg. project name
        in your case) is in the repository url"""
        if isinstance(change.branch, basestring):
            if self.repository.endswith(change.branch):
                self.branch = change.branch
                Scheduler.addChange(self, change)


class FixedScheduler(Scheduler):
    """ fix Scheduler to (somewhat) respect `branch=None` """

    def addChange(self, change):
        """ for some vcs, e.g. git, the default branch cannot be determined
            leading to "ignored off-branch changes" in the log.  this can be
            fixed by explicitly setting a branch, which is made a little
            clearer here """
        if not self.branch:
            log.msg('%s ignoring change due to unknown default branch. '
                    'please set one using `branch = ...`' % self)
        Scheduler.addChange(self, change)
