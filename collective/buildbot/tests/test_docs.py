# -*- coding: utf-8 -*-
"""
Doctest runner for 'collective.buildbot'.
"""
__docformat__ = 'restructuredtext'

from os.path import join
import os
import unittest
import zc.buildout.testing
from ConfigParser import ConfigParser

from zope.testing import doctest, renormalizing
import collective.buildbot.poller
import collective.buildbot.project
import collective.buildbot.project_recipe

optionflags =  (doctest.ELLIPSIS |
                doctest.NORMALIZE_WHITESPACE |
                doctest.REPORT_ONLY_FIRST_FAILURE)
                
DOCTEST_DIR = os.path.normpath(join(os.path.dirname(__file__), '..', 'docs'))

def setUp(test):
    zc.buildout.testing.buildoutSetUp(test)

    os.makedirs(join(os.path.expanduser('~'), '.buildout'))
    fd = open(join(os.path.expanduser('~'), '.buildout', 'default.cfg'), 'w')
    fd.write('''[buildout]\noffline=true''')
    fd.close()

    # Install any other recipes that should be available in the tests

    zc.buildout.testing.install('Paste', test)
    zc.buildout.testing.install('PasteDeploy', test)
    zc.buildout.testing.install('PasteScript', test)
    zc.buildout.testing.install_develop('zc.recipe.egg', test)
    zc.buildout.testing.install_develop('virtualenv', test)
    zc.buildout.testing.install_develop('zope.interface', test)
    zc.buildout.testing.install_develop('Twisted', test)
    zc.buildout.testing.install_develop('buildbot', test)

    try:
        zc.buildout.testing.install_develop('pyflakes', test)
    except AttributeError:
        # The pyflakes PyPI page links to a broken download which means that we can't
        # make it a dependency of collective.buildbot. Therefore, in case the user
        # doesn't have it installed we'll simply fake it since the tests won't
        # actually try to run it, but the buildout depends on its existence.
        develop_eggs = join(os.getcwd(), 'develop-eggs')
        if os.path.isdir(develop_eggs):
            # Get rid of the .egg-link that got created.
            if os.path.exists(join(develop_eggs, 'pyflakes.egg-link')):
                os.unlink(join(develop_eggs, 'pyflakes.egg-link'))
            
            # Create a fake egg
            fake = open(join(develop_eggs, 'pyflakes.egg-info'), 'w')
            fake.write('Metadata-Version: 1.0\nName: pyflakes\nVersion: 0.0\n')
            fake.close()

    # Install the recipe in develop mode
    zc.buildout.testing.install_develop('collective.buildbot', test)

def test_suite():

    # doc file suite
    test_files = [
                  'master.txt',
                  'slave.txt',
                  'project.txt',
                  'poller.txt',
                  'fullexample.txt',
                  'svnauth.txt'
                 ]
    globs = globals()
    suite = unittest.TestSuite([
            doctest.DocFileSuite(
                join(DOCTEST_DIR, filename),
                setUp=setUp,
                tearDown=zc.buildout.testing.buildoutTearDown,
                globs=globs,
                optionflags=optionflags,
                module_relative=False,
                checker=renormalizing.RENormalizing([
                        # If want to clean up the doctest output you
                        # can register additional regexp normalizers
                        # here. The format is a two-tuple with the RE
                        # as the first item and the replacement as the
                        # second item, e.g.
                        # (re.compile('my-[rR]eg[eE]ps'), 'my-regexps')
                        zc.buildout.testing.normalize_path,
                        ]),
                )
            for filename in test_files if os.path.isfile(join(DOCTEST_DIR, filename))])

    # doc test suite
    suite.addTest(doctest.DocTestSuite(collective.buildbot.poller))
    suite.addTest(doctest.DocTestSuite(collective.buildbot.project))
    suite.addTest(doctest.DocTestSuite(collective.buildbot.project_recipe))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='test_suite')
