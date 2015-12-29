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

0. Install git?::

    $ sudo apt-get isntall git-core

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
    $ sudo apt-get install libavcodec-extra-52 libavdevice-extra-52
    libavfilter-extra-0 libavformat-extra-52 libavutil-extra-49
    libpostproc-extra-51 libswscale-extra-0

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
import urllib
import optparse
import getpass
import pprint
import json
import datetime
import tarfile
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


def get_home():
    return os.path.expanduser('~')


def get_easy_install_path()
    return os.path.join(get_home(), 'env', 'bin', 'easy_install')


def get_pip_path()
    return os.path.join(get_home(), 'env', 'bin', 'pip')


def create_env():
    """Create the Python virtual environment in which to install the OLD.

    """

    if which('virtualenv'):
        path = os.path.join(get_home(), 'env')
        stdout = shell(['virtualenv', '--no-site-packages', path])
        print stdout
        print 'Created env/.'
    else:
        sys.exit('%sUnable to create a virtual environment: `virtualenv` is not'
            ' installed.%s' % (ANSI_FAIL, ANSI_ENDC))


def shell(cmd_list, cwd=None):
    """Execute `cmd_list` as a shell command, pipe stderr to stdout and return
    stdout.

    """

    sp = Popen(cmd_list, cwd=cwd, stdout=PIPE, stderr=STDOUT)
    stdout, nothing = sp.communicate()
    return stdout


def aptget(lib_list):
    return shell(['sudo', 'apt-get', 'install'] + lib_list)


