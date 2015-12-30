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
import urllib2
import optparse
import getpass
import pprint
import json
import datetime
import tarfile
from subprocess import Popen, PIPE, STDOUT


# ANSI escape sequences for formatting command-line output.
ANSI_HEADER = '\033[95m'
ANSI_OKBLUE = '\033[94m'
ANSI_OKGREEN = '\033[92m'
ANSI_WARNING = '\033[93m'
ANSI_FAIL = '\033[91m'
ANSI_ENDC = '\033[0m'
ANSI_BOLD = '\033[1m'
ANSI_UNDERLINE = '\033[4m'


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


def get_easy_install_path():
    return os.path.join(get_home(), 'env', 'bin', 'easy_install')


def get_pip_path():
    return os.path.join(get_home(), 'env', 'bin', 'pip')


def get_python_path():
    return os.path.join(get_home(), 'env', 'bin', 'python')


def get_script_dir_path():
    return os.path.dirname(os.path.abspath(__file__))


def get_tmp_path():
    return os.path.join(get_script_dir_path(), 'tmp')


def get_log_path():
    return os.path.join(get_script_dir_path(), 'log')


def create_env():
    """Create the Python virtual environment in which to install the OLD.

    """

    if which('virtualenv'):
        path = os.path.join(get_home(), 'env')
        if os.path.isfile(os.path.join(path, 'bin', 'python')):
            print 'A virtual environment already exists at %s.' % path
            return
        print 'Creating a virtual environment in %s ...' % path,
        stdout = shell(['virtualenv', '--no-site-packages', path])
        # print stdout
        log('create-env.log', stdout)
        try:
            assert 'New python executable in ' in stdout
            print 'Done.'
        except AssertionError:
            sys.exit('%sFailed to create a new virtual environment in'
               ' %s.%s' % (ANSI_FAIL, path, ANSI_ENDC))
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
        print 'Installing virtualenv ...',
        stdout = shell(['sudo', 'easy_install', 'virtualenv'])
        log('install-virtualenv.log', stdout)
        try:
            assert 'Finished processing dependencies for virtualenv' in stdout
            print 'Installed virtualenv.'
        except AssertionError:
            sys.exit('%sFailed to install virtualenv. Aborting.%s' % (
               ANSI_FAIL, ANSI_ENDC))
    else:
        sys.exit('%seasy_install is not installed. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))


def install_easy_install():
    """Run `$ sudo apt-get install python-setuptools` to install Python's
    easy_install.

    """

    if which('easy_install'):
        print 'easy_install is already installed.'
    else:
        print 'Installing easy_install ...',
        stdout = aptget(['python-setuptools'])
        log('install-easy-install.log', stdout)
        # TODO: inspect stdout to see if install worked.
        print 'Done.'


def install_old():
    """ $ ./env/bin/easy_install onlinelinguisticdatabase

    TODO: get OLD version ... from PyPI? ...

    """

    if old_installed():
        print 'OLD is already installed.'
        return
    print 'Installing OLD ...',
    stdout = shell([get_easy_install_path(), 'onlinelinguisticdatabase'])
    try:
        assert ('Finished processing dependencies for'
            ' onlinelinguisticdatabase') in stdout
        print 'Done.'
    except AssertionError:
        sys.exit('%sFailed to install the OLD.%s' % (ANSI_FAIL, ANSI_ENDC))


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
    else:
        sys.exit('%sWarning, the OLD was developed on Python 2.6 and 2.7.'
            ' Your system Python is version %s. Please install Python 2.6 or'
            ' 2.7 using .pyenv prior to using this install script.'
            ' Aborting.%s' % (ANSI_FAIL, version, ANSI_ENDC))


def install_mysql_python():
    """ `$ ./env/bin/easy_install MySQL-python`

    """

    if mysql_python_installed():
        print 'MySQL-python is already installed.'
        return
    print 'Installing MySQL-python ...',
    aptget(['libmysqlclient-dev', 'python-dev'])
    stdout = shell([get_easy_install_path(), 'MySQL-python'])
    try:
        assert 'Finished processing dependencies for MySQL-python' in stdout
        print 'Done.'
    except AssertionError:
        sys.exit('%s.Failed to install MySQL-python.%s' % (
            ANSI_FAIL, ANSI_ENDC))


def install_importlib():
    if importlib_installed():
        print 'importlib is already installed.'
        return
    print 'Installing importlib ...',
    stdout = shell([get_easy_install_path(), 'importlib'])
    try:
        assert 'Finished processing dependencies for importlib' in stdout
        print 'Done.'
    except AssertionError:
        sys.exit('%sFailed to install importlib.%s' % (ANSI_FAIL,
            ANSI_ENDC))


def library_installed(name):
    """Return `True` if a Linux library is installed.

    """

    stdout = shell(['ldconfig', '-p', '|', 'grep', name])
    if stdout.strip():
        return True
    return False


def install_PIL_dependencies():
    """$ sudo apt-get install libjpeg-dev libfreetype6 libfreetype6-dev zlib1g-dev

    """

    stdout = aptget(['libjpeg-dev', 'libfreetype6', 'libfreetype6-dev',
        'zlib1g-dev'])
    log('install-PIL-dependencies.log', stdout)


def old_installed():
    stdout = shell([get_python_path(), '-c', 'import onlinelinguisticdatabase'])
    if stdout.strip():
        return False
    return True


def importlib_installed():
    stdout = shell([get_python_path(), '-c', 'import importlib'])
    if stdout.strip():
        return False
    return True


def mysql_python_installed():
    stdout = shell([get_python_path(), '-c', 'import MySQLdb'])
    if stdout.strip():
        return False
    return True


def pil_installed():
    stdout = shell([get_python_path(), '-c', 'import Image'])
    if stdout.strip():
        return False
    return True


def install_PIL():
    """Install PIL from source.

    TODO: verify .png, .jpg, and .gif scaling/thumbnailing
    wget

    """

    if pil_installed():
        print 'PIL is already installed.'
        return

    print 'Installing PIL ...',
    install_PIL_dependencies()
    pilpath = os.path.join(get_home(), 'Imaging-1.1.7.tar.gz')
    pildirpath = os.path.join(get_home(), 'Imaging-1.1.7')
    fname, headers = urllib.urlretrieve(
        'http://effbot.org/downloads/Imaging-1.1.7.tar.gz', pilpath)
    if not os.path.isfile(pilpath):
        sys.exit('%sUnable to download PIL. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))
    tar = tarfile.open(pilpath, mode='r:gz')
    tar.extractall(path=get_home())
    tar.close()
    if not os.path.isdir(pildirpath):
        sys.exit('%sUnable to extract PIL. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))
    logtext = ['Ran `setup.py build_ext -i` in PIL\n\n']
    stdout = shell([get_python_path(), 'setup.py', 'build_ext', '-i'],
        pildirpath)
    logtext.append(stdout)
    logtext.append('\n\nRan `selftext.py` in PIL\n\n')
    stdout = shell([get_python_path(), 'selftest.py'], pildirpath)
    logtext.append(stdout)
    stdout = shell([get_python_path(), 'setup.py', 'install'],
        pildirpath)
    logtext.append(stdout)
    log('install-PIL.log', '\n'.join(logtext))
    try:
        assert 'SETUP SUMMARY' in stdout
        print 'Done.'
    except AssertionError:
        sys.exit('%sFailed to install PIL. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))


def test_PIL():
    if pil_installed():
        stdout = shell([get_python_path(), 'tests/pil.py'])
        try:
            for ext in ('gif', 'png', 'jpg'):
                orignm = 'sample.%s' % ext
                origpth = os.path.join(get_script_dir_path(), 'media', orignm)
                convnm = 'small_sample.%s' % ext
                convpth = os.path.join(get_script_dir_path(), 'media', convnm)
                assert os.path.isfile(convpth)
                assert os.path.getsize(convpth) < os.path.getsize(origpth)
            print 'PIL is working correctly.'
        except AssertionError:
            print ('%sWarning: the PIL installation does not seem to be able to'
                ' correctly reduce the size of .jpg, .png and/or .gif'
                ' files.%s' % (ANSI_WARNING, ANSI_ENDC))
        for ext in ('gif', 'png', 'jpg'):
            convnm = 'small_sample.%s' % ext
            convpth = os.path.join(get_script_dir_path(), 'media', convnm)
            if os.path.isfile(convpth):
                os.remove(convpth)
    else:
        print 'PIL is not installed'


def install_FFmpeg_dependencies():
    stdout = aptget(['libavcodec-extra-52', 'libavdevice-extra-52',
        'libavfilter-extra-0', 'libavformat-extra-52', 'libavutil-extra-49',
        'libpostproc-extra-51', 'libswscale-extra-0'])
    log('install-ffmpeg-dependencies.log', stdout)


def install_FFmpeg():
    """Install FFmpeg.

    TODO: verify .wav to .ogg and .wav to .mp3 conversion

    """

    if which('ffmpeg'):
        print 'FFmpeg is already installed.'
        return
    print 'Installing FFmpeg ...',
    install_FFmpeg_dependencies()
    stdout = aptget(['ffmpeg'])
    log('install-ffmpeg.log', stdout)
    print 'Done.'


def test_FFmpeg():
    """Test to make sure that FFmpeg can convert .wav to both .mp3 and .ogg.

    """

    wavpth = os.path.join(get_script_dir_path(), 'media', 'sample.wav')
    mp3pth = os.path.join(get_script_dir_path(), 'media', 'sample.mp3')
    oggpth = os.path.join(get_script_dir_path(), 'media', 'sample.ogg')
    if os.path.isfile(mp3pth):
        os.remove(mp3pth)
    if os.path.isfile(oggpth):
        os.remove(oggpth)
    shell(['ffmpeg', '-i', wavpth, mp3pth])
    shell(['ffmpeg', '-i', wavpth, oggpth])
    try:
        assert os.path.isfile(mp3pth)
        assert os.path.isfile(oggpth)
        assert os.path.getsize(mp3pth) < os.path.getsize(wavpth)
        assert os.path.getsize(oggpth) < os.path.getsize(wavpth)
        print 'FFmpeg is working correctly.'
    except AssertionError:
        print ('%sWarning: the FFmpeg install does not appear to be able to'
            ' convert .wav files to .mp3 and/or .ogg formats.%s' % (
            ANSI_WARNING, ANSI_ENDC))
    if os.path.isfile(mp3pth):
        os.remove(mp3pth)
    if os.path.isfile(oggpth):
        os.remove(oggpth)


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

    print 'Installing m4 ...',
    m4path = os.path.join(get_home(), 'm4-1.4.10.tar.gz')
    m4dirpath = os.path.join(get_home(), 'm4-1.4.10')

    fname, headers = urllib.urlretrieve(
        'ftp://ftp.gnu.org/gnu/m4/m4-1.4.10.tar.gz', m4path)
    if not os.path.isfile(m4path):
        sys.exit('%sUnable to download m4. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    tar = tarfile.open(m4path, mode='r:gz')
    tar.extractall(path=get_home())
    tar.close()
    if not os.path.isdir(m4dirpath):
        sys.exit('%sUnable to extract m4. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    logtext = ['./configure run in m4\n\n']
    stdout = shell(['./configure', '--prefix=/usr/local/m4'], m4dirpath)
    logtext.append(stdout)

    stdout = shell(['make'], m4dirpath)
    logtext.append(['\n\nmake run in m4\n\n'])
    logtext.append(stdout)

    stdout = shell(['sudo', 'make', 'install'], m4dirpath)
    logtext.append(['\n\nsudo make install run in m4\n\n'])
    logtext.append(stdout)

    log('install-m4.log', '\n'.join(logtext))
    print 'Done.'


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

    print 'Installing bison ...',
    bisonpath = os.path.join(get_home(), 'bison-2.3.tar.gz')
    bisondirpath = os.path.join(get_home(), 'bison-2.3')

    fname, headers = urllib.urlretrieve(
        'http://ftp.gnu.org/gnu/bison/bison-2.3.tar.gz', bisonpath)
    if not os.path.isfile(bisonpath):
        sys.exit('%sUnable to download bison. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    tar = tarfile.open(bisonpath, mode='r:gz')
    tar.extractall(path=get_home())
    tar.close()
    if not os.path.isdir(bisondirpath):
        sys.exit('%sUnable to extract bison. Aborting.%s' % (ANSI_FAIL,
            ANSI_ENDC))

    os.environ["PATH"] += os.pathsep + '/usr/local/m4/bin/'

    logtext = ['./configure run in bison\n\n']
    stdout = shell(['./configure', '--prefix=/usr/local/bison'], bisondirpath)
    logtext.append(stdout)

    stdout = shell(['make'], bisondirpath)
    logtext.append('\n\n`make` run in bison\n\n')
    logtext.append(stdout)

    stdout = shell(['sudo', 'make', 'install'], bisondirpath)
    logtext.append('\n\n`sudo make install` run in bison\n\n')
    logtext.append(stdout)

    log('install-bison.log', '\n'.join(logtext))
    print 'Done.'


def install_flex():
    """
    $ sudo apt-get install flex

    """

    if which('flex'):
        print 'flex is already installed.'
        return
    print 'Installing flex ...',
    stdout = aptget(['flex'])
    # print stdout
    log('install-flex.log', stdout)
    print 'Done.'


def install_subversion():
    """$ sudo apt-get install subversion

    """

    if which('svn'):
        print 'subversion is already installed.'
        return
    print 'Installing subversion ...',
    stdout = aptget(['subversion'])
    # print stdout
    log('install-subversion.log', stdout)
    print 'subversion installed'


def log(fname, text):
    if text.strip():
        path = os.path.join(get_log_path(), fname)
        with open(path, 'w') as f:
            f.write(text)


def install_foma():
    """

    $ svn co http://foma.googlecode.com/svn/trunk/foma/
    $ cd foma
    $ PATH=$PATH:/usr/local/bison/bin/
    $ sudo apt-get install libreadline6 libreadline6-dev
    $ make
    $ sudo make install

    """

    if which('foma') and which('flookup'):
        print 'foma is already installed.'
        return

    install_m4()
    install_bison()
    install_flex()
    install_subversion()

    print 'Installing foma ...',
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
    $ svn checkout http://mitlm.googlecode.com/svn/trunk/@46 mitlm
    $ cd mitlm

    $ sudo apt-get install autoconf automake libtool gfortran

    $ make -j

    """

    if which('estimate-ngram') and which('evaluate-ngram'):
        print 'MITLM is already installed.'
        return
    print 'Installing MITLM ...',
    stdout = shell(['svn', 'checkout', 'http://mitlm.googlecode.com/svn/trunk/',
        'mitlm'], get_home())
    mitlmdir = os.path.join(get_home(), 'mitlm')
    try:
        assert os.path.isdir(mitlmdir)
    except:
        sys.exit('%sFailed to install MITLM to %s.%s' % (ANSI_FAIL, mitlmdir,
            ANSI_ENDC))
    stdout = shell(['make', '-j'], mitlmdir)
    log('install-mitlm.log', stdout)
    if which('estimate-ngram') and which('evaluate-ngram'):
        print 'Done.'
    else:
        print 'Failed to install MITLM.'


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
    test_PIL()
    install_FFmpeg()
    test_FFmpeg()
    install_foma()
    install_mitlm()


def main():
    options, args = get_params()
    install()


if __name__ == '__main__':
    main()


