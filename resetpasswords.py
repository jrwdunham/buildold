"""This script can be used to change/reset the passwords of all users on a
given OLD and send them emails to that effect.

TODO: set up command-line arguments to make this general-purpose.

"""

import smtplib
import random
import string
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import old_client
import pprint
import sys
import optparse
import getpass

def sendemail(params):
    """Send an email via gmail, using info in `params`.

    """

    fromaddr = params['fromaddr']
    toaddrs = params['toaddrs']
    mymsg = params['mymsg']
    username = params['username']
    password = params['password']
    subject = params['subject']

    # The actual mail send
    server = smtplib.SMTP('smtp.gmail.com:587')
    server.starttls()
    server.login(username, password)
    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg.attach(MIMEText(mymsg))
    server.sendmail(fromaddr, toaddrs, msg.as_string())
    server.quit()


def get_email_msg(username, password, language):

    return ('''
Dear %s Dative/OLD user,

You are receiving this email because the %s Dative/OLD system has moved
and your password has been changed.

Your database can now be accessed at http://app.dative.ca. When you go to log
in, you should find "%s OLD" in your list of servers. Choose that one and
enter the following username and password.

- username: %s
- password: %s

Please change your password when you first log in by going to the users page
(Resources > Users) and editing your user.

If you need help, you can email me. You may also find useful information at the
Dative or OLD web sites:

    - http://www.dative.ca
    - http://www.onlinelinguisticdatabase.org

Thank you,

Joel
''' % (language, language, language, username, password)).strip()


def main():

    # Get an OLD client.
    old_url = '' # URL of target OLD
    old_username = '' # username of OLD admin on target OLD
    old_password = "" # password of OLD admin on target OLD
    old_language = '' # Name of language that the target OLD is about.
    c = old_client.OLDClient(old_url)

    # Log in to the OLD.
    logged_in = c.login(old_username, old_password)
    if not logged_in:
        sys.exit(u'Unable to log in to %s with username %s and password %s.'
            u' Aborting.' % (old_url, old_username, old_password))

    # Get users.
    users = c.get('users')

    for user in users:
        if user['username'] == old_username:
            continue
        username = user['username']
        new_password = genpwd()
        user['password'] = new_password
        user['password_confirm'] = new_password
        if user['input_orthography']:
            user['input_orthography'] = user['input_orthography']['id']
        if user['output_orthography']:
            user['output_orthography'] = user['output_orthography']['id']
        if user['markup_language'] == 'restructuredText':
            user['markup_language'] = 'reStructuredText'
        resp = c.update('users/%d' % user['id'], user)
        if resp.get('username') == username:
            print 'Successfully changed password of %s to %s.' % (
                username, new_password)
            if user.get('email'):
                mymsg = get_email_msg(username, new_password, language)
                params = {
                    'fromaddr': '', # a Gmail source address
                    'toaddrs': user['email'],
                    'mymsg': mymsg,
                    'username': '', # a Gmail username
                    'password': '', # Gmail password
                    'subject': '' # subject of email
                }
                sendemail(params)
            else:
                print 'Could not send email; %s has no email address' % username
        else:
            print 'Failed to change password of %s.' % username


def genpwd():
    """Generate a new OLD-compatible password for a user.

    """

    up = string.ascii_uppercase
    dn = string.ascii_lowercase
    di = string.digits
    pu = ',!{}[]().;:/'
    p1 = ''.join(random.choice(up + dn + di + pu) for x in range(4))
    p2 = random.choice(up)
    p3 = random.choice(dn)
    p4 = random.choice(di)
    p5 = random.choice(pu)
    return p1 + p2 + p3 + p4 + p5


if __name__ == '__main__':
    main()

