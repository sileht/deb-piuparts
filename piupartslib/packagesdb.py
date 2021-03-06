# Copyright 2005 Lars Wirzenius (liw@iki.fi)
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.
# 
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
# 
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA


"""Packages database for distributed piuparts processing

This module contains tools for keeping track of which packages have
been tested, the test results, and for determining what to test next.

Lars Wirzenius <liw@iki.fi>
"""


import dircache
import os
import tempfile
import UserDict
import apt_pkg

from piupartslib.dependencyparser import DependencyParser

apt_pkg.init_system()


def rfc822_like_header_parse(input):
    headers = []
    while 1:
        line = input.readline()
        if not line or line in ["\r\n", "\n"]:
            break
        if headers and line and line[0].isspace():
            headers[-1] = headers[-1] + line
        else:
            headers.append(line)
    return headers

class Package(UserDict.UserDict):

    def __init__(self, headers):
        UserDict.UserDict.__init__(self)
        self.headers = headers
        for header in headers:
            name, value = header.split(":", 1)
            self[name.strip()] = value.strip()
        self._parsed_deps = {}
        self._parsed_alt_deps = {}
        self._rrdep_count = None
        self._block_count = None

    def _parse_dependencies(self, header_name):
        if header_name in self._parsed_deps:
            depends = self._parsed_deps[header_name]
        else:
            parser = DependencyParser(self[header_name])
            depends = parser.get_dependencies()
            depends = [alternatives[0].name for alternatives in depends]
            self._parsed_deps[header_name] = depends
        return depends

    def _parse_alternative_dependencies(self, header_name):
        if header_name in self._parsed_alt_deps:
            depends = self._parsed_alt_deps[header_name]
        else:
            parser = DependencyParser(self[header_name])
            depends = parser.get_dependencies()
            depends = [[alt.name for alt in alternatives] for alternatives in depends]
            self._parsed_alt_deps[header_name] = depends
        return depends

    # first alternative only - [package_name...]
    def dependencies(self):
        vlist = []
        for header in ["Depends", "Pre-Depends"]:
            if header in self:
                vlist += self._parse_dependencies(header)
        return vlist

    # all alternatives - [[package_name...]...]
    def all_dependencies(self, header_name=None):
        headers = ["Depends", "Pre-Depends"]
        if header_name is not None:
            headers = [header_name]
        vlist = []
        for header in headers:
            if header in self:
                vlist += self._parse_alternative_dependencies(header)
        return vlist

    def prefer_alt_depends(self, header_name,dep_idx,dep):
        if header_name in self:
            if header_name not in self._parsed_deps:
                  self._parse_dependencies(header_name)
            if self._parsed_deps[header_name][dep_idx]:
                self._parsed_deps[header_name][dep_idx] = dep

    def provides(self):
        vlist = []
        for header in ["Provides"]:
            if header in self:
                vlist += self._parse_dependencies(header)
        return vlist

    def is_testable(self):
        """Are we testable at all? Required aren't."""
        return self.get("Priority", "") != "required"

    def rrdep_count(self):
        """Get the recursive dependency count, if it has been calculated"""
        if self._rrdep_count == None:
            raise Exception('Reverse dependency count has not been calculated')
        return(self._rrdep_count)

    def set_rrdep_count(self, val):
        self._rrdep_count = val

    def block_count(self):
        """Get the number of packages blocked by this package"""
        if self._block_count == None:
            raise Exception('Block count has not been calculated')
        return(self._block_count)

    def set_block_count(self, val):
        self._block_count = val

    def dump(self, output_file):
        output_file.write("".join(self.headers))


class PackagesFile(UserDict.UserDict):

    def __init__(self, input):
        UserDict.UserDict.__init__(self)
        self._read_file(input)

    def _read_file(self, input):
        """Parse a Packages file and add its packages to us-the-dict"""
        while True:
            headers = rfc822_like_header_parse(input)
            if not headers:
                break
            p = Package(headers)
            if p["Package"] in self:
                q = self[p["Package"]]
                if apt_pkg.version_compare(p["Version"], q["Version"]) <= 0:
                    # there is already a newer version
                    continue
            self[p["Package"]] = p