def install_virtualenv():
    """Use `easy_install` to install `virtualenv`.

    """

    if which('virtualenv'):
        print 'virtualenv is already installed.'
        return
    if which('easy_install'):
        stdout = shell(['easy_install', 'virtualenv'])
        print stdout
        print 'Installed virtualenv.'
    else:
        sys.exit('%seasy_install is not installed. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))


def install_easy_install():
    """Run `$ sudo apt-get install python-setuptools` to install Python's
    easy_install.

    """

    if not which('easy_install'):
        stdout = aptget(['python-setuptools'])
        print stdout
        print 'Installed easy_install'


def install_old():
    """ $ ./env/bin/easy_install onlinelinguisticdatabase

    TODO: get OLD version ... from PyPI? ...

    """

    stdout = shell([get_easy_install_path(), 'onlinelinguisticdatabase'])
    print stdout
    print 'Online Linguistic Database installed'


def get_system_python_version():
    """Check the Python version. If it's in major version 2 but is not 2.6 or
    2.7, exit. Also exit if it's major version 3.

    """

    version = sys.version.split(' ')[0]
    v_list = version.split('.')
    maj = v_list[0]
    min = v_list[1]
    if maj == '2':
        if min not in ['7', '6']:
            sys.exit('%sWarning, the OLD was developed on Python 2.6 and 2.7.'
                ' Your system Python is version %s. Please install Python 2.6 or'
                ' 2.7 using .pyenv prior to using this install script.'
                ' Aborting.%s' % (ANSI_FAIL, version, ANSI_ENDC))
    else
        sys.exit('%sWarning, the OLD was developed on Python 2.6 and 2.7.'
            ' Your system Python is version %s. Please install Python 2.6 or'
            ' 2.7 using .pyenv prior to using this install script.'
            ' Aborting.%s' % (ANSI_FAIL, version, ANSI_ENDC))


def install_mysql_python():
    """ `$ ./env/bin/easy_install MySQL-python`

    """

    stdout = shell([get_easy_install_path(), 'MySQL-python'])
    print stdout
    print 'MySQL-python installed.'


def install_importlib():
    try:
        import importlib
    except ImportError:
        stdout = shell([get_easy_install_path(), 'importlib'])
        print stdout
        print 'importlib installed.'


def library_installed(name):
    """Return `True` if a Linux library is installed.

    """

    stdout = shell(['ldconfig', '-p', '|', 'grep', name])
    if stdout.strip()
        return True
    return False


def install_PIL_dependencies():
    """$ sudo apt-get install libjpeg-dev libfreetype6 libfreetype6-dev zlib1g-dev

    """

    stdout = aptget(['libjpeg-dev', 'libfreetype6', 'libfreetype6-dev',
        'zlib1g-dev'])
    print stdout
    print 'PIL dependencies installed.'


def install_PIL():
    """Install PIL::

        $ ./env/bin/pip install PIL --allow-external PIL --allow-unverified PIL

    TODO: verify .png, .jpg, and .gif scaling/thumbnailing

    """

    try:
        import Image
        print 'PIL already installed'
    except ImportError
        install_PIL_dependencies()
        stdout = shell([get_pip_path(), 'install', 'PIL', '--allow-external',
            'PIL', '--allow-unverified', 'PIL'])
        print stdout
        print 'PIL installed.'


def install_Ffmpeg_dependencies():
    stdout = aptget(['libavcodec-extra-52', 'libavdevice-extra-52',
        'libavfilter-extra-0', 'libavformat-extra-52', 'libavutil-extra-49',
        'libpostproc-extra-51', 'libswscale-extra-0'])
    print stdout
    print 'Ffmpeg dependencies installed.'


def install_Ffmpeg():
    """Install Ffmpeg.

    TODO: verify .wav to .ogg and .wav to .mp3 conversion

    """

    if not which('ffmpeg'):
        install_Ffmpeg_dependencies()
        stdout = aptget(['ffmpeg'])
        print stdout
        print 'Ffmpeg installed.'


def wget(url):
    local_filename, headers = urllib.request.urlretrieve(url)
    return local_filename


def install_m4():
    """Install m4, a bison dep, which is a foma dep.

    $ wget ftp://ftp.gnu.org/gnu/m4/m4-1.4.10.tar.gz
    $ tar -xvzf m4-1.4.10.tar.gz
    $ cd m4-1.4.10
    $ ./configure --prefix=/usr/local/m4
    $ make
    $ sudo make install

    """

    if which('m4'):
        print 'm4 is already installed.'
        return

    m4path = os.path.join(get_home(), 'm4-1.4.10.tar.gz')
    m4dirpath = os.path.join(get_home(), 'm4-1.4.10')

    fname, headers = urllib.request.urlretrieve(
        'ftp://ftp.gnu.org/gnu/m4/m4-1.4.10.tar.gz', m4path)
    if not os.path.isfile(m4path):
        sys.exit('%sUnable to download m4. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    out = tarfile.open(m4path, mode='w:gz')
    if not os.path.isdir(m4dirpath):
        sys.exit('%sUnable to extract m4. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    stdout = shell(['./configure', '--prefix=/usr/local/m4'], m4dirpath)
    print stdout
    print 'm4 configured'

    stdout = shell(['make'], m4dirpath)
    print stdout
    print '`make` run in m4'

    stdout = shell(['sudo', 'make', 'install'], m4dirpath)
    print stdout
    print '`sudo make install` run in m4'


def install_bison():
    """

    $ wget http://ftp.gnu.org/gnu/bison/bison-2.3.tar.gz
    $ tar -xvzf bison-2.3.tar.gz
    $ cd bison-2.3
    $ PATH=$PATH:/usr/local/m4/bin/
    $ ./configure --prefix=/usr/local/bison
    $ make
    $ sudo make install

    """

    if os.path.isdir('/usr/local/bison/'):
        print 'bison is already installed.'
        return

    bisonpath = os.path.join(get_home(), 'bison-2.3.tar.gz')
    bisondirpath = os.path.join(get_home(), 'bison-2.3')

    fname, headers = urllib.request.urlretrieve(
        'http://ftp.gnu.org/gnu/bison/bison-2.3.tar.gz', bisonpath)
    if not os.path.isfile(bisonpath):
        sys.exit('%sUnable to download bison. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    out = tarfile.open(bisonpath, mode='w:gz')
    if not os.path.isdir(bisondirpath):
        sys.exit('%sUnable to extract bison. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    os.environ["PATH"] += os.pathsep + '/usr/local/m4/bin/'

    stdout = shell(['./configure', '--prefix=/usr/local/bison'], bisondirpath)
    print stdout
    print 'bison configured'

    stdout = shell(['make'], bisondirpath)
    print stdout
    print '`make` run in bison'

    stdout = shell(['sudo', 'make', 'install'], bisondirpath)
    print stdout
    print '`sudo make install` run in bison'


def install_flex():
    """
    $ sudo apt-get install flex

    """

    if which('flex'):
        print 'flex is already installed.'
        return
    stdout = aptget(['flex'])
    print stdout
    print 'flex installed'


def install_subversion()
    """
    $ sudo apt-get install subversion
    """

    if which('svn'):
        print 'subversion is already installed.'
        return
    stdout = aptget(['subversion'])
    print stdout
    print 'subversion installed'


def install_foma():
    """

    $ svn co http://foma.googlecode.com/svn/trunk/foma/
    $ cd foma
    $ PATH=$PATH:/usr/local/bison/bin/
    $ sudo apt-get install libreadline6 libreadline6-dev
    $ make
    $ sudo make install

    """

    if which('foma'):
        print 'foma is already installed.'
        return

    install_m4()
    install_bison()
    install_flex()
    install_subversion()

    stdout = shell(['svn', 'co', 'http://foma.googlecode.com/svn/trunk/foma/'],
        get_home())
    print stdout
    print 'foma source checked out'
    fomadir = os.path.join(get_home(), 'foma')
    try:
        assert os.path.isdir(fomadir)
    except:
        sys.exit('%sFailed to install foma to %s.%s' % (ANSI_FAIL, fomadir,
            ANSI_ENDC))

    bisondir = '/usr/local/bison/bin/'
    if os.path.isdir(bisondir):
        os.environ["PATH"] += os.pathsep + bisondir
    else:
        sys.exit('%sbison is not installed. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    stdout = aptget(['libreadline6', 'libreadline6-dev'])
    print stdout
    print 'foma library deps installed.'

    stdout = shell(['make'], fomadir)
    print stdout
    print '`make` ran in foma'

    stdout = shell(['sudo', 'make', 'install'], fomadir)
    print stdout
    print '`sudo make install` ran in foma'

    if which('foma') and which('flookup'):
        print 'foma and flookup installed'
    else:
        print 'failed to install foma.'


def install_mitlm():
    """

    $ svn checkout http://mitlm.googlecode.com/svn/trunk/ mitlm
    $ cd mitlm
    $ make -j

    """

    if which('estimate-ngram') and which('evaluate-ngram'):
        print 'MITLM is already installed.'
        return

    stdout = shell(['svn', 'checkout', 'http://mitlm.googlecode.com/svn/trunk/',
        'mitlm'], get_home())
    print stdout
    print 'MITLM source checked out'
    mitlmdir = os.path.join(get_home(), 'mitlm')
    try:
        assert os.path.isdir(mitlmdir)
    except:
        sys.exit('%sFailed to install MITLM to %s.%s' % (ANSI_FAIL, mitlmdir,
            ANSI_ENDC))

    stdout = shell(['make', '-j'], mitlmdir)
    print stdout
    print '`make -j` ran in MITLM'

    if which('estimate-ngram') and which('evaluate-ngram'):
        print 'MITLM installed'
    else:
        print 'failed to install MITLM'


def install():
    """Install what needs installin'.

    TODO: install latex/xetex: `sudo apt-get install texlive-xetex`

    """

    get_system_python_version()
    install_easy_install()
    install_virtualenv()
    create_env()
    install_old()
    install_mysql_python()
    install_importlib()
    install_PIL()
    install_Ffmpeg()
    install_foma()
    install_mitlm()


def main():
    options, args = get_params()
    install()


if __name__ == '__main__':
    main()


