# -*- coding: utf-8 -*-
'''
General management functions for salt, tools like seeing what hosts are up
and what hosts are down
'''

# Import python libs
import os
import subprocess

# Import salt libs
import salt.key
import salt.client
import salt.output


def status(output=True):
    '''
    Print the status of all known salt minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.status
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.ping', timeout=__opts__['timeout'])

    key = salt.key.Key(__opts__)
    keys = key.list_keys()

    ret = {}
    ret['up'] = sorted(minions)
    ret['down'] = sorted(set(keys['minions']) - set(minions))
    if output:
        salt.output.display_output(ret, '', __opts__)
    return ret


def key_regen():
    '''
    This routine is used to regenerate all keys in an environment. This is
    invasive! ALL KEYS IN THE SALT ENVIRONMENT WILL BE REGENERATED!!

    The key_regen routine sends a command out to minions to revoke the master
    key and remove all minion keys, it then removes all keys from the master
    and prompts the user to restart the master. The minions will all reconnect
    and keys will be placed in pending.

    After the master is restarted and minion keys are in the pending directory
    execute a salt-key -A command to accept the regenerated minion keys.

    The master *must* be restarted within 60 seconds of running this command or
    the minions will think there is something wrong with the keys and abort.

    Only Execute this runner after upgrading minions and master to 0.15.1 or
    higher!

    CLI Example:

    .. code-block:: bash

        salt-run manage.key_regen
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'saltutil.regen_keys')

    for root, dirs, files in os.walk(__opts__['pki_dir']):
        for fn_ in files:
            path = os.path.join(root, fn_)
            try:
                os.remove(path)
            except os.error:
                pass
    msg = ('The minion and master keys have been deleted.  Restart the Salt\n'
           'Master within the next 60 seconds!!!\n\n'
           'Wait for the minions to reconnect.  Once the minions reconnect\n'
           'the new keys will appear in pending and will need to be re-\n'
           'accepted by running:\n'
           '    salt-key -A\n\n'
           'Be advised that minions not currently connected to the master\n'
           'will not be able to reconnect and may require manual\n'
           'regeneration via a local call to\n'
           '    salt-call saltutil.regen_keys')
    print(msg)


def down(removekeys=False):
    '''
    Print a list of all the down or unresponsive salt minions
    Optionally remove keys of down minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.down
        salt-run manage.down removekeys=True
    '''
    ret = status(output=False).get('down', [])
    for minion in ret:
        if removekeys:
            subprocess.call(["salt-key", "-qyd", minion])
        else:
            salt.output.display_output(minion, '', __opts__)
    return ret


def up():  # pylint: disable=C0103
    '''
    Print a list of all of the minions that are up

    CLI Example:

    .. code-block:: bash

        salt-run manage.up
    '''
    ret = status(output=False).get('up', [])
    for minion in ret:
        salt.output.display_output(minion, '', __opts__)
    return ret


def versions():
    '''
    Check the version of active minions

    CLI Example:

    .. code-block:: bash

        salt-run manage.versions
    '''
    client = salt.client.LocalClient(__opts__['conf_file'])
    minions = client.cmd('*', 'test.version', timeout=__opts__['timeout'])

    labels = {
        -1: 'Minion requires update',
        0: 'Up to date',
        1: 'Minion newer than master',
    }

    version_status = {}

    comps = salt.__version__.split('-')
    if len(comps) == 3:
        master_version = '-'.join(comps[0:2])
    else:
        master_version = salt.__version__
    for minion in minions:
        comps = minions[minion].split('-')
        if len(comps) == 3:
            minion_version = '-'.join(comps[0:2])
        else:
            minion_version = minions[minion]
        ver_diff = cmp(minion_version, master_version)

        if ver_diff not in version_status:
            version_status[ver_diff] = []
        version_status[ver_diff].append(minion)

    ret = {}
    for key in version_status:
        for minion in sorted(version_status[key]):
            ret.setdefault(labels[key], []).append(minion)

    salt.output.display_output(ret, '', __opts__)
    return ret


def bootstrap(version="develop",
              script="http://bootstrap.saltstack.org",
              hosts=""):
    '''
    Bootstrap minions with salt-bootstrap

    Options:
        version: git tag of version to install [default: develop]
        script: Script to execute [default: http://bootstrap.saltstack.org]
        hosts: Comma separated hosts [example: hosts="host1.local,host2.local"]

    CLI Example:

    .. code-block:: bash

        salt-run manage.bootstrap hosts="host1,host2"
        salt-run manage.bootstrap hosts="host1,host2" version="v0.17"
        salt-run manage.bootstrap hosts="host1,host2" version="v0.17" script="https://raw.github.com/saltstack/salt-bootstrap/develop/bootstrap-salt.sh"

    '''
    for host in hosts.split(","):
        # Could potentially lean on salt-ssh utils to make
        # deployment easier on existing hosts (i.e. use sshpass,
        # or expect, pass better options to ssh etc)
        subprocess.call(["ssh", "root@" + host, "python -c 'import urllib; "
                        "print urllib.urlopen("
                        "\"" + script + "\""
                        ").read()' | sh -s -- git " + version])
