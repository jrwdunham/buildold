#!/usr/bin/python

"""
================================================================================
  Install OLD
================================================================================

This is a command-line utility for installing the OLD. It was created using a
Ubuntu 10.04 server install. The OLD is the Online Linguistic Database, a
Python/Pylons, RESTful, JSON-communicating web service application for
collaborative linguistic fieldwork.

- OLD source code: https://github.com/jrwdunham/old
- OLD documentation: http://online-linguistic-database.readthedocs.org/en/latest/
- OLD on PyPI: https://pypi.python.org/pypi/onlinelinguisticdatabase


Install Notes
================================================================================

1. get easy_install::

    $ sudo apt-get install ...

2. install virtualenv::

    $ easy_install virtualenv

3. Create env::

    $ cd ~
    $ virtualenv --no-site-packages env

4. Install OLD::

    $ ./env/bin/easy_install onlinelinguisticdatabase

5.  Install MySQL-python in the virtualenv's Python::

    $ ./env/bin/easy_install MySQL-python


6. Install importlib (required by markdown and not in SL of Python 2.6; OLD
   issue created)::

    $ easy_install importlib

7. Distro-independent way to tell if a Linux library is installed::

    $ ldconfig -p | grep <library-name>

8. Install PIL dependencies and PIL::

    $ sudo apt-get install libjpeg-dev libfreetype6 libfreetype6-dev zlib1g-dev
    $ ./env/bin/pip install PIL --allow-external PIL --allow-unverified PIL

9. Install FFMPEG::

    $ sudo apt-get install ffmpeg
    $ sudo apt-get install libavcodec-extra-52 libavdevice-extra-52 libavfilter-extra-0 libavformat-extra-52 libavutil-extra-49 libpostproc-extra-51 libswscale-extra-0

10. Install foma and flookup for FST parsers::

    $ sudo apt-get install subversion
    $ svn co http://foma.googlecode.com/svn/trunk/foma/

Install m4 for bison installation::

    $ wget ftp://ftp.gnu.org/gnu/m4/m4-1.4.10.tar.gz
    $ tar -xvzf m4-1.4.10.tar.gz
    $ cd m4-1.4.10
    $ ./configure --prefix=/usr/local/m4
    $ make
    $ sudo make install

Install bison::

    $ wget http://ftp.gnu.org/gnu/bison/bison-2.3.tar.gz
    $ tar -xvzf bison-2.3.tar.gz
    $ cd bison-2.3
    $ PATH=$PATH:/usr/local/m4/bin/
    $ ./configure --prefix=/usr/local/bison
    $ make
    $ sudo make install

Install flex::

    $ sudo apt-get install flex

Install foma::

    $ cd foma
    $ PATH=$PATH:/usr/local/bison/bin/
    $ sudo apt-get install libreadline6 libreadline6-dev
    $ make
    $ sudo make install


Requirements
================================================================================

1. you should be able to issue something like the following command and the OLD
and its dependencies will be installed on your Ubuntu server.::

    $ ./installold.py

- OLD dependencies:


Usage
================================================================================

To install the OLD on your Ubuntu (or Debian?) server::

    $ ./installold.py


TODOs
================================================================================


"""

import re
import os
import sys
import shutil
import optparse
import getpass
import pprint
import json
import datetime
from subprocess import Popen, PIPE, STDOUT


def which(program):
    """Return the path to `program` if it is an executable; otherwise return
    `None`. From
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python.

    """

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def add_optparser_options(parser):
    """Add options to the optparser parser.

    Example::

        parser.add_option("--mysql-username", dest="mysql_user",
            metavar="MYSQL_USER",
            help="The username of a MySQL user that can create and drop"
            " databases, alter them, and perform CRUD operations on tables.")

    """

    pass


def get_params():
    """Get parameters based on the arg and/or options entered at the command
    line. Prompt the user for missing params, as needed. Fail if we cannot
    acquire valid params.

    """

    usage = "usage: ./%prog [options]"
    parser = optparse.OptionParser(usage)
    add_optparser_options(parser)
    (options, args) = parser.parse_args()


    return (options, args)


def install():
    """
    $ virtualenv --no-site-packages env-old-py2.6
    $ source env-old-py2.6/bin/activate
    $ cd ~/Documents/old
    $ python setup.py develop
    $ python setup.py bdist_egg register upload

    """

    print 'install stuff'
    print sys.version
    print which('easy_install')
    print which('virtualenv')


def main():
    options, args = get_params()
    install()


if __name__ == '__main__':
    main()