class LogDB:

    def listdir(self, dirname):
        return dircache.listdir(dirname)

    def exists(self, pathname):
        try:
            cache = self.exists_cache
        except AttributeError:
            self.exists_cache = {}
            cache = self.exists_cache
        if pathname not in cache:
            cache[pathname] = os.path.exists(pathname)
        return cache[pathname]

    def open_file(self, pathname, mode):
        return file(pathname, mode)

    def remove_file(self, pathname):
        os.remove(pathname)

    def _log_name(self, package, version):
        return "%s_%s.log" % (package, version)

    def log_exists(self, package, subdirs):
        log_name = self._log_name(package["Package"], package["Version"])
        for subdir in subdirs:
            if self.exists(os.path.join(subdir, log_name)):
                return True
        return False

    def create(self, subdir, package, version, contents):
        (fd, temp_name) = tempfile.mkstemp(dir=subdir)
        os.close(fd)

        # tempfile.mkstemp sets the file mode to be readable only by owner.
        # Let's make it follow the umask.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp_name, 0666 & ~umask)

        full_name = os.path.join(subdir, self._log_name(package, version))
        try:
            os.link(temp_name, full_name)
        except OSError, detail:
            os.remove(temp_name)
            return False
        os.remove(temp_name)
        f = self.open_file(full_name, "w")
        f.write(contents)
        f.close()
        return True

    def remove(self, subdir, package, version):
        full_name = os.path.join(subdir, self._log_name(package, version))
        if self.exists(full_name):
            self.remove_file(full_name)


