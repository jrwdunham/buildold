================================================================================
  Build OLD
================================================================================

This project contains two Python scripts to be used as command-line tools:

1. installold.py installs the OLD (on Ubuntu 10.04, at least)
2. buildold.py builds OLDs once the OLD software is installed.


installold.py
================================================================================

A command line utility for installing the OLD, on Ubuntu 10.04. Additional
platforms may be supported in future versions.


Usage
--------------------------------------------------------------------------------

To install the OLD::

    $ ./installold.py


buildold.py
================================================================================

A command line utility for building (and serving) OLD applications. The server
that this is run on must already have the OLD software
(https://github.com/jrwdunham/old) and all of its dependencies installed. This
is what `buildold` does:

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
--------------------------------------------------------------------------------

To build and serve an OLD called "bla" (e.g., for Blackfoot)::

    $ ./buildold.py bla

Additional information is required to build an OLD. You can specify it in
options or let the script prompt you for it. The easiest, though, is to use the
`--config-file` option to specify a path to a JSON config file that holds this
information in an object with any of the following keys: 'mysql_user',
'paster_path', 'apps_path', 'vh_path', or 'host'::

    $ ./buildold.py bla --config-file=buildold.conf

To see available options::

    $ ./buildold.py -h

To destroy an OLD that was built using this script::

    $ ./buildold.py bla --destroy


Dependencies
--------------------------------------------------------------------------------

Python-crontab (https://pypi.python.org/pypi/python-crontab) should be
installed if you want the OLD-restart cronjob to be created for you. But the
script will still work without it.


Warnings
--------------------------------------------------------------------------------

1. This script assumes that you are serving OLDs on a Debian/Ubuntu Linux
   server; it currently (probably) won't work on Mac or RHEL/CentOS. It
   basically follows the instructions of Chapter 21 Deployment of The
   Definitive Guide to Pylons.

2. You'll run into problems if you change the `vh_path` option after you have
   installed OLDs with a different Apache virtual hosts config file. Don't do
   this.



TODOs
================================================================================

1. functionality for:

    - stop serving an OLD and redirect requests to a notification page.

    - start serving an already-built OLD that has been stopped.

