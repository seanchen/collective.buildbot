# -*- coding: utf-8 -*-
import os
import sys
import glob
import shutil
import virtualenv
import subprocess
from os.path import join
from ConfigParser import ConfigParser

class BaseRecipe(object):

    config_dir = ''

    def log(self, msg):
        print msg

    recipe_dir = os.path.dirname(__file__)

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.location = join(buildout['buildout']['parts-directory'], self.name)
        dirname = join(self.buildout['buildout']['parts-directory'],
                        self.config_dir or self.name)
        if not os.path.isdir(dirname):
            os.mkdir(dirname)

    def create_virtualenv(self, location):
        is_win = (sys.platform == 'win32')
        is_cygwin = (sys.platform == 'cygwin')
        executable = (is_win or is_cygwin) and 'python.exe' or 'python'
        bin_location = join(location, is_win and 'Scripts' or 'bin')
        python_executable = self.options.get(
            'executable', self.buildout['buildout']['executable'])

        if is_cygwin:
            # Virtualenv doesn't work on cygwin, but create a
            # bin/python using the one of buildout
            if not python_executable.endswith('exe'):
                python_executable += '.exe'
            unix_bin_location = join(location, 'bin')
            if not os.path.isfile(join(unix_bin_location, executable)):
                if not os.path.exists(unix_bin_location):
                    os.mkdir(unix_bin_location)
                os.symlink(python_executable,
                           join(unix_bin_location, executable))
        else:
            # Ok, the next part is a bit hackish. We want to run
            # virtualenv with a different version of
            # Python. Hopefully, virtualenv is just a script, so we
            # need to get the script file and execute it with the
            # correct python we want.
            virtualenv_python_file = virtualenv.__file__
            if virtualenv_python_file.endswith('c'):
                # We want a Python file, not a pyc
                virtualenv_python_file = virtualenv_python_file[:-1]

            subprocess.call([python_executable,
                             virtualenv_python_file,
                             '--no-site-packages',
                             location])
            if 'eggs' in self.options:
                eggs = [e for e in self.options['eggs'].split('\n') if e]
                subprocess.call([join(bin_location, 'easy_install'),] + eggs)

        if is_win:
            # On windows, add a bin/python as a copy of Scripts/python.exe
            unix_bin_location = join(location, 'bin')
            if not os.path.isfile(join(unix_bin_location, executable)):
                pythons = glob.glob(join(bin_location, 'python*'))
                if not os.path.exists(unix_bin_location):
                    os.mkdir(unix_bin_location)
                shutil.copyfile(pythons[0],
                                join(unix_bin_location, executable))


    def write_config(self, name, **kwargs):
        config = ConfigParser()
        for section, options in sorted(kwargs.items(), reverse=True):
            config.add_section(section)
            for key, value in sorted(options.items(), reverse=True):
                config.set(section, key, value)
        filename = join(self.buildout['buildout']['parts-directory'],
                        self.config_dir or self.name, '%s.cfg' % name)
        fd = open(filename, 'w')
        config.write(fd)
        fd.close()
        self.log('Generated config %r.' % filename)
        return filename

