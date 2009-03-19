piuparts README
---------------

Author: Lars Wirzenius 
Email: <liw@iki.fi>


Introduction
~~~~~~~~~~~~

                This is a tool for testing that .deb packages can be
                installed, upgraded, and removed without problems. The
                name, a variant of something suggested by Tollef Fog
                Heen, is short for "package installation, upgrading, and
                removal testing suite".
                
                See the manual page for more information about using
                the program.
                
                You need at least Python 2.3 and debootstrap. The
                version of debootstrap in the Debian 3.1 release
                (codename sarge) is too old.
                
                piuparts is licensed under the GNU General Public
                License, version 2.
                

Distrubuted testing
~~~~~~~~~~~~~~~~~~~

                As part of the quality assurance effort of Debian, I run
                piuparts on the Debian package archive. This requires a
                lot of processing power, and so the work is distributed
                over several hosts.

                There is one central machine, the master, and any number
                of slave machines. Each slave machine connects to the
                master, via ssh, and runs the piuparts-master program to
                report results of packages it has tested already, and to
                get more work.
                
                To set this up for yourself, the following steps should
                suffice:
                
                 1. Pick a machine to run the master. It cannot be a chroot,
                    but a etch system is good enough.
                 2. Install piuparts on it.
                 3. Create an account for the master.
                 4. Configure /etc/piuparts/piuparts-master.conf 
                    appropriately.
                 
                 5. Pick one or more slaves to run the slave. You can use
                    the machine running the master also as a slave. Etch is
		    fine, it can even be in a chroot.
                 6. Install piuparts on it.
                 7. Configure /etc/piuparts/piuparts-slave.conf
                    appropriately.
                 8. Create an account for the slave. This must be different
                    from the master account.
                 9. Create an ssh keypair for the slave. No passphrase.
                10. Add the slave's public key to the master's 
                    .ssh/authorized_keys
		11. Configure sudo on the slave machine to allow the slave
		    account run /usr/sbin/piuparts as root without password
		    (otherwise you'll be typing in a password all the time).

                12. Run /usr/share/piuparts/piuparts-slave.py on the slave
		    accounts. Packages that are installed want to use
		    /dev/tty, so you can't do this from cron. Also, you'll
		    want to keep an eye on what is happening, to catch
		    runaway processes and stuff.

                13. The logs go into the master account, into
                    subdirectories.

                Please note that running piuparts this way is somewhat
                risky, to say the least. There are security implications
                that you want to consider. It's best to do it on
                machines that you don't mind wiping clean at a moment's
                notice, and preferably so that they don't have direct
                network access.


Distributed piuparts testing protocol
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                
                The slave machine and the piuparts-master program
                communicate using a simplistic line based protocol. Ssh
                takes care of authentication, so there is nothing in the
                protocol for that. The protocol is transaction based:
                the slave gives a command, the master program responds.
                Commands and responses can be simple (a single line) or
                long (a status line plus additional data lines). Simple
                commands and responses are of the following format:
                
                    keyword arg1 arg2 arg3 ... argN
                    
                The keyword is a command or status code ("ok"), and it
                and the arguments are separated by spaces. An argument
                may not contain a space.
                
                A long command or response is deduced from the context:
                certain commands always include additional data, and
                certain commands always get a long response, if
                successful (error responses are always simple). The
                first line of a long command or response is the same as
                for a simple one, the additional lines are prefixed with
                a space, and followed by a line containing only a
                period.
                
                A sample session (">>" indicates what the slave sends,
                "<<" what the master responds with):
                
                    << hello
                    >> pass liwc 1.2.3-4
                    >>  The piuparts
                    >>  log file comes
                    >>  here
                    >> .
                    << ok
                    >> reserve
                    << ok vorbisgain 2.3-4
                
                Here the slave first reports a successful test of
                package liwc, version 1.2.3-4, and sends the piuparts
                log file for it. Then it reserves a new package to test
                and the master gives it vorbisgain, version 2.3-4.
                
                The communication always starts with the master saying
                "hello". The slave shall not speak until the master has
                spoken.
                
                Commands and responses in this protocol:
                
                    Command: reserve
                    Success: ok <packagename> <packageversion>
                    Failure: error
                    
                        Slave asks master to reserve a package (a
                        particular version of it) for the slave to test.
                        The slave may reserve any number of packages to
                        test. If the transaction fails, there are no
                        more packages to test, and the slave should
                        disconnect, wait some time and try again.
                    
                    Command: unreserve <packagename> <packageversion>
                    Success: ok
                    
                        Slave informs master it cannot test the desired
                        version of a package (perhaps it went away from
                        the mirror?).
                
                    Command: pass <packagename> <packageversion>
                              log file contents
                             .
                    Success: ok
                    
                        Slave reports that it has tested a particular
                        version of a package and that the package passed
                        all tests. Master records this and stores the
                        log file somewhere suitable.
                        
                    Command: fail <packagename> <packageversion>
                              log file contents
                             .
                    Success: ok
                    
                        Same as "pass", but package failed one or more tests.
                        
                    Command: untestable <packagename> <packageversion>
                              log file contents
                             .
                    Success: ok
                    
                        Slave reports that a particular package is
                        untestable, possibly because it insists on
                        interacting with the user.
                        
                In all cases, if the master cannot respond with "ok"
                (e.g., because of a disk error storing a log file), it
                aborts and the connection fails. The slave may only
                assume the command has succeeded if the master responds
                with "ok".
                
                The master may likewise abort, without an error message,
                if the slave sends garbage, or sends too much data.


Master configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~

                piuparts-master uses the configuration file
                /etc/piuparts/piuparts-master.conf. The syntax is defined
                by the Python ConfigParser class, and is, briefly, like
                this:
                
                    [master]
                    foo = bar
                    
		where "master" is the name of a section.  By default,
		piuparts-master.py uses the "master" section in the master
		configuration file, but you can tell it to use another
		section by giving the name of that section as an argument.
		"foo" is the name of a configuration item, and "bar" is the
		value.  If a section other than "master" is used, all the
		piuparts logs for that section are kept in a subdirectory by
		the name of the section.
                
                The following configuration items are defined for the master:
                
                * "log-file" is the name of a file to where the master should
                  write its log messages. In the default configuration file
                  it is "/dev/null", that is, log messages are not put in a
                  file.

                * "packages-url" is a URL to the Packages.bz2 file for your
                  mirror. It is usually best to use the Packages.bz2 for
                  sid (unstable), unless you know what you're doing. For
                  example, you might use
                  
                      http://ftp.debian.org/debian/dists/sid/main/
                      binary-i386/Packages.bz2
          
                  (all on one line, of course), but you really do want
                  to replace "ftp.debian.org" with the name of your local
                  mirror.

                Both configuration items must be in the configuration file,
                or master will refuse to run.


Slave configuration file
~~~~~~~~~~~~~~~~~~~~~~~~

                piuparts-slave uses the configuration file
                /etc/piuparts/piuparts-slave.conf. It has the same
                general syntax as the master's configuration file. The
		default section is called "slave" (again, you can use a
		different section by specifying it on the command-line) and
		the configuration items are as follows:
                
                * "idle-sleep" is the length of time the slave should wait
                  before querying the master again if the master didn't have
                  any new packages to test. In seconds, so a value of 300
                  would mean five minutes, and that seems to be a good
                  value when there are fairly few slaves per master.
                  
                * "master-host" is the host where the master exists. The
                  slave will give this host to ssh.
                  
                * "master-user" is the username of the master. The slave will
                  log in using this username.
                
                * "master-directory" is the directory where the master keeps
                  its files. Can be relative to the master's home directory.
                  
                * "master-command" is the command to run on master-host to
                  start the master. When the master has been installed from
                  the Debian package, the command is 
		  "python /usr/share/piuparts/piuparts-master.py".  If you
		  want to use a section in the master configuration file
		  other than "master", append the section name to this
		  command.  For example, if the master configuration file has
		  a "sid-ia64" section that you want to use, the command
		  should be
		  "python /usr/share/piuparts/piuparts-master.py sid-ia64".
                  
                * "mirror" tells the slave which mirror it is to use. The
                  slave gives this to piuparts when it runs it.
                  
                * "piuparts-cmd" is the command the slave uses to start
                  piuparts. It should include "sudo" if necessary so that
                  piuparts runs with sufficient priviledges to do its testing
                  (and that means root priviledges).
                  
                * "distro" is the distribution the slave should tell piuparts
                  to use for basic install/purge testing.
                  
                * "chroot-tgz" is the name of the file the slave should
                  use for the tarball to keep the chroot for the basic
                  install/purge testing. If the tarball doesn't exist, the
                  slave creates it.

                * "upgrade-test-distros" is the space delimited list of
                  distributions the slave should use for testing upgrades
                  between distributions (i.e., Debian versions). Currently,
		  "etch lenny sid" is a good choice.  Make this empty if you
		  do not want to run upgrade tests.

                * "upgrade-test-chroot-tgz" is the name of the file the slave
                  should use for the tarball to keep the chroot for the
                  first distribution in upgrade-test-distros. If the file
                  does not exist, the slave creates it.

                * "max-reserved" is the maximum number of packages the
                  slave will reserve at once. It should be large enough
                  that the host that runs master is not unduly stressed by
                  frequent ssh logins and running master (both of which
                  take quite a bit of CPU cycles), yet at the same time it
                  should not be so large that one slave grabs so many
                  packages all other slaves just sit idle. The number
                  obviously depends on the speed of the slave. A good
                  value seems to be enough to let the slave test packages
                  for about an hour before reporting results and reserving
                  more. For a contemporary AMD64 machine with a reasonably
                  fast disk subsystem the value 50 seems to work fine.

		* "keep-sources-list" controls whether the slave runs
		  piuparts with the "--keep-sources-list" option.  This
		  option does not apply to upgrade tests.  The value should
		  be "yes" or "no", with the default being "no".  Use this
		  option for dists that you need a custom sources.list for,
		  such as "stable-proposed-updates".

                * "debug" tells the slave whether to log debug level
                  messages. The value should be "yes" or "no", with the
                  default being "no".

                Some of the configuration items are not required, but it
                is best to set them all to be sure what the configuration
                actually is.

How to use piuparts in 5 minutes
--------------------------------

* Basic Usage
~~~~~~~~~~~~~

Testing your packages with piuparts is as easy as typing at the console prompt:

    # piuparts sm_0.6-1_i386.deb

Note that in order to work, piuparts has to be executed as user root, so you 
need to be logged as root or use sudo.

This will create a sid chroot with debootstrap, where it'll test your package.

If you want to test your package in another release, for example, lenny, you can
do so with:

    # piuparts sm_0.6-1_i386.deb -d lenny

By default, this will read the first mirror from your /etc/apt/sources.list 
file. If you want to specify a different mirror you can do it with the option 
-m:

    # piuparts sm_0.6-1_i386.deb -m http://ftp.de.debian.org/debian


* Some tips
~~~~~~~~~~~

If you use piuparts on a regular basis, waiting for it to create a chroot every 
time takes too much time, even if you are using a local mirror or a caching tool 
such as approx. 

Piuparts has the option of using a tarball as the contents of the initial chroot, 
instead of building a new one with debootstrap. A easy way to use this option 
is use a tarball created with pbuilder. If you are not a pbuilder user, you can 
create this tarball with the command (again, as root):

    # puilder create
 
then you only have to remember to update this tarball with:

    #  pbuilder update.

To run piuparts using this tarball:

    # piuparts -p sm_0.6-1_i386.deb

If you want to use your own pre-made tarball:

    # piuparts --basetgz=/path/to/my/tarball.tgz sm_0.6-1_i386.deb

Piuparts also has the option of using a tarball as the contents of the initial
chroot, instead of building a new one with pbuilder. You can save a tarball
for later use with the -s (--save) piuparts option. Some people like this, 
others prefer to only have to maintain one tarball. Read the piuparts manpage 
about the -p, -b and -s options


* Piuparts tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, piuparts does two tests:
1 - Installation and purging test.
2 - Installation, upgrade and purging tests.

The first test installs the package in a minimal chroot, removes it and purges
it. The second test installs the current version in the archive of the given 
packages, then upgrades to the new version (deb files given to piuparts in the
input), removes and purges.

If you only want to perfom the first test, you can use the option: 
--no-upgrade-test  


* Analyzing piuparts results
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When piuparts finishes all the tests satisfactorily, you will get these lines
as final output:

    0m39.5s INFO: PASS: All tests.
    0m39.5s INFO: piuparts run ends.

Anyway, it is a good idea to read the whole log in order to discover possible 
problems that did not stop the piuparts execution.

If you do not get those lines, piuparts has failed during a test. The latest 
lines should give you a pointer to the problem with your package.

Custom scripts with piuparts
------------------------------

You can specify several custom scripts to be run inside piuparts.
You have to store them in a directory and give it as argument to
piuparts: --scriptsdir=/dir/with/the/scripts

The scripts can be run:

    Before *installing* your package. The name of the script must
    start with:
    pre_install_

    After *installing* your package and its deps. In the case of the 
    upgrade test, it is after install and upgrade. The name of the 
    script must start with:
    post_install_

    After *removing* your package, The name of the script must start with:
    post_remove_

    After *purging* your package, The name of the script must start with:
    post_purge_

    Before *upgrading* your package, once the current version in the archive
    has been installed (this is done in the second test, "Installation, 
    upgrade and purging test"). The name of the script must start with:
    pre_upgrade_

    Before upgrading the chroot to another distro and after upgrading:
    pre_distupgrade_
    post_distupgrade_

You can run several scripts in every step, they are run in alphabetical 
order.

The scripts are run *inside* the piuparts chroot and only can be shell 
scripts, if you want to run Python or Perl scripts, you have to install 
Python or Perl. The chroot where piuparts is run is minized and does not 
include Perl.


It would be interesting to declare some piuparts variables like the name
of the current testing packages, and be able to use this variable in the 
custom scripts. But this option is not available yet.

Example script:

'$cat post_install_number.sh'
----
#!/bin/bash

number=`dpkg -l | wc -l`
echo "There are $number packages installed."
exit 0
----