class PackagesDB:

    # keep in sync with piuparts-report.py: emphasize_reason()
    # FIXME: can we reorder this list or remove entries without breaking the counts.txt for the plot?
    _states = [
        "successfully-tested",
        "failed-testing",
        "cannot-be-tested",
        "essential-required",
        "waiting-to-be-tested",
        "waiting-for-dependency-to-be-tested",
        "dependency-failed-testing",
        "dependency-cannot-be-tested",
        "dependency-does-not-exist",
        "circular-dependency",  # obsolete
        "unknown",
        "unknown-preferred-alternative",  # obsolete
        "no-dependency-from-alternatives-exists",  # obsolete
        #"does-not-exist",  # can only happen as query result for a dependency
    ]

    _good_states = [
        "successfully-tested",
        "essential-required",
    ]

    _obsolete_states = [
        "circular-dependency",
        "unknown-preferred-alternative",
        "no-dependency-from-alternatives-exists",
    ]

    _propagate_error_state = {
        "failed-testing": "dependency-failed-testing",
        "cannot-be-tested": "dependency-cannot-be-tested",
        "dependency-failed-testing": "dependency-failed-testing",
        "dependency-cannot-be-tested": "dependency-cannot-be-tested",
        "dependency-does-not-exist": "dependency-cannot-be-tested",
        "does-not-exist": "dependency-does-not-exist",
    }

    _propagate_waiting_state = {
        "waiting-to-be-tested": "waiting-for-dependency-to-be-tested",
        "waiting-for-dependency-to-be-tested": "waiting-for-dependency-to-be-tested",
    }

    def __init__(self, logdb=None, prefix=None):
        self.prefix = prefix
        self._packages_files = []
        self._ready_for_testing = None
        self._logdb = logdb or LogDB()
        self._packages = None
        self._in_state = None
        self._package_state = {}
        self.set_subdirs(ok="pass", fail="fail", evil="untestable",
                         reserved="reserved", morefail=["bugged", "affected"])

    def set_subdirs(self, ok=None, fail=None, evil=None, reserved=None, morefail=None):
        # Prefix all the subdirs with the prefix
        if self.prefix:
            pformat = self.prefix + "/%s"
        else:
            pformat = "%s"
        if ok:
            self._ok = pformat % ok
        if fail:
            self._fail = pformat % fail
        if evil:
            self._evil = pformat % evil
        if reserved:
            self._reserved = pformat % reserved
        if morefail:
            self._morefail = [pformat % s for s in morefail]
        self._all = [self._ok, self._fail, self._evil, self._reserved] + self._morefail

    def create_subdirs(self):
        for sdir in self._all:
            if not os.path.exists(sdir):
                os.makedirs(sdir)

    def read_packages_file(self, input):
        self._packages_files.append(PackagesFile(input))
        self._packages = None

    def _find_all_packages(self):
        if self._packages is None:
            self._packages = {}
            self._virtual_packages = {}
            for pf in self._packages_files:
                for p in pf.values():
                    self._packages[p["Package"]] = p
            for p in self._packages.values():
                for provided in p.provides():
                    if provided != p["Package"]:
                        if provided not in self._virtual_packages:
                            self._virtual_packages[provided] = []
                        self._virtual_packages[provided].append(p["Package"])

    def _get_recursive_dependencies(self, package):
        assert self._packages is not None
        deps = []
        more = package.dependencies()
        while more:
            dep = more[0]
            more = more[1:]
            if dep not in deps:
                deps.append(dep)
                if dep in self._packages:
                    more += self._packages[dep].dependencies()
                elif dep in self._virtual_packages:
                    more += self._packages[self._virtual_packages[dep][0]].dependencies()
        return deps

    def _get_dependency_cycle(self, package_name):
        deps = []
        circular = []
        more = [package_name]
        while more:
            dep = more[0]
            more = more[1:]
            if dep not in deps:
                deps.append(dep)
                if dep in self._packages:
                    dep_pkg = self._packages[dep]
                elif dep in self._virtual_packages:
                    dep_pkg = self._packages[self._virtual_packages[dep][0]]
                else:
                    dep_pkg = None
                if dep_pkg is not None and package_name in self._get_recursive_dependencies(dep_pkg):
                    circular.append(dep)
                    more += dep_pkg.dependencies()
        return circular

    def _compute_package_state(self, package):
        if self._logdb.log_exists(package, [self._ok]):
            return "successfully-tested"
        if self._logdb.log_exists(package, [self._fail] + self._morefail):
            return "failed-testing"
        if self._logdb.log_exists(package, [self._evil]):
            return "cannot-be-tested"
        if not package.is_testable():
            return "essential-required"

        # First attempt to resolve (still-unresolved) multiple alternative depends
        # Definitely sub-optimal, but improvement over blindly selecting first one
        # Select the first alternative in the highest of the following states:
        #   1) "essential-required"
        #   2) "successfully-tested"
        #   3) "waiting-to-be-tested" / "waiting-for-dependency-to-be-tested"
        #   4) "unknown" (retry later)
        # and update the preferred alternative of that dependency.
        # If no alternative is in any of these states we retry later ("unknown")
        # or set "dependency-does-not-exist".
        #
        # Problems:
        #   a) We will test and fail when >=1 "successfully-tested" but another
        #      that failed is selected by apt during test run
        #   b) We may report a status of "waiting-for-dependency-to-be-tested"
        #      instead of "waiting-to-be-tested" depending on the order the
        #      package states get resolved.

        for header in ["Depends", "Pre-Depends"]:
            alt_deps = package.all_dependencies(header)
            for d in range(len(alt_deps)):
                if len(alt_deps[d]) > 1:
                    alt_found = 0
                    prefer_alt_score = -1
                    prefer_alt = None
                    for alternative in alt_deps[d]:
                        altdep_state = self.get_package_state(alternative)
                        if altdep_state != "does-not-exist":
                            alt_found += 1
                            if prefer_alt_score < 3 and altdep_state == "essential-required":
                                prefer_alt = alternative
                                prefer_alt_score = 3
                            elif prefer_alt_score < 2 and altdep_state == "successfully-tested":
                                prefer_alt = alternative
                                prefer_alt_score = 2
                            elif prefer_alt_score < 1 and \
                                 altdep_state in ["waiting-to-be-tested", "waiting-for-dependency-to-be-tested"]:
                                prefer_alt = alternative
                                prefer_alt_score = 1
                            elif prefer_alt_score < 0 and altdep_state == "unknown":
                                prefer_alt = alternative
                                prefer_alt_score = 0
                    if alt_found == 0:
                        return "dependency-does-not-exist"
                    if prefer_alt_score >= 0:
                        package.prefer_alt_depends(header, d, prefer_alt)

        deps = package.dependencies()

        for dep in deps:
            dep_state = self.get_package_state(dep)
            if dep_state in self._propagate_error_state:
                return self._propagate_error_state[dep_state]

        testable = True
        for dep in deps:
            dep_state = self.get_package_state(dep)
            if dep_state not in self._good_states:
                testable = False
                break
        if testable:
            return "waiting-to-be-tested"

        # treat circular-dependencies as testable (for the part of the circle)
        circular_deps = self._get_dependency_cycle(package["Package"])
        if package["Package"] in circular_deps:
            testable = True
            for dep in deps:
                dep_state = self.get_package_state(dep)
                if dep in circular_deps:
                    # allow any non-error dep_state on the cycle for testing
                    # (error states are handled by the error propagation above)
                    pass
                elif dep_state not in self._good_states:
                    # non-circular deps must have passed before testing circular deps
                    testable = False
                    break
            if testable:
                return "waiting-to-be-tested"

        for dep in deps:
            dep_state = self.get_package_state(dep)
            if dep_state in self._propagate_waiting_state:
                return self._propagate_waiting_state[dep_state]

        return "unknown"

    def _compute_package_states(self):
        if self._in_state is not None:
            return

        todo = []

        self._find_all_packages()
        package_names = self._packages.keys()

        self._package_state = {}
        for package_name in package_names:
            self._package_state[package_name] = "unknown"

        self._in_state = {}
        for state in self._states:
            self._in_state[state] = []

        while package_names:
            todo = []
            done = []
            for package_name in package_names:
                package = self._packages[package_name]
                if self._package_state[package_name] == "unknown":
                    state = self._compute_package_state(package)
                    assert state in self._states
                    if state == "unknown":
                        todo.append(package_name)
                    else:
                        self._in_state[state].append(package_name)
                        self._package_state[package_name] = state
                        done.append(package)
            if not done:
                # If we didn't do anything this time, we sure aren't going
                # to do anything the next time either.
                break
            package_names = todo

        self._in_state["unknown"] = todo

        for state in self._states:
            self._in_state[state].sort()

    def get_states(self):
        return self._states

    def get_active_states(self):
        return [x for x in self._states if not x in self._obsolete_states]

    def get_error_states(self):
        return [x for x in self._propagate_error_state.keys() if x in self._states]

    def get_pkg_names_in_state(self, state):
        self._compute_package_states()
        return set(self._in_state[state])

    def has_package(self, name):
        self._find_all_packages()
        return name in self._packages

    def get_package(self, name):
        return self._packages[name]

    def get_providers(self, name):
        if name in self._virtual_packages:
            return self._virtual_packages[name]
        return []

    def get_all_packages(self):
        self._find_all_packages()
        return self._packages

    def get_control_header(self, package_name, header):
        if header == "Source":
          # binary packages build from the source package with the same name
          # don't have a Source header, so let's try:
          try:
            _source = self._packages[package_name][header]
            # for binNMU the Source header in Packages files holds the version 
            # too, so we need to chop it of:
            if " " in _source:
              source, version = _source.split(" ")
            else:
              source = _source
          except:
            source = self._packages[package_name]["Package"]
          return source
        elif header == "Uploaders":
          # not all (source) packages have an Uploaders header
          uploaders = ""
          try:
            uploaders = self._packages[package_name][header]
          except:
            pass
          return uploaders
        else:
          return self._packages[package_name][header]

    def get_package_state(self, package_name, resolve_virtual=True):
        if package_name in self._package_state:
            return self._package_state[package_name]
        if package_name in self._virtual_packages:
            if resolve_virtual:
                provider = self._virtual_packages[package_name][0]
                return self._package_state[provider]
            else:
                return "virtual"
        return "does-not-exist"

    def _find_packages_ready_for_testing(self):
        return self.get_pkg_names_in_state("waiting-to-be-tested")

    def reserve_package(self):
        pset = self._find_packages_ready_for_testing()
        while (len(pset)):
            p = self.get_package(pset.pop())
            if self._logdb.create(self._reserved, p["Package"], p["Version"], ""):
                return p
        return None

    def _check_for_acceptability_as_filename(self, str):
        if "/" in str:
            raise Exception("'/' in (partial) filename: %s" % str)

    def unreserve_package(self, package, version):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        self._logdb.remove(self._reserved, package, version)

    def pass_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._ok, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

    def fail_package(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._fail, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

    def make_package_untestable(self, package, version, log):
        self._check_for_acceptability_as_filename(package)
        self._check_for_acceptability_as_filename(version)
        if self._logdb.create(self._evil, package, version, log):
            self._logdb.remove(self._reserved, package, version)
        else:
            raise Exception("Log file exists already: %s (%s)" %
                                (package, version))

    def calc_rrdep_counts(self):
        """Calculate recursive reverse dependency counts for Packages"""

        self._find_all_packages()       # populate _packages
        self._compute_package_states()  # populate _package_state
        error_states = self.get_error_states()

        # create a reverse dependency dictionary.
        # entries consist of a one-level list of reverse dependency package names,
        # by package name
        rdeps = {}
        for pkg_name in self._packages.keys():
            # use the Packages dependencies() method for a conservative count
            for dep in self._packages[pkg_name].dependencies():
                if dep in rdeps:
                    rdeps[dep].append( pkg_name )
                else:
                    rdeps[dep] = [pkg_name]

        def recurse_rdeps( pkg_name, rdeps, rrdep_dict ):
            """ Recurse through the reverse dep arrays to determine the recursive
                dependency count for a package. rrdep_dict.keys() contains the
                accumulation of rdeps encountered"""

            # are there any rdeps for this package?
            if pkg_name in rdeps:
                for rdep in rdeps[pkg_name]:
                    # break circular dependency loops
                    if not rdep in rrdep_dict:
                        rrdep_dict[rdep] = 1
                        rrdep_dict = recurse_rdeps( rdep, rdeps, rrdep_dict )

            return rrdep_dict

        # calculate all of the rrdeps and block counts
        for pkg_name in self._packages.keys():
            rrdep_list = recurse_rdeps( pkg_name, rdeps, {} ).keys()
            self._packages[pkg_name].set_rrdep_count( len(rrdep_list) )

            if self._package_state[pkg_name] in error_states:
                block_list = [x for x in rrdep_list
                              if self._package_state[x] in error_states]
            else:
                block_list = []
            self._packages[pkg_name].set_block_count( len(block_list) )


# vi:set et ts=4 sw=4 :
