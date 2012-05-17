import os
from os.path import join

from collective.buildbot.scheduler import SVNScheduler, FixedScheduler
from buildbot.scheduler import Nightly, Periodic, Dependent, Scheduler
from buildbot.process import factory
from buildbot import steps
from buildbot.steps.python import PyFlakes
from buildbot.status import mail
from buildbot.status.builder import Results
from twisted.python import log

from collective.buildbot.utils import split_option

CRON_MAX_RANGE = {0: (60, 0), 1:(24, 0), 2:(31, 1), 3:(12, 1), 4:(7, 0)}.get

def cron_value_to_setting(value, max_range=24, min_range=0):
    """Convert a value in a cron setting to a value which can be
    understood by the Nightly scheduler.
    """
    try:
        if ',' in value:
            return map(int, value.split(','))
        elif value == '*':
            return value
        elif value.startswith('*/'):
            return range(min_range, max_range, int(value[2:]))
        return int(value)
    except ValueError:
        raise ValueError("Invalid cron value '%s'" % value)


def convert_cron_to_setting(cron):
    """Convert a cron-like will to valid settings for the Nightly scheduler.
    """
    cron_values = cron.split()
    if len(cron_values) != 5:
        raise ValueError("Invalid cron settings %s (too much values)" % cron)
    return [cron_value_to_setting(v, *CRON_MAX_RANGE(i))
            for i, v in enumerate(cron_values)]


s = factory.s

class FileChecker:

    def __init__(self, frags):
        self.frags = frags

    def __call__(self, change):
        for f in change.files:
            for frag in self.frags:
                if frag in f:
                    return True
        return False

