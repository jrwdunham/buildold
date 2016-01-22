#!/usr/bin/python

"""
================================================================================
  Build OLD
================================================================================

This is a command-line utility for creating, configuring and serving an OLD
application on a server that already has the OLD software
(https://github.com/jrwdunham/old) and all of its dependencies installed. This
is what it does:

    1. Creates needed directories.
    2. Creates the MySQL database.
    3. Runs `paster` commands to:
        a. create the OLD config file,
        b. perform setup (build the tables and add default data), and
        c. serve the app.
    4. Modifies /etc/apache2/sites-available/<VIRT_HOSTS_FILE> appropriately.
    5. Restarts Apache.
    6. Adds a Cronjob to restart the OLD every minute, if it's down.


Usage
================================================================================

To build and serve an OLD called "bla" (e.g., for Blackfoot)::

    $ ./buildold.py bla

Additional information is required to build an OLD. You can specify it in
options or let the script prompt you for it. The easiest, though, is to use the
--config-file option to specify a path to a JSON config file that holds this
information in an object with any of the following keys: 'mysql_user',
'paster_path', 'apps_path', 'vh_path', or 'host'::

    $ ./buildold.py bla --config-file=buildold.conf

To see available options::

    $ ./buildold.py -h

To destroy an OLD that was built using this script::

    $ ./buildold.py bla --destroy


Dependencies
================================================================================

Python-crontab (https://pypi.python.org/pypi/python-crontab) should be
installed if you want the OLD-restart cronjob to be created for you. But the
script will still work without it.


Warnings
================================================================================

1. This script assumes that you are serving OLDs on a Debian/Ubuntu Linux
   server; it currently (probably) won't work on Mac or RHEL/CentOS. It
   basically follows the instructions of Chapter 21 Deployment of The
   Definitive Guide to Pylons.

2. You'll run into problems if you change the vh_path option after you have
   isntalled OLDs with a different Apache virtual hosts config file. Don't do
   this.


TODOs
================================================================================

1. functionality for:
    - stop serving and redirect to error page.
    - start serving an already-built OLD.

2. Create a separate executable to install/uninstall/update the OLD software
   and its dependencies.

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

# Try to import python-crontab (https://pypi.python.org/pypi/python-crontab)
try:
    import crontab
except ImportError:
    crontab = None

# A hidden JSON file will be written at this path in order to keep track of
# OLDs that have been built by this OLD builder script.
STORE = '.buildold.json'

# These values specify the range of ports that we can serve OLDs on.
PORT_START = 9000
PORT_END = 9100

# ANSI escape sequences for formatting command-line output.
ANSI_HEADER = '\033[95m'
ANSI_OKBLUE = '\033[94m'
ANSI_OKGREEN = '\033[92m'
ANSI_WARNING = '\033[93m'
ANSI_FAIL = '\033[91m'
ANSI_ENDC = '\033[0m'
ANSI_BOLD = '\033[1m'
ANSI_UNDERLINE = '\033[4m'


class DBCheckError(Exception):
    pass


class DirPathIsFile(Exception):
    pass


def catcherror(func):
    """This is a decorator to wrap all functions that take a `params` dict as
    their only argument. If something goes wrong, we clean up what we've done
    in `abort` and we exit the script.

    Note: this decorator should not be used in the "destructive" functions like
    `destroy_cronjob`.

    """

    def new_func(params):
        try:
            return func(params)
        except DirPathIsFile:
            print ('%sError: attempted to create a directory where a file'
                ' already existed. Aborting.%s' % (ANSI_FAIL, ANSI_ENDC))
            abort(params)
            sys.exit('Goodbye.')
        except DBCheckError:
            print ('%sError occurred when attempting to check if the MySQL'
                ' database %s already exists. Aborting.%s' % (ANSI_FAIL, db_name,
                ANSI_ENDC))
            abort(params)
            sys.exit('Goodbye.')
        except Exception, e:
            print ('%sAn error occurred. Aborting.%s' % (ANSI_FAIL,
                ANSI_ENDC))
            print e
            abort(params)
            sys.exit('Goodbye.')
    return new_func


def write_updated_virtual_hosts_file_to_tmp(params):
    """Update the Apache virtual hosts file at `params['vh_path']` and write it
    to /tmp/.

    """

    tmp_vhs_path = '/tmp/new_old_virtual_hosts_config'
    # Get any existing ProxyPass and ProxyPassReverse lines in the virtual
    # hosts file.
    proxy_lines = {
        'ProxyPass': {},
        'ProxyPassReverse': {}
    }
    if os.path.isfile(params['vh_path']):
        with open(params['vh_path']) as f:
            for line in f:
                line_words = line.split()
                if 'ProxyPass' in line_words:
                    _dir_name = line.strip().split()[1][1:-1]
                    proxy_lines['ProxyPass'][_dir_name] = line.strip()
                if 'ProxyPassReverse' in line_words:
                    _dir_name = line.strip().split()[1][1:-1]
                    proxy_lines['ProxyPassReverse'][_dir_name] = line.strip()
    proxy_lines['ProxyPass'][params['old_dir_name']] = \
        'ProxyPass /%s/ http://localhost:%s/ retry=5' % (
            params['old_dir_name'], params['old_port'])
    proxy_lines['ProxyPassReverse'][params['old_dir_name']] = \
        'ProxyPassReverse /%s/ http://localhost:%s/' % (
            params['old_dir_name'], params['old_port'])
    proxy_lines = '%s\n    %s' % (
        '\n    '.join(sorted(proxy_lines['ProxyPass'].values())),
        '\n    '.join(sorted(proxy_lines['ProxyPassReverse'].values())))

    # Write the new virtual hosts file to /tmp/, including any previously
    # existing proxying statements.
    with open(tmp_vhs_path, 'w') as fo:
        fo.write('''<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName %s:443
    ServerAlias %s:443

    # Logfiles
    ErrorLog %s/log/error.log
    CustomLog %s/log/access.log combined

    SSLEngine on
    SSLCertificateFile %s
    SSLCertificateKeyFile %s
    SSLCertificateChainFile %s

    # Proxy
        %s
    ProxyPreserveHost On
    <Proxy *>
        Order deny,allow
        Allow from all
    </Proxy>

</VirtualHost>
</IfModule>
            ''' % (params['host'], params['host'], params['apps_path'],
                    params['apps_path'], params['ssl_crt_path'], 
                    params['ssl_key_path'], params['ssl_pem_path'], proxy_lines))

    return tmp_vhs_path


def get_http_virtual_host_file(params, proxy_lines):
    """Use this to return a string representing an Apache virtual hosts file
    for an HTTP domain.

    """

    return '''NameVirtualHost *:80
<VirtualHost *:80>
    ServerName %s
    ServerAlias %s

    # Logfiles
    ErrorLog %s/log/error.log
    CustomLog %s/log/access.log combined

    # Proxy
    %s
    ProxyPreserveHost On
    <Proxy *>
        Order deny,allow
        Allow from all
    </Proxy>
</VirtualHost>
            ''' % (params['host'], params['host'], params['apps_path'],
                    params['apps_path'], proxy_lines)


@catcherror
def add_virtual_host(params):
    """Create the Apache virtual host for the OLD app.

    """

    print 'Modifying Apache virtual hosts file.'
    tmp_vhs_path = write_updated_virtual_hosts_file_to_tmp(params)
    if os.path.isfile(params['vh_path']):
        r = os.system('sudo mv %s %s_bk' % (params['vh_path'], params['vh_path']))
        print ('%sThe virtual hosts file %s already existed; we moved the'
            ' pre-modified version of it to %s_bk.%s' % (ANSI_WARNING,
            params['vh_path'], params['vh_path'], ANSI_ENDC))
    r = os.system('sudo mv %s %s' % (tmp_vhs_path, params['vh_path']))
    try:
        assert r == 0
        params['actions'].append('virtual hosts file modified')
    except:
        vhs_content = ''
        if os.path.isfile(tmp_vhs_path):
            with open(tmp_vhs_path) as f:
                vhs_content = f.read()
        abort(params)
        if vhs_content:
            sys.exit('%sUnable to configure the virtual host. Maybe you can do'
                ' it manually. The file at %s should look like this:'
                '\n\n%s%s' % (ANSI_FAIL, params['vh_path'], vhs_content, ANSI_ENDC))
        else:
            sys.exit('%sUnable to configure the virtual host.%s' % (ANSI_FAIL,
                ANSI_ENDC))

    # If not enabled, we enable the virtual hosts config file here.
    enable_virtual_hosts_config(params)


def enable_virtual_hosts_config(params):
    """If the user-specified Apache virtual hosts config file is not enabled,
    we enable it here.

    WARNING: this is very brittle as it assumes that we can check if a config
    file is enabled simply by replacing 'sites-available' in its path with
    'sites-enabled' and checking if that path points to a file.

    """

    fail_msg = ('%sUnable to enable your Apache virtual hosts config'
        ' file. Do it manually by running `sudo a2ensite ` followed'
        ' by the name of your virtual hosts config file.%s' % (
        ANSI_WARNING, ANSI_ENDC))
    if not os.path.isfile(params['vh_path'].replace('sites-available',
        'sites-enabled')):
        try:
            print 'Enabling the Apache virtual hosts config file.'
            vh_name = os.path.split(params['vh_path'])[1]
            enableconfig = Popen(['sudo', 'a2ensite', vh_name],
                stdout=PIPE, stderr=STDOUT)
            stdout, nothing = enableconfig.communicate()
            try:
                assert 'Enabling site' in stdout
            except:
                print fail_msg
        except:
            print fail_msg


def restore_virtual_hosts_file(params):
    """Restore the Apache virtual hosts file to its previous state and restart
    Apache.

    """

    try:
        print 'Restoring Apache virtual hosts file.'
        fail_msg = ('%sUnable to restore virtual hosts file. You should manually'
            ' remove any lines that contain ProxyPass /%s/ or ProxyPassReverse /%s/'
            ' from the file %s and then run `sudo /etc/init.d/apache2 restart`.%s' % (
            ANSI_WARNING, params['old_dir_name'], params['old_dir_name'],
            params['vh_path'], ANSI_ENDC))
        if os.path.isfile('%s_bk' % params['vh_path']):
            r = os.system('sudo mv %s_bk %s' % (params['vh_path'],
                params['vh_path']))
            try:
                assert r == 0
                restart_apache(params)
            except:
                print fail_msg
        else:
            print fail_msg
    except:
        print ('%sSomething may have gone wrong when attempting to restore the'
            ' virtual hosts file %s. Please check that it is no longer proxying'
            ' requests to %s.%s' % (ANSI_WARNING, params['vh_path'],
            params['old_dir_name'], ANSI_ENDC))


@catcherror
def restart_apache(params):
    """Restart the Apache2 server so that the new virtual hosts file can take
    effect.

    """

    print 'Restarting the Apache server.'
    apacherestart = Popen(['sudo', '/etc/init.d/apache2', 'restart'],
        stdout=PIPE, stderr=STDOUT)
    stdout, nothing = apacherestart.communicate()
    try:
        assert '...done.' in stdout
    except:
        print ('%sUnable to restart Apache. Do it manually by running `sudo'
            ' /etc/init.d/apache2 restart`.%s' % (ANSI_WARNING, ANSI_ENDC))


def get_available_ports(params):
    """Inspect the file at `params['vh_path']` and return the list of AVAILABLE ports.

    """

    all_ports = map(str, range(PORT_START, PORT_END + 1))
    used_ports = get_used_ports(params)
    return [p for p in all_ports if p not in used_ports]


def get_used_ports(params):
    """Inspect the file at `params['vh_path']` and return the list of USED ports.

    """

    ports = set()
    if os.path.isfile(params['vh_path']):
        with open(params['vh_path']) as f:
            for line in f:
                if '://localhost:' in line:
                    port = []
                    for c in line:
                        if c in map(str, range(0, 10)):
                            port.append(c)
                    port = ''.join(port)
                    ports.add(port)
    return list(ports)


def add_optparser_options(parser):
    """Add options to the optparser parser.

    """

    parser.add_option("--mysql-username", dest="mysql_user",
        metavar="MYSQL_USER",
        help="The username of a MySQL user that can create and drop"
        " databases, alter them, and perform CRUD operations on tables.")

    parser.add_option("--mysql-password", dest="mysql_pwd",
        metavar="MYSQL_PWD",
        help="The password of the MySQL user.")

    parser.add_option("--config-file", dest="config_file",
        metavar="CONFIG_FILE",
        help="Path to a JSON file containing an object with any of the"
            " following keys: 'mysql_user', 'paster_path', 'apps_path',"
            " 'vh_path', 'host', 'ssl_crt_path', 'ssl_key_path', or"
            " 'ssl_pem_path'. If present, these values will be used when"
            " their corresponding options are not supplied.")

    parser.add_option("--paster_path", dest="paster_path",
        metavar="PASTER_PATH",
        help="The path to the paster program. Defaults to 'paster'.")

    parser.add_option("--apps-path", dest="apps_path",
        metavar="APPS_PATH",
        help="Path of the directory where you want the OLD app to be installed.")

    parser.add_option("--virtual-hosts-path", dest="vh_path",
        metavar="VH_PATH",
        help="Path to the Apache virtual hosts config file. This file may exist"
            " but it doesn't need to; this script will create it, if needed."
            " Defaults to a file with the same name as HOST located in"
            " /etc/apache2/sites-available/.")

    parser.add_option("--host", dest="host", metavar="HOST",
        help="The host name of the URL of this OLD. E.g., www.myoldurl.com")

    parser.add_option("--destroy", dest="destroy",
            action="store_true", default=False, metavar="DESTROY",
            help="Use this option to change this program from a builder to a"
            " destroyer. If buildold.py has created the target OLD, it will be"
            " destroyed: it will stop being served, its directories will be"
            " deleted, and its MySQL database will be dropped. USE WITH EXTREME"
            " CAUTION.")

    parser.add_option("--list", dest="list",
        action="store_true", default=False, metavar="LIST",
        help="Print a list of all OLDs that have been installed here by"
            " buildold.py.")

    parser.add_option("--dative-servers", dest="dative_servers",
        metavar="DATIVE_SERVERS", help="Specify the path for a JSON file that"
        " this script should produce; that JSON file will summarize the OLD"
        " instances that are being served by this script; this JSON summary can"
        " be served by Dative as servers.json so that Dative's default servers"
        " match those being served here.")

    parser.add_option("--ssl-crt-path", dest="ssl_crt_path",
        metavar="SSL_CRT_PATH",
        help="Path to your SSL .crt file.")

    parser.add_option("--ssl-pem-path", dest="ssl_pem_path",
        metavar="SSL_PEM_PATH",
        help="Path to your SSL .pem file, i.e., the intermediate certificate,"
            " the one that Apache calls the SSLCertificateChainFile.")

    parser.add_option("--ssl-key-path", dest="ssl_key_path",
        metavar="SSL_KEY_PATH",
        help="Path to your SSL .key file.")


def get_config_from_file(options):
    """If the user specified a value for the --config-file option, attempt to
    parse the JSON of this file and return it as a dict.

    """

    config_from_file = {}
    config_file = getattr(options, 'config_file', None)
    if config_file:
        if os.path.isfile(config_file):
            try:
                config_from_file = json.load(open(config_file))
                assert type(config_from_file) is type({})
            except Exception, e:
                config_from_file = {}
    return config_from_file


def prompt_for_name(p):
    """Prompt the user for an OLD name if we don't have one.

    """

    if not p['old_name']:
        prompt, fail_msg = {
            True: ('%sPlease enter the name of the OLD that you want to'
                ' destroy:%s ' % (ANSI_WARNING, ANSI_ENDC),
                '%sYou must provide the name of the OLD to destroy.%s' % (
                ANSI_FAIL, ANSI_ENDC)),
            False: ('%sPlease enter a name for the OLD that you want to build'
                ' (use only letters, numbers and/or the underscore):%s ' % (
                ANSI_WARNING, ANSI_ENDC),
                '%sYou must provide a name for the OLD that you want to'
                ' build.%s' % (ANSI_FAIL, ANSI_ENDC))}[p['destroy']]
        p['old_name'] = raw_input(prompt)
        if not p['old_name']:
            sys.exit(fail_msg)


def prompt_for_mysql_password(p):
    """Prompt user for MySQL password, if we don't have it yet.

    """

    if not p['mysql_pwd']:
        p['mysql_pwd'] = getpass.getpass('%sPlease enter the password for the'
            ' MySQL user %s:%s ' % (ANSI_WARNING, p['mysql_user'], ANSI_ENDC))
        if not p['mysql_pwd']:
            sys.exit('%sYou must provide the MySQL user\'s password.%s' % (
                ANSI_FAIL, ANSI_ENDC))


def validate_mysql_credentials(params):
    """Check if we can actually access MySQL with the provided credentials;
    also check if we have sufficient privileges to do what we need to do.

    WARNING: requiring that the output to 'SHOW GRANTS;' contain "GRANT ALL
    PRIVILEGES ON *.* TO '<mysql-user>'" might be too stringent.

    """

    mysql_show_grants = Popen(['mysql', '-u', params['mysql_user'],
        '-p%s' % params['mysql_pwd'], '-e', 'show grants;'], stdout=PIPE,
        stderr=STDOUT)
    stdout, stderr = mysql_show_grants.communicate()
    if 'Access denied' in stdout:
        sys.exit('%sSorry, we cannot access MySQL with user %s and the provided'
            ' password.%s' % (ANSI_FAIL, params['mysql_user'], ANSI_ENDC))
    elif "GRANT ALL PRIVILEGES ON *.* TO '%s'" % params['mysql_user'] not in stdout:
        print 'INSUFF PRIV'
        sys.exit('%sSorry, user %s does not have sufficient MySQL privileges to'
            ' build an OLD.%s' % (ANSI_FAIL, params['mysql_user'], ANSI_ENDC))


def get_params():
    """Get parameters based on the arg and/or options entered at the command
    line. Prompt the user for missing params, as needed. Fail if we cannot
    acquire valid params.

    """

    global_state = get_state()

    usage = "usage: ./%prog old-name [options]"
    parser = optparse.OptionParser(usage)
    add_optparser_options(parser)
    (options, args) = parser.parse_args()
    try:
        old_name = args[0]
    except:
        old_name = None
    conf = get_config_from_file(options)
    p = {
        'old_name': old_name,
        'mysql_user': options.mysql_user or conf.get('mysql_user'),
        'mysql_pwd': options.mysql_pwd,
        'paster_path': options.paster_path or conf.get('paster_path'),
        'apps_path': options.apps_path or conf.get('apps_path'),
        'vh_path': options.vh_path or conf.get('vh_path'),
        'ssl_crt_path': options.ssl_crt_path or conf.get('ssl_crt_path'),
        'ssl_key_path': options.ssl_key_path or conf.get('ssl_key_path'),
        'ssl_pem_path': options.ssl_pem_path or conf.get('ssl_pem_path'),
        'host': options.host or conf.get('host'),
        'destroy': options.destroy,
        'list': options.list,
        'dative_servers': options.dative_servers,
        'actions': [] # remembers what we've done, in case abort needed.
    }

    # If the user wants to list all of the OLDs installed, we exit here--don't
    # need a name.
    if p['list'] or p['dative_servers']:
        return p, global_state

    # Prompt user for an OLD name if we don't have one.
    prompt_for_name(p)

    # If we're destroying an OLD, all we need it its name.
    if p['destroy']:
        return p, global_state

    # Prompt the user for the apps path, if we don't have it yet.
    if not p['apps_path']:
        p['apps_path'] = raw_input('%sPlease enter the path of the directory'
            ' where you want your OLD\'s files to be written. This script will'
            ' create the directory, if needed:%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['apps_path']:
            sys.exit('%sYou must specify the directory where the OLD app\'s'
                ' directory will be located.%s' % (ANSI_FAIL, ANSI_ENDC))

    # Exit if the OLD name is invalid
    if not re.search('^\w+$', p['old_name'].strip()):
        sys.exit('%sYour OLD name can only contain letters, numbers'
            ' and/or the underscore.%s' % (ANSI_FAIL, ANSI_ENDC))

    # Exit if the OLD name is already in use.
    if old_already_exists(p):
        sys.exit('%sThere is already an OLD with the name %s installed here.'
            ' Please try again with a different name.%s' % (ANSI_FAIL,
            p['old_name'], ANSI_ENDC))

    # Prompt user for MySQL username, if we don't have it yet.
    if not p['mysql_user']:
        p['mysql_user'] = raw_input('%sPlease enter the username of a MySQL user with'
            ' sufficient privileges:%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['mysql_user']:
            sys.exit('%sYou must provide a MySQL username.%s' % (ANSI_FAIL,
                ANSI_ENDC))

    prompt_for_mysql_password(p)
    validate_mysql_credentials(p)

    # Prompt user for path to Paster executable, if we don't have it yet.
    if not p['paster_path']:
        p['paster_path'] = raw_input('%sPlease tell us where the paste'
            ' executable is; type nothing if it\'s in your PATH and can be'
            ' accessed with \'paster\':%s' % (ANSI_WARNING, ANSI_ENDC))
        if not p['paster_path']:
            p['paster_path'] = conf.get('paster_path', 'paster')

    # Check if paster is really available at the specified path.
    if not which(p['paster_path']):
        sys.exit('%sSorry, there is no (paster) executable at %s.'
            ' Please install Paste and tell us where it is.%s' % (
            ANSI_FAIL, p['paster_path'], ANSI_ENDC))

    # Exit if the OLD name corresponds to an already-existing MySQL database
    p['old_dir_name'] = get_dir_name_from_old_name(p['old_name'])
    if database_already_exists(p['old_dir_name'], p['mysql_user'],
        p['mysql_pwd']):
        sys.exit('%sThere is already a MySQL database with the name %s. Please'
            ' choose a name for your OLD other than %s.%s' % (ANSI_FAIL,
            p['old_dir_name'], p['old_name'], ANSI_ENDC))

    # Exit if this script has already built an OLD with this name.
    exists = len([old_p for old_p in global_state
        if old_p['old_dir_name'] == p['old_dir_name']]) > 0
    if exists:
        sys.exit('%sThis script has already installed an OLD with the name %s.'
            ' Please try again with a different name.%s' % (ANSI_FAIL,
            p['old_name'], ANSI_ENDC))

    # Prompt the user for the host, if we don't have it yet.
    if not p['host']:
        p['host'] = raw_input('%sPlease enter the host name of the URL where'
            ' your OLD will be served, e.g., something like'
            ' "www.myoldurl.com":%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['host']:
            sys.exit('%sYou must provide a host value.%s' % (ANSI_FAIL,
                ANSI_ENDC))

    # Prompt the user for the virtual hosts path, if we don't have it yet.
    if not p['vh_path']:
        default = '/etc/apache2/sites-available/%s' % p['host']
        p['vh_path'] = raw_input('%sPlease enter the path for the Apache'
            ' virtual hosts path for this OLD. We will use %s if you enter'
            ' nothing:%s ' % (ANSI_WARNING, default, ANSI_ENDC))
        if not p['vh_path']:
            p['vh_path'] = default

    # Prompt the user for the SSL .crt file path, if we don't have it yet.
    if not p['ssl_crt_path']:
        p['ssl_crt_path'] = raw_input('%sPlease enter the absolute path to'
            ' your SSL .crt file:%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['ssl_crt_path']:
            sys.exit('%sYou must provide a SSL .crt file path%s' % (ANSI_FAIL,
                ANSI_ENDC))

    # Prompt the user for the SSL .key file path, if we don't have it yet.
    if not p['ssl_key_path']:
        p['ssl_key_path'] = raw_input('%sPlease enter the absolute path to'
            ' your SSL .key file:%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['ssl_key_path']:
            sys.exit('%sYou must provide a SSL .key file path%s' % (ANSI_FAIL,
                ANSI_ENDC))

    # Prompt the user for the SSL .key file path, if we don't have it yet.
    if not p['ssl_pem_path']:
        p['ssl_pem_path'] = raw_input('%sPlease enter the absolute path to'
            ' your SSL .pem file:%s ' % (ANSI_WARNING, ANSI_ENDC))
        if not p['ssl_pem_path']:
            sys.exit('%sYou must provide a SSL .pem file path%s' % (ANSI_FAIL,
                ANSI_ENDC))

    return p, global_state


def old_already_exists(params):
    """Return `True` if there is already an OLD installed here with name `old_name`.

    """

    return get_dir_name_from_old_name(params['old_name']) in \
        get_old_dirs(params)


def get_old_dirs(params):
    """Return the list of directories in params['apps_path']. These should only
    be OLD-containing directories.

    """

    existing_old_dirs = []
    if os.path.isdir(params['apps_path']):
        existing_old_dirs = [o for o in os.listdir(params['apps_path']) if
            os.path.isdir(os.path.join(params['apps_path'], o))]
    return existing_old_dirs


def create_directory_safely(path):
    """Create a directory. If `path` is an existing file, fail. If `path` is an
    existing directory, return `path`. If `path` doesn't exist, create it and
    return `path`.

    """

    if os.path.isfile(path):
        raise DirPathIsFile
    if not os.path.isdir(path):
        os.makedirs(path)
    return path


def get_next_available_port(params):
    """Get the next available port for creating OLDs with.

    """

    available_ports = get_available_ports(params)
    if available_ports:
        return available_ports[0]
    else:
        abort(params)
        sys.exit('%sAborting: no more ports available; you are already using'
            ' ports %s through %s.%s' % (ANSI_FAIL, PORT_START, PORT_END,
            ANSI_ENDC))


def get_dir_name_from_old_name(old_name):
    """Given the user-supplied OLD name, return the name that we will use for
    the directory that holds the files of this new OLD.

    """

    return '%sold' % old_name.lower()


@catcherror
def create_dirs(params):
    """Create the directories needed to build the OLD.

    """

    print 'Creating directories.'
    log_path = os.path.join(params['old_path'], 'log')
    general_log_path = os.path.join(params['apps_path'], 'log')
    create_directory_safely(params['apps_path'])
    create_directory_safely(general_log_path)
    create_directory_safely(params['old_path'])
    create_directory_safely(log_path)
    params['actions'].append('created old directory')


@catcherror
def make_config(params):
    """Get Python Paster to create the production.ini config file for the new
    OLD.

    """

    print 'Creating the OLD config file.'
    cnf_pth = os.path.join(params['old_path'], 'production.ini')
    cmd = '%s make-config onlinelinguisticdatabase %s' % (
        params['paster_path'], cnf_pth)
    resp = os.popen(cmd).read()
    fail_msg = '%sUnable to create the OLD config file. Aborting.%s' % (
        ANSI_FAIL, ANSI_ENDC)
    try:
        resp = [l.strip() for l in resp.split('\n') if l.strip()]
        if resp[-1] != cnf_pth:
            abort(params)
            sys.exit(fail_msg)
    except:
        abort(params)
        sys.exit(fail_msg)


def __get_serve_command__(params):
    """Return the string of the command that serves this OLD.

    """

    # pid_pth = os.path.join(params['old_path'], 'old.pid')
    # log_pth = os.path.join(params['old_path'], 'log', 'paster-old.log')
    # cnf_pth = os.path.join(params['old_path'], 'production.ini')
    pid_pth = 'old.pid'
    log_pth = os.path.join('log', 'paster-old.log')
    cnf_pth = 'production.ini'
    return ('cd %s; %s serve --daemon --pid-file=%s --log-file=%s %s' % (
        params['old_path'], params['paster_path'], pid_pth, log_pth, cnf_pth))


def get_serve_command(params):
    """Return an array representing the command that serves this OLD.

    """

    pid_pth = os.path.join(params['old_path'], 'old.pid')
    log_pth = os.path.join(params['old_path'], 'log', 'paster-old.log')
    cnf_pth = os.path.join(params['old_path'], 'production.ini')
    # pid_pth = 'old.pid'
    # log_pth = os.path.join('log', 'paster-old.log')
    # cnf_pth = 'production.ini'
    return [params['paster_path'], 'serve', '--daemon',
        '--pid-file=%s' % pid_pth, '--log-file=%s' % log_pth, cnf_pth]


@catcherror
def serve(params):
    """Use Python Paster to serve the OLD app in a daemon process.

    """

    print 'Starting the paster server.'
    cmd = get_serve_command(params)
    print '\n%s\n' % ' '.join(cmd)
    # resp = os.popen(cmd).read()
    serve = Popen(cmd, stdout=PIPE, stderr=STDOUT, cwd=params['old_path'])
    resp, nothing = serve.communicate()
    # FOX
    try:
        assert resp.strip() == ''
        params['actions'].append('served app')
    except:
        print resp
        abort(params)
        sys.exit('%sSomething went wrong when attempting to serve the OLD.'
            ' Aborting.%s' % (ANSI_HEADER, ANSI_ENDC))


def stop_serving(params):
    """Use Python Paster to stop serving the OLD app.

    """

    try:
        print 'Stopping the paster server.'
        # cmd = '%s stop' % get_serve_command(params)
        # resp = os.popen(cmd).read()
        cmd = get_serve_command(params)
        cmd.append('stop')
        stopserve = Popen(cmd, stdout=PIPE, stderr=STDOUT, cwd=params['old_path'])
        resp, nothing = stopserve.communicate()
        try:
            assert resp.strip() == ''
        except Exception, e:
            print ('Error: the output from stopping the paster server is not'
                ' empty:')
            print e
            print ('%sSomething may have gone wrong when attempting to stop the'
                ' paster server.%s' % (ANSI_HEADER, ANSI_ENDC))
    except Exception, e:
        print 'An error occurred when attempting to stop the paster server'
        print e
        print ('%sSomething may have gone wrong when attempting to stop the'
            ' paster server.%s' % (ANSI_WARNING, ANSI_ENDC))


def get_cronjob_cmd(params):
    """Return the Cronjob command to restart the OLD if it has stopped.

    """

    return 'cd %s; %s start >/dev/null 2>&1' % (params['old_path'],
        ' '.join(get_serve_command(params)))


@catcherror
def create_cronjob(params):
    """Create a crontab to check every minute if the OLD has stopped and
    restart it if so.

    """

    print 'Enabling cronjob to restart your OLD in case it goes down.'
    cmd = get_cronjob_cmd(params)
    if crontab:
        cron  = crontab.CronTab(user=True)
        job = cron.new(command=cmd)
        job.minute.every(1)
        job.enable()
        if True == job.is_valid():
            params['actions'].append('cronjob created')
            cron.write()
        else:
            print ('%sUnable to enable the OLD restart cronjob. We suggest you'
                ' put the following line in your crontab: "*/1 * * * * %s".%s' % (
                ANSI_WARNING, cmd, ANSI_ENDC))
    else:
        print ('%sPython-crontab is not installed. You should probably install'
            ' it (e.g., via `easy_install python-crontab`) before you run this'
            ' script again. For the OLD that has just been built, we suggest'
            ' you put the following line in your crontab: "*/1 * * * * %s".%s' % (
            ANSI_WARNING, cmd, ANSI_ENDC))


def destroy_cronjob(params):
    """Create a crontab to check every minute if the OLD has stopped and
    restart it if so.

    """

    print 'Destroying cronjob.'
    try:
        cmd = get_cronjob_cmd(params)
        if crontab:
            cron  = crontab.CronTab(user=True)
            for job in cron.find_command(cmd):
                cron.remove(job)
            cron.write()
        else:
            print ('%sPython-crontab is not installed. You should probably install'
                ' it (e.g., via `easy_install python-crontab`) before you run this'
                ' script again. For now, we suggest that you manually remove the'
                ' following line from your crontab: "* * * * * %s".%s' % (
                ANSI_WARNING, cmd, ANSI_ENDC))
    except:
        print ('%sSorry, something went wrong when attempting to destroy the'
            ' cronjob. Try to do it yourself.%s' % (ANSI_WARNING, ANSI_ENDC))


@catcherror
def setup_app(params):
    """Get Python Paster to create the OLD database tables and defaults, i.e.,
    run `setup-app`.

    """

    print 'Running OLD setup: building tables and entering defaults.'
    cnf_pth = os.path.join(params['old_path'], 'production.ini')
    cmd = 'cd %s; %s setup-app %s' % (params['old_path'],
        params['paster_path'], cnf_pth)
    resp = os.popen(cmd).read()
    try:
        assert resp.strip() == ('Running setup_app() from'
            ' onlinelinguisticdatabase.websetup')
    except:
        abort(params)
        sys.exit('%sSomething went wrong when attempting to set up the OLD.'
            ' Aborting.%s' % (ANSI_HEADER, ANSI_ENDC))


@catcherror
def edit_config(params):
    """Edit the OLD's config file production.ini:

    - Change the port to `params['port']`
    - Comment out the SQLite lines and uncomment MySQL lines.
    - Change the first MySQL so it holds the credentials and correct db name.

    """

    print 'Editing the OLD\'s config file (production.ini).'
    try:
        new_config_file = []
        cnf_pth = os.path.join(params['old_path'], 'production.ini')
        mysql_line = ('sqlalchemy.url ='
            ' mysql://%s:%s@localhost:3306/%s?charset=utf8' % (params['mysql_user'],
            params['mysql_pwd'], params['db_name']))
        with open(cnf_pth) as fi:
            for line in fi:
                if line.startswith('port ='):
                    new_config_file.append('port = %s' % params['old_port'])
                elif 'sqlalchemy.url' in line and 'sqlite' in line:
                    new_config_file.append('# %s' % line.strip())
                elif 'sqlalchemy.url' in line and 'mysql' in line:
                    new_config_file.append(mysql_line)
                elif 'sqlalchemy.pool_recycle' in line:
                    new_config_file.append('sqlalchemy.pool_recycle = 3600')
                else:
                    new_config_file.append(line.strip())
        with open(cnf_pth, 'w') as fo:
            fo.write('\n'.join(new_config_file))
    except Exception, e:
        print e
        abort(params)
        sys.exit('%sSomething went wrong when attempting to edit the OLD\'s'
            ' config file. Aborting.%s' % (ANSI_HEADER, ANSI_ENDC))


@catcherror
def create_database(params):
    """Create MySQL database `params['db_name']`.

    """

    print 'Creating MySQL database %s.' % params['db_name']
    cmd = ('mysql -u %s -p%s -e "create database %s default character set'
        ' utf8;"' % (params['mysql_user'], params['mysql_pwd'],
        params['db_name']))
    resp = os.popen(cmd).read()
    try:
        resp = resp.strip()
        params['actions'].append('mysql database created')
        if resp:
            abort(params)
            if 'database exists' in resp:
                sys.exit('%sThe MySQL database %s already exists; please drop'
                    ' it manually or choose a different name for your'
                    ' OLD.%s' % (ANSI_FAIL, params['db_name'], ANSI_ENDC))
            else:
                sys.exit('%sAn error occurred when attempting to create the'
                    ' MySQL database %s. Aborting.%s' % (ANSI_FAIL,
                    params['db_name'], ANSI_ENDC))
    except:
        abort(params)
        sys.exit('%sAn error occurred when attempting to create the'
            ' MySQL database %s. Aborting.%s' % (ANSI_FAIL, params['db_name'],
            ANSI_ENDC))


def drop_database(params):
    """Drop the MySQL database corresponding to the OLD encoded in `params`.

    """

    fail_msg = ('%sSomething may have gone wrong when attempting to drop the'
        ' MySQL database %s. Please check to ensure that it has been'
        ' dropped.%s' % (ANSI_WARNING, params['db_name'], ANSI_ENDC))
    try:
        print 'Dropping MySQL database %s.' % params['db_name']
        cmd = 'mysql -u %s -p%s -e "drop database %s;"' % (params['mysql_user'],
            params['mysql_pwd'], params['db_name'])
        resp = os.popen(cmd).read()
        try:
            assert resp.strip() == ''
        except Exception, e:
            print e
            print fail_msg
    except Exception, e:
        print e
        print fail_msg


def database_already_exists(db_name, mysql_user, mysql_pwd):
    """Return `True` if MySQL database `db_name` already exists; `False`
    otherwise.

    """

    cmd = ('mysql -u %s -p%s -e "SELECT SCHEMA_NAME FROM'
        ' INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME = \'%s\';"' % (
        mysql_user, mysql_pwd, db_name))
    try:
        resp = os.popen(cmd).read()
        if db_name in resp:
            return True
        else:
            return False
    except:
        raise DBCheckError


@catcherror
def fix_tag_name_col(params):
    """Change the collation of the MySQL tag table's "name" column to
    "utf8_bin" so that capitalized duplicate tags can be migrated.

    """

    print 'Setting the tag table\'s "name" colummn to UTF-8 collation.'
    cmd = ('mysql -u %s -p%s -e "use %s; alter table tag modify name'
        ' varchar(255) collate utf8_bin;"' % (params['mysql_user'],
        params['mysql_pwd'], params['db_name']))
    resp = os.popen(cmd).read()
    try:
        assert resp.strip() == ''
    except:
        abort(params)
        sys.exit('%sAn error occurred when attempting to create the'
            ' MySQL database %s. %s. Aborting.%s' % (ANSI_FAIL,
            params['db_name'], resp, ANSI_ENDC))



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


def abort(params):
    """This is called when the script aborts mid-build. It should undo what has
    been done, in reverse order.

    created old directory -> destroy_old_directory
    mysql database created -> drop_database
    served app -> stop_serving
    virtual hosts file modified -> restore_virtual_hosts_file
    cronjob created -> destroy_cronjob

    """

    actions_taken = params['actions']
    if 'init script' in actions_taken:
        remove_init_script(params)
    if 'cronjob created' in actions_taken:
        destroy_cronjob(params)
    if 'virtual hosts file modified' in actions_taken:
        restore_virtual_hosts_file(params)
    if 'served app' in actions_taken:
        stop_serving(params)
    if 'mysql database created' in actions_taken:
        drop_database(params)
    if 'created old directory' in actions_taken:
        destroy_old_directory(params)


def destroy_old_directory(params):
    """Destroy the OLD directory for the OLD encoded in `params`. Useful for
    cleaning up an OLD whose build has been aborted because of an error or for
    destroying an existing OLD.

    """

    try:
        print 'Destroying directory for the OLD %s.' % params['old_name']
        if os.path.isdir(params['old_path']):
            shutil.rmtree(params['old_path'])
    except:
        print ('%sSomething may have gone wrong when attempting to destroy the'
            ' directory %s. Check to ensure that it has been destroyed.%s' % (
            ANSI_WARNING, params['old_path'], ANSI_ENDC))


def save_state(params):
    """Document the OLD that we have built in our JSON file at `STORE`. This is
    just good practice. But it will also allow this script to destroy and/or
    shut down OLDs that it has previously built.

    """

    try:
        global_state = get_state()
        params['build_date'] = datetime.datetime.utcnow().isoformat()
        state = {}
        for attr in ['actions', 'apps_path', 'build_date', 'db_name', 'host',
            'mysql_user', 'old_dir_name', 'old_name', 'old_path', 'old_port',
            'paster_path', 'vh_path']:
            state[attr] = params[attr]
        global_state.append(state)
        with open(STORE, 'w') as fo:
            json.dump(global_state, fo, indent=4, sort_keys=True)
    except:
        print ('%sWarning: an error occurred when attempting to save state to'
            ' %s. Because of this, this script cannot be used in the future to'
            ' destroy or shut down this OLD.%s' % (ANSI_WARNING, STORE,
            ANSI_ENDC))


def get_state():
    """Return our global state (a record of the OLDs that we have built) as
    encoded in the file at STORE, defaults to ./.buildold.json.

    """

    global_state = []
    if os.path.isfile(STORE):
        try:
            global_state = json.load(open(STORE))
            assert type(global_state) is type([])
        except:
            print ('%sWarning: unable to retrieve buildold\'s state at %s. The'
                ' file exists but is not properly formatted. If this build'
                ' succeeds, we will overwrite it.%s' % (ANSI_WARNING, STORE,
                ANSI_ENDC))
            global_state = []
    return global_state


def destroy(params, global_state):
    """Destroy the OLD with name `params['old_name']`. `global_state` is a list
    of dicts representing the OLDs that this buildold.py has built.

    Note: we prompt the user to confirm that they want to proceed with the
    destruction.

    """

    print '\n%sOLD Destroyer.%s' % (ANSI_HEADER, ANSI_ENDC)

    # Check if we have a record of this to-be-destroyed OLD.
    try:
        destroyee_params = [o for o in global_state
            if o['old_name'] == params['old_name']][0]
    except:
        sys.exit('%sSorry, this script has no record of an OLD named %s. If it'
            ' exists, you will need to destroy it manually.%s' % (ANSI_FAIL,
            params['old_name'], ANSI_ENDC))

    # Make sure the user wants to do this.
    proceed = raw_input('%sAre you sure that you want to destroy the OLD named'
        ' %s? THIS CANNOT BE UNDONE. Enter \'y\' or \'Y\' to proceed with the'
        ' destruction. You may want to backup its database and files, prior'
        ' to destruction.%s' % (ANSI_WARNING, params['old_name'], ANSI_ENDC))
    if proceed not in ['y', 'Y']:
        sys.exit('Aborted, phewf.')

    # Get MySQL password and verify we can access MySQL.
    params = destroyee_params
    params['mysql_pwd'] = None
    prompt_for_mysql_password(params)
    validate_mysql_credentials(params)

    # Remove the params for the to-be-destroyed OLD from buildold.py's state.
    global_state = [o for o in global_state
        if o['old_name'] != params['old_name']]
    with open(STORE, 'w') as fo:
        json.dump(global_state, fo, indent=4, sort_keys=True)

    # Do the destroyin'
    actions_taken = params['actions']
    if 'init script' in actions_taken:
        remove_init_script(params)
    if 'cronjob created' in actions_taken:
        destroy_cronjob(params)
    if 'virtual hosts file modified' in actions_taken:
        restore_virtual_hosts_file(params)
    if 'served app' in actions_taken:
        stop_serving(params)
    if 'mysql database created' in actions_taken:
        drop_database(params)
    if 'created old directory' in actions_taken:
        destroy_old_directory(params)
    print 'Done.'


def build(params):
    """Build an OLD, given `params`.

    """

    print '\n%sOLD Builder.%s' % (ANSI_HEADER, ANSI_ENDC)
    print 'Building an OLD called %s%s%s.' % (ANSI_OKGREEN, params['old_name'],
        ANSI_ENDC)

    params['old_port'] = get_next_available_port(params)
    params['old_path'] = os.path.join(params['apps_path'],
        params['old_dir_name'])
    params['db_name'] = params['old_dir_name']

    create_dirs(params)
    make_config(params)
    create_database(params)
    edit_config(params)
    setup_app(params)
    fix_tag_name_col(params)
    serve(params)
    add_virtual_host(params)
    restart_apache(params)
    create_cronjob(params)
    init_script(params)
    save_state(params)

    print ('The %s OLD is being served at %shttps://%s/%s%s.\nIts files are'
        ' stored at %s%s%s.' % (params['old_name'], ANSI_OKGREEN, params['host'],
        params['old_dir_name'], ANSI_ENDC, ANSI_OKGREEN,
        os.path.join(params['apps_path'], params['old_dir_name']), ANSI_ENDC))
    print 'Done.'


@catcherror
def init_script(params):
    """Create and install a Debian-based init script to restart the OLD in case
    the server goes down.

    """

    print 'Creating an init script.'

    pid_pth = os.path.join(params['old_path'], 'old.pid')
    log_pth = os.path.join(params['old_path'], 'log', 'paster-old.log')
    cnf_pth = os.path.join(params['old_path'], 'production.ini')
    init_name = '%s_init' % params['old_dir_name']

    script = """#!/bin/sh -e
