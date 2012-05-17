# -*- coding: utf-8 -*-
import random
import os
from os.path import join
from collective.buildbot.recipe import BaseRecipe

import logging


# Project names should be unique inside all buildout parts, so keep track of
# them on the global level.
project_names = set()


class Project(BaseRecipe):
    """Buildout recipe to generate a project configuration file for a
    buildbot project.
    """

    config_dir = 'projects'

    def install(self):
        """generates .cfg files"""
        files = []
        project = self.name
        globs = dict(name=self.name)

        # default values in buildout section
        valid_args = ('mail-host', 'email-notification-sender',
                      'email-notification-recipients', 'email-zope-test-style',
                      'vcs-mode', 'build-timeout', 'test-timeout', 'timeout')
        for key, value in self.buildout['buildout'].items():
            if key in valid_args:
                globs[key] = value

        # project values
        globs.update(dict(self.options.items()))
        globs.pop('recipe', '')

        for k, v in (('vcs', 'svn'),
                     ('vcs-mode', 'update'),
                     ('timeout', '3600'),
                     ('build-timeout', '3600'),
                     ('test-timeout', '3600'),
                     ('mail-host', 'localhost'),
                     ('repository', ''),
                     ('email-notification-sender', ''),
                     ('email-notification-recipients', ''),
                     ('email-zope-test-style', 'False'),
                     ('test-sequence', '\n'.join([join('bin', 'test --exit-with-status')])),
                     ):
            globs.setdefault(k, v)

        if 'build-sequence' not in globs:
            globs['build-sequence'] = '\n'.join(
                ['python bootstrap.py',
                 join('bin', 'buildout')])

        if globs['vcs'] == 'git':
            globs.setdefault('branch', 'master')

        files.append(self.write_config(project, **{'project':globs}))

        return files

    update = install

class Projects(BaseRecipe):
    """Multiple project support within a single buildout section.

    All configuration options will be shared among the projects with
    the exception of the repository. For Subversion repositories it is
    possible to define separate branches/tags. For Git and other vcs
    that use the ``branch`` option the branch will be shared also.
    """

    def extract_name(self, url):
        """Extracts a name for a project based on a repository URL.

            >>> buildout = {'buildout' : {'parts-directory' : ''} }

        The method knows how to handle different version control
        system URLs. For Subversion the standard trunk/tags/branches
        structure is supported.

            >>> p = Projects(buildout, 'some-project', {'vcs' : 'svn'})
            >>> p.extract_name('http://svn.server/my.project/trunk')
            'my.project'
            >>> p.extract_name('http://svn.server/my.project/tags/1.2.3')
            'my.project'
            >>> p.extract_name('http://svn.server/my.project/branches/major-refactoring')
            'my.project'

        Unknown repository layouts will fallback to the section name.

            >>> p.extract_name('http://svn.server/my.project/stable')
            'some-project'

        Git repositories are also supported.

            >>> p = Projects(buildout, 'git-project', {'vcs' : 'git'})
            >>> p.extract_name('git://github.com/dokai/hexagonit-swfheader.git')
            'hexagonit-swfheader'

        """
        vcs = self.options.get('vcs', 'svn')
        parts = url.split('/')

        if vcs == 'svn':
            if parts[-1] == 'trunk':
                return parts[-2]
            elif parts[-2] in ('branches', 'tags'):
                return parts[-3]
        elif vcs == 'git':
            if parts[-1].endswith('.git'):
                return parts[-1][:-4]

        return self.name

    def extract_extra_identifier(self, url):
        """Extract extra identifier (branch/tag name) from url

        project, project_2, project_3 isn't that great if you're testing trunk
        and a couple of branches.  If we extract the last part of the svn url
        (so the tag or branch name), we can append that instead of an
        integer.  So project, project_reinout-refactor, project_brainstorm.

        """
        vcs = self.options.get('vcs', 'svn')
        parts = url.split('/')

        if vcs == 'svn':
            # Only for svn repositories.  Just return the last part which
            # should be 'trunk' or the branch/tag name.
            return parts[-1]

    def install(self):
        options = dict([(k, v) for k,v in self.options.items()])
        log = logging.getLogger(self.name)

        # BBB
        if 'repository' in options:
            log.info('The "repository" option is deprecated in favor '
                     'of "repositories". Please update your buildout '
                     'configuration.')
            options['repositories'] = options.pop('repository')

        repositories = [r.strip() for r
                        in options.pop('repositories', '').splitlines()
                        if r.strip()]

        cron = options.pop('cron-scheduler', None)
        if cron is not None:
            try:
                minute, hour, dom, month, dow = [v for v in cron.split()[:5]]
            except (IndexError, ValueError, TypeError):
                log.msg('Invalid cron definition for the cron scheduler: %s' % cron)
                raise

        files = []
        global project_names
        # Project names should be unique througout all buildout parts, so we
        # use the global set.

        for repository in repositories:
            if len(repositories) > 1:
                # Distribute builds randomly so we don't build
                # everything at once
                minute = str(random.randint(1,59))

                # Make sure we use unique names for project config
                # files.  First try to append a branch/tag name, alternatively
                # append an integer.
                name = self.extract_name(repository)
                if name in project_names:
                    extra = self.extract_extra_identifier(repository)
                    if extra:
                        name = name + '_' + extra
                idx = 2
                while name in project_names:
                    name = '%s_%s' % (self.extract_name(repository), idx)
                    idx += 1
                project_names.add(name)
                if 'dependent-scheduler'in options:
                    # TODO
                    log.info('dependent-scheduler is selected with projects'
                             ' including more than one repository.')
            else:
                name = self.name

            options['repository'] = repository
            if cron is not None:
                options['cron-scheduler'] = ' '.join(
                    [minute, hour, dom, month, dow])
            p = Project(self.buildout, name, options)
            files.extend(p.install())

        return files

    update = install