class Project(object):
    """A builbot project::

        >>> from collective.buildbot.project import Project

    We need to test args::

        >>> config_opts = {'repository':'https://ingeniweb.svn.sourceforge.net/svnroot/ingeniweb/collective.buildbot/trunk',
        ...                'email_notification_sender':'gael@ingeniweb.com',
        ...                'email_notification_recipients':'gael@ingeniweb.com',
        ...                }
        >>> project = Project(**config_opts)

        >>> print project.repository
        https://ingeniweb.svn.sourceforge.net/svnroot/ingeniweb/collective.buildbot/trunk

        >>> print project.email_notification_sender
        gael@ingeniweb.com
        >>> print project.email_notification_recipients
        ['gael@ingeniweb.com']

    We can have multiple recipients::

        >>> config_opts['email_notification_recipients'] = 'gael@ingeniweb.com buildout@ingeniweb.com'
        >>> project = Project(**config_opts)
        >>> print project.email_notification_recipients
        ['gael@ingeniweb.com', 'buildout@ingeniweb.com']

        >>> config_opts['email_notification_recipients'] = '''gael@ingeniweb.com
        ...                                                   buildout@ingeniweb.com'''
        >>> project = Project(**config_opts)
        >>> print project.email_notification_recipients
        ['gael@ingeniweb.com', 'buildout@ingeniweb.com']

    Please note that .cfg files likely contain dashes (e.g. `-`) that are transformed into
    underscored (e.g. `_`).
    """

    def __init__(self, **options):
        self.name = options.get('name')

        self.mail_host = options.get('mail_host', 'localhost')
        self.email_notification_sender = options.get('email_notification_sender','').strip()
        self.email_notification_recipients = options.get('email_notification_recipients', '').split()
        self.mail_mode = options.get('mail_mode', 'failing')
        self.mail_lookup = options.get('mail_lookup', None)
        # message formatter is later used as a named arg for MailNotifier
        # If message_formatter is None, it uses the internal one
        self.message_formatter = options.get('email_zope_test_style', False) \
            and self.messageFormatter or None

        self.slave_names =  options.get('slave_names', '').split()
        self.vcs = options.get('vcs', 'svn')
        self.vcs_mode = options.get('vcs_mode', 'update')
        self.vcs_retry = (10, 3)
        self.always_use_latest = (
            options.get('always_use_latest', '').strip().lower() in
            ('yes', 'true', 'y') or False)

        d_timeout = options.get('timeout', '3600').strip()
        self.timeout = int(d_timeout)
        self.build_timeout = int(options.get('build_timeout', d_timeout).strip())
        self.test_timeout = int(options.get('test_timeout', d_timeout).strip())

        self.build_sequence = split_option(options, 'build_sequence')

        self.test_sequence = split_option(options, 'test_sequence')
        if not self.test_sequence:
            self.test_sequence = [join('bin', 'test')]

        self.dependencies = split_option(options, 'dependencies')
        self.repository = options.get('repository', '')
        self.branch = options.get('branch', '')
        self.options = options
        self.schedulers = []
        self.username, self.password = self._get_login(self.repository)

    def _get_login(self, repository):
        """gets an option in .httpauth"""
        httpauth = join(os.path.expanduser('~'), '.buildout', '.httpauth')
        if not os.path.exists(httpauth):
            return None, None
        for line in open(httpauth):
            realm, url, username, password = (l.strip() for l in line.split(','))
            if repository.startswith(url):
                return username, password
        return None, None


    def executable(self):
        """returns python bin"""
        return os.sep.join(['..', '..', 'bin', 'python'])

    def checkBot(self, c):
        slave_names = [b.slavename for b in c['slaves']]
        for name in self.slave_names:
            if name in slave_names:
                return
        raise RuntimeError('No valid bot name in %r' % self.slave_names)

    def setStatus(self, c):
        if not self.email_notification_sender or \
           not self.email_notification_recipients:
            log.msg('Skipping MailNotifier for project %s: from: %s, to: %s' % (
                      self.name, self.email_notification_sender,
                      self.email_notification_recipients))
        else:
            try:
                c['status'].append(mail.MailNotifier(
                        builders=self.builders(),
                        fromaddr=self.email_notification_sender,
                        extraRecipients=self.email_notification_recipients,
                        addLogs=True,
                        relayhost=self.mail_host,
                        mode=self.mail_mode,
                        sendToInterestedUsers=True,
                        lookup=self.mail_lookup,
                        messageFormatter=self.message_formatter))
            except AssertionError:
                log.msg('Error adding MailNotifier for project %s: '
                        'from: %s, to: %s' % (
                        self.name, self.email_notification_sender,
                        self.email_notification_recipients))

    def __call__(self, c, registry):
        log.msg('Trying to add %s project' % self.name)
        try:
            self.checkBot(c)
            self.setScheduler(c, registry)
            self.setBuilder(c)
            self.setStatus(c)
        except Exception, e:
            log.msg('Error while adding the %s project: %r %s' % (self.name, e, e))
            raise

        log.msg('Project %s added' % self.name)

    def builder(self, name):
        return '%s %s' % (self.name, name)

    def builders(self):
        return [self.builder(s) for s in self.slave_names]

    def setScheduler(self, c, registry):

        # Always set a scheduler used by pollers
        if self.vcs == 'svn':
            self.schedulers.append(
                    SVNScheduler('Scheduler for %s' % self.name, self.builders(),
                                 repository=self.repository))

        # Set up the default scheduler, which can be helpful with VCSs not
        # supported by the pollers (yet), e.g. Git
        default = self.options.get('default_scheduler', None)
        if default is not None:
            try:
                timer = int(default) or 600
                if timer < 1:
                    raise ValueError
                name = 'Default scheduler for %s' % self.name
                self.schedulers.append(
                    FixedScheduler(name=name, branch=self.branch,
                              builderNames=self.builders(),
                              treeStableTimer=timer))
            except (ValueError, TypeError):
                log.msg('Invalid definition for the default '
                        'scheduler: %s' % default)
                raise

        # Set up a simple periodic scheduler
        periodic = self.options.get('periodic_scheduler', None)
        if periodic is not None:
            try:
                period = int(str(periodic).strip())
                if period < 1:
                    raise ValueError

                name = 'Periodic scheduler for %s' % self.name
                self.schedulers.append(
                    Periodic(name, self.builders(), period * 60))
            except (TypeError, ValueError):
                log.msg('Invalid period for periodic scheduler: %s' % period)
                raise

        # Set up a cron-like scheduler
        cron = self.options.get('cron_scheduler', None)
        if cron is not None:
            try:
                when = convert_cron_to_setting(cron)
                name = 'Cron scheduler for %s at %s' % (self.name, cron)
                self.schedulers.append(Nightly(name, self.builders(), *when))

            except (IndexError, ValueError, TypeError):
                log.msg('Invalid cron definition for the cron '
                        'scheduler: %s' % cron)
                raise

        # Set up a dependent scheduler
        dependent = self.options.get('dependent_scheduler', None)
        if dependent is not None:
            try:
                for parent in registry.runned(dependent, c, registry).schedulers:
                    name = ('Dependent scheduler between scheduler <%s> '
                            'and project %s' % (parent.name, self.name))
                    self.schedulers.append(
                        Dependent(name, parent, self.builders()))
            except KeyError:
                log.msg('Invalid project %s selected as dependency' % dependent)
                raise
            except ValueError:
                log.msg('Dependency loop detected')
                raise

        # Set up a general scheduler for any changes to dependencies
        dependencies = self.dependencies
        if dependencies:
            name = 'Dependency scheduler watching %s for %s' % (
                ', '.join(map(repr, dependencies)), self.name)
            self.schedulers.append(
                Scheduler(name=name, branch=None,
                          builderNames=self.builders(),
                          treeStableTimer=60,
                          fileIsImportant=FileChecker(tuple(dependencies)),
                          ))

        log.msg('Adding schedulers for %s: %s' % (self.name, self.schedulers))

        c['schedulers'].extend(self.schedulers)

    def setBuilder(self, c):
        executable = self.executable()

        if self.vcs == 'svn':
            if self.username is not None and self.password is not None:
                update_sequence = [s(steps.source.SVN, mode=self.vcs_mode,
                                     retry=self.vcs_retry,
                                     svnurl=self.repository,
                                     username=self.username,
                                     password=self.password,
                                     alwaysUseLatest=self.always_use_latest)]
            else:
                update_sequence = [s(steps.source.SVN, mode=self.vcs_mode,
                                     retry=self.vcs_retry,
                                     svnurl=self.repository,
                                     alwaysUseLatest=self.always_use_latest)]
        elif self.vcs in  ('hg', 'bzr'):
            extra = {}
            if self.vcs == 'hg':
                klass = steps.source.Mercurial
                branch_type = self.options.get('hg_branch_type')
                if branch_type:
                    extra['branchType'] = branch_type
                extra['defaultBranch'] = self.options.get(
                    'branch',
                    branch_type == 'inrepo' and 'default' or None)
            else:
                klass = steps.source.Bzr
            update_sequence = [s(klass, mode=self.vcs_mode,
                                 retry=self.vcs_retry,
                                 repourl=self.repository,
                                 alwaysUseLatest=self.always_use_latest,
                                 **extra)]
        elif self.vcs == 'git':
            update_sequence = [s(steps.source.Git, mode=self.vcs_mode,
                                 retry=self.vcs_retry,
                                 repourl=self.repository,
                                 branch=self.branch,
                                 alwaysUseLatest=self.always_use_latest)]
        elif self.vcs == 'cvs':
            cvsroot, cvsmodule = self.repository.split('!')
            update_sequence = [s(steps.source.CVS,
                                 cvsroot=cvsroot,
                                 cvsmodule=cvsmodule,
                                 branch=self.branch,
                                 mode=self.vcs_mode,
                                 retry=self.vcs_retry,
                                 alwaysUseLatest=self.always_use_latest)]
        else:
            raise NotImplementedError('%s not supported yet' % self.vcs)

        def _cmd(cmd):
            cmd = [el.strip() for el in cmd.split()]
            if cmd[0].startswith('python'):
                log.msg("Replacing python in build command with slave "
                        "python for project %s" % self.name)
                cmd[0] = self.executable()
            return cmd

        build_sequence = [s(steps.shell.ShellCommand,
                            command=_cmd(cmd),
                            haltOnFailure=True,
                            timeout=self.build_timeout)
                          for cmd in self.build_sequence
                          if cmd.strip() != '']

        test_sequence = [s(steps.shell.Test,
                           command=_cmd(cmd),
                           timeout=self.test_timeout)
                         for cmd in self.test_sequence
                         if cmd.strip() != '']

        pyflakes_sequence = []
        if self.options.get('pyflakes', None) is not None:
            pyflakes_cmds = self.options.get('pyflakes').strip().splitlines()
            for pyf in pyflakes_cmds:
                if len(pyf.strip()) > 0:
                    pyflakes_sequence.append(s(PyFlakes, command=pyf.split()))

        sequence = (update_sequence + build_sequence +
                    test_sequence + pyflakes_sequence)

        for slave_name in self.slave_names:
            log.msg('Adding slave %s to %s project' % (slave_name, self.name))
            name = '%s_%s' % (self.name, slave_name)
            builder = {'name': self.builder(slave_name),
                       'slavename': slave_name,
                       'builddir': name,
                       'factory': factory.BuildFactory(sequence)
                      }

            c['builders'].append(builder)

    # shameless copy of this: http://buildbot.afpy.org/ztk1.0dev/master.cfg
    # thx ccomb
    @staticmethod
    def messageFormatter(mode, name, build, results, master_status):
        """Provide a customized message to BuildBots's MailNotifier.
        The last 80 lines of the log are provided as well as the changes
        relevant to the build.

        >>> class AllMock(object):
        ...     def __init__(self):
        ...         self.branch = 'HIT MY'
        ...         self.revision = 0
        ...         self.patch = None
        ...     def getProjectName(self):
        ...         return 'test'
        ...     def getURLForThing(self, ignore):
        ...         return 'http://test'
        ...     def getReason(self):
        ...         return 'Running tests'
        ...     def getBuildbotURL(self):
        ...         return 'http://buildbot'
        ...     def getResponsibleUsers(self):
        ...         return ['Oliver Clothesoff!', 'Call for Oliver Clothesoff!']
        ...     def getSourceStamp(self):
        ...        return self
        >>> mocker = AllMock()
        >>> SUCCESS, FAILURE, UNKNOWN = 0, 2, 3
        >>> Project.messageFormatter(mocker, 'test', mocker, SUCCESS, mocker)
        {'body': 'OK : test / test\\nBuild: http://test\\n\\n\\nBuild Reason: Running tests\\n\\n\\nBuild Source Stamp: [branch HIT MY] HEAD\\n\\n\\nBlamelist: Oliver Clothesoff!, Call for Oliver Clothesoff!\\n\\n\\nBuildbot: http://buildbot', 'type': 'plain', 'subject': 'OK : test / test'}
        >>> Project.messageFormatter(mocker, 'test', mocker, FAILURE, mocker)['subject']
        'FAILED : test / test'
        >>> Project.messageFormatter(mocker, 'test', mocker, UNKNOWN, mocker)['subject']
        'UNKNOWN : test / test'
        """
        result = Results[results]

        limit_lines = 80
        text = list()

        # status required by zope-tests list
        # http://docs.zope.org/zopetoolkit/process/buildbots.html
        status = 'UNKNOWN'
        if result == 'success':
            status = 'OK'
        if result == 'failure':
            status = 'FAILED'

        subject = '%s : %s / %s' % (status, master_status.getProjectName(), name)
        text.append(subject)
        text.append("Build: %s" % master_status.getURLForThing(build))
        text.append('\n')
        text.append("Build Reason: %s" % build.getReason())
        text.append('\n')

        source = ""
        ss = build.getSourceStamp()
        if ss.branch:
            source += "[branch %s] " % ss.branch
        if ss.revision:
            source +=  ss.revision
        else:
            source += "HEAD"
        if ss.patch:
            source += " (plus patch)"
        text.append("Build Source Stamp: %s" % source)
        text.append('\n')
        text.append("Blamelist: %s" % ", ".join(build.getResponsibleUsers()))
        text.append('\n')
        text.append("Buildbot: %s" % master_status.getBuildbotURL())
        return {
            'body': "\n".join(text),
            'subject': subject,
	    'type' : 'plain'
            }