### BEGIN INIT INFO
# Provides:          %s
# Required-Start:    mysql networking
# Required-Stop:     mysql networking
# Default-Start:     2 3 4 5
# Default-Stop:      0 1 6
# Short-Description: Start an OLD web application daemon at boot time
# Description:       Start an OLD web application daemon at boot time
### END INIT INFO

cd %s

case "$1" in
start)
    %s serve --daemon --pid-file=%s --log-file=%s %s start
    ;;
stop)
    %s serve --daemon --pid-file=%s --log-file=%s %s stop
    ;;
restart)
    %s serve --daemon --pid-file=%s --log-file=%s %s restart
    ;;
force-reload)
    %s serve --daemon --pid-file=%s --log-file=%s %s restart
    /etc/init.d/apache2 restart
    ;;
*)
    echo $"Usage: $0 {start|stop|restart|force-reload}"
    exit 1
esac

exit 0

    """ % (init_name, params['old_path'],
            params['paster_path'], pid_pth, log_pth, cnf_pth,
            params['paster_path'], pid_pth, log_pth, cnf_pth,
            params['paster_path'], pid_pth, log_pth, cnf_pth,
            params['paster_path'], pid_pth, log_pth, cnf_pth)

    tmp_pth = '/tmp/%s' % init_name
    initd_pth = '/etc/init.d/%s' % init_name
    with open(tmp_pth, 'w') as f:
        f.write(script)

    fail_msg = ('Something went wrong when attempting to install the init'
        ' script. You can try doing it yourself. See'
        ' http://pylonsbook.com/en/1.1/deployment.html. Also check to see if'
        ' there is a file at %s and whether it contains errors.' % (
        initd_pth,))

    cp = Popen(['sudo', 'cp', tmp_pth, initd_pth], stdout=PIPE, stderr=STDOUT)
    stdout, nothing = cp.communicate()
    try:
        assert stdout.strip() == ''
    except:
        print fail_msg
        return

    chmod = Popen(['sudo', 'chmod', 'o+x', initd_pth], stdout=PIPE,
        stderr=STDOUT)
    stdout, nothing = chmod.communicate()
    try:
        assert stdout.strip() == ''
    except:
        print fail_msg
        return

    update = Popen(['sudo', '/usr/sbin/update-rc.d', '-f', init_name,
        'defaults'], stdout=PIPE, stderr=STDOUT)
    stdout, nothing = update.communicate()
    try:
        exp = 'Adding system startup for %s' % initd_pth
        assert exp in stdout
        params['actions'].append('init script')
    except:
        print fail_msg


def remove_init_script(params):
    """Remove the init script.

    """

    print 'Removing init script.'

    init_name = '%s_init' % params['old_dir_name']
    initd_pth = '/etc/init.d/%s' % init_name
    fail_msg = ('%sSomething may have gone wrong when attempting to remove'
        ' the init script.%s' % (ANSI_WARNING, ANSI_ENDC))
    if os.path.isfile(initd_pth):
        rm = Popen(['sudo', 'rm', initd_pth], stdout=PIPE, stderr=STDOUT)
        stdout, nothing = rm.communicate()
        try:
            assert stdout.strip() == ''
        except:
            print fail_msg
            return

        update = Popen(['sudo', 'update-rc.d', '-f', init_name, 'remove'],
            stdout=PIPE, stderr=STDOUT)
        stdout, nothing = update.communicate()
        try:
            exp = 'Removing any system startup links for %s' % initd_pth
            assert exp in stdout
        except:
            print fail_msg


def list_built(global_state):
    """Print out info on the OLDs that were built by this script.

    """

    if global_state:
        print '%sOLDs built here by this script:%s' % (ANSI_HEADER, ANSI_ENDC)
        for old in global_state:
            print '%s%s%s in %s being served at %shttps://%s/%s%s.' % (
                ANSI_OKGREEN, old['old_name'], ANSI_ENDC, old['old_path'],
                ANSI_OKGREEN, old['host'], old['old_dir_name'], ANSI_ENDC)
    else:
        print '%sNo OLDs have been built here by this script.%s' % (
            ANSI_HEADER, ANSI_ENDC)


def create_dative_servers_file(params, global_state):
    """Create a JSON file summarizing the OLD instances being served by this
    build script. This file can be served by a Dative web site in order to
    define the default available servers.

    """

    path = params['dative_servers']
    if os.path.isfile(path):
        r = raw_input('There is already a file at %s. Do you want to overwrite'
            ' it? ' % path)
        if r not in ['y', 'Y']:
            sys.exit('%sDative servers file was NOT written at %s.%s' % (
                ANSI_WARNING, path, ANSI_ENDC))
    with open(path, 'w') as fo:
        servers = []
        for old in global_state:
            old_dict = {
                'name': '%s OLD' % old['old_name'].capitalize(),
                'type': 'OLD',
                'url': 'https://%s/%s' % (old['host'], old['db_name']),
                'serverCode': None,
                'corpusServerURL': None,
                'website': 'http://www.onlinelinguisticdatabase.org'
            }
            servers.append(old_dict)
        json.dump(servers, fo, indent=4, sort_keys=True)


def main():
    params, global_state = get_params()
    if params['list']:
        list_built(global_state)
    elif params['dative_servers']:
        create_dative_servers_file(params, global_state)
    elif params['destroy']:
        destroy(params, global_state)
    else:
        build(params)


if __name__ == '__main__':
    main()

