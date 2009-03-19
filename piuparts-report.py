#!/usr/bin/python
#
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
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA


"""Create HTML reports of piuparts log files

Lars Wirzenius <liw@iki.fi>
"""


import os
import sys
import time
import logging
import ConfigParser
import urllib
import shutil
import string

import piupartslib


CONFIG_FILE = "piuparts-report.conf"


HTML_HEADER = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN">
 <html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <title>piuparts.debian.org / piuparts.cs.helsinki.fi</title>
  <link type="text/css" rel="stylesheet" href="/style.css">
  <link rel="shortcut icon" href="/favicon.ico">
 </head>

 <body>
 <div id="header">
   <h1 class="header">
    <a href="http://www.debian.org/">
     <img src="http://piuparts.debian.org/images/openlogo-nd-50.png" border="0" hspace="0" vspace="0" alt=""></a>
    <a href="http://www.debian.org/">
     <img src="http://piuparts.debian.org/images/debian.png" border="0" hspace="0" vspace="0" alt="Debian Project"></a>
    Quality Assurance
   </h1>
  <table class="reddy" width="97%">
   <tr>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-upperleft.png" align="left" border="0" hspace="0" vspace="0"
      alt="" width="15" height="16"></td>
    <td rowspan="2" class="reddy">Policy is your friend. Trust the Policy. Love the Policy. Obey the Policy.</td>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-upperright.png" align="right" border="0" hspace="0" vspace="0"
     alt="" width="16" height="16"></td>
   </tr>
   <tr>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-lowerleft.png" align="left" border="0" hspace="0" vspace="0"
      alt="" width="16" height="16"></td>
    <td class="reddy">
     <img src="http://piuparts.debian.org/images/red-lowerright.png" align="right" border="0" hspace="0" vspace="0"
      alt="" width="15" height="16"></td>
   </tr>
  </table>
 </div>
 <hr>
<div id="main">
<table class="containertable">
 <tr class="containerrow" valign="top">
  <td class="containercell">
   <table class="lefttable">
    <tr class="titlerow">
     <td class="titlecell">
      General information
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/">Overview</a>
     </td>
    </tr>
      <td class="contentcell">
      <a href="http://wiki.debian.org/piuparts">About</a>
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="http://wiki.debian.org/piuparts/FAQ">FAQ</a> 
     </td>
     </tr>     
    <tr class="titlerow">
     <td class="titlecell">
      Available reports
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/sid/">sid</a> 
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      <a href="/squeeze/">squeeze</a> 
     </td>
    </tr>
    <tr class="titlerow">
     <td class="titlecell">
      Last update
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell">
      $time
     </td>
    </tr>
   </table>
  </td>
  <td class="containercell">
"""


HTML_FOOTER = """
  </td>
 </tr>
</table> 
</div>
 <hr>
 <div id="footer">
  <div>
   piuparts was written by <a href="mailto:liw@iki.fi">Lars Wirzenius</a> and is now maintained by 
   <a href="mailto:holger@debian.org">Holger Levsen</a>,  
   <a href="mailto:luk@debian.org">Luk Claes</a> and others. GPL2 licenced.
   <br>
  </div>
  <div>
   <a href="http://validator.w3.org/check?uri=referer">
    <img border="0" src="/images/valid-html401.png" alt="Valid HTML 4.01!" height="31" width="88">
   </a>
   <a href="http://jigsaw.w3.org/css-validator/check/referer">
    <img border="0" src="/images/vcss.png" alt="Valid CSS!"  height="31" width="88">
   </a>
  </div>
 </div>
</body>
</html>
"""


LOG_LIST_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      $title
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      $preface
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      The list has $count packages, with $versioncount total versions.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <ul>
       $loglist
      </ul>
     </td>
    </tr>
   </table>
"""


STATE_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      Packages in state "$state"
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      <ul>
       $list
      </ul>
     </td>
    </tr>
   </table>
"""


SECTION_STATS_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      Statistics of packages per section
     </td>
    </tr>
    $tablerows
    <tr class="titlerow">
     <td class="titlecell" colspan="3">
      URL to packages file(s)
     </td>
    </tr>
     <tr class="normalrow">
     <td class="contentcell2" colspan="3">
      <code>$packagesurl</code>
     </td>
    </tr>
   </table>
"""


INDEX_BODY_TEMPLATE = """
   <table class="righttable">
    <tr class="titlerow">
     <td class="titlecell">
      piuparts.debian.org / piuparts.cs.helsinki.fi
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      piuparts is a tool for testing that .deb packages can be installed, upgraded, and removed without problems. The
      name, a variant of something suggested by Tollef Fog Heen, is short for "<em>p</em>ackage <em>i</em>nstallation, 
      <em>up</em>grading <em>a</em>nd <em>r</em>emoval <em>t</em>esting <em>s</em>uite". 
      <br>
      It does this by  creating a minimal Debian installation in a chroot, and installing,
      upgrading, and removing packages in that environment, and comparing the state of the directory tree before and after. 
      piuparts reports any files that have been added, removed, or modified during this process.
      <br>
      piuparts is meant as a quality assurance tool for people who create .deb packages to test them before they upload 
      them to the Debian package archive.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      To make sure piuparts is run on all packages, piuparts.debian.org was set up.
      <br>
      piuparts.debian.org is a service running on <a href="http://db.debian.org/machines.cgi?host=piatti">piatti.debian.org</a>,
      generously donated by <a href="http://hp.com/go/debian/" target="_blank">HP</a> and hosted at piuparts.cs.helsinki.fi by 
      the University of Helsinki, at the <a href="http://cs.helsinki.fi/index.en.html" target="_blank">Department of Computer Science</a> in Finland.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      This setup is currently still being polished. Better reports and statistics as well as PTS integration is
      planned. Join #debian-qa if you want to help.
     </td>
    </tr>
    <tr class="normalrow">
     <td class="contentcell2">
      These pages are updated daily.
     </td>
    </tr>
    </table>
"""


title_by_dir = {
    "pass": "PASSED piuparts logs",
    "fail": "Failed UNREPORTED piuparts logs",
    "bugged": "Failed REPORTED piuparts logs",
    "fixed": "Failed and FIXED packages",
    "reserved": "RESERVED packages",
    "untestable": "UNTESTABLE packages",
}


desc_by_dir = {
    "pass": "Log files for packages that have PASSED testing.",
    "fail": "Log files for packages that have FAILED testing. " +
            "Bugs have not yet been reported.",
    "bugged": "Log files for packages that have FAILED testing. " +
              "Bugs have been reported, but not yet fixed.",
    "fixed": "Log files for packages that have FAILED testing, but for " +
             "which a fix has been made.",
    "reserved": "Packages that are RESERVED for testing on a node in a " +
                "distributed piuparts network.",
    "untestable": "Log files for packages that have are UNTESTABLE with " +
                  "piuparts at the current time.",
}

state_by_dir = {
    "pass": "successfully-tested",
    "fail": "failed-testing",
    "bugged": "failed-testing",
    "fixed": "fix-not-yet-tested",
    "reserved": "waiting-to-be-tested",
    "untestable": "dependency-cannot-be-tested",
}


class Config(piupartslib.conf.Config):

    def __init__(self, section="report"):
        self.section = section
        piupartslib.conf.Config.__init__(self, section,
            {
                "sections": "report",
                "output-directory": "html",
                "index-page": "index.html",
                "packages-url": None,
                "master-directory": ".",
            },
            ["output-directory", "packages-url", "master-directory"])


def setup_logging(log_level, log_file_name):
    logger = logging.getLogger()
    logger.setLevel(log_level)

    formatter = logging.Formatter(fmt="%(asctime)s %(message)s",
                                  datefmt="%H:%M")

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    if log_file_name:
        handler = logging.FileHandler(log_file_name)
        logger.addHandler(handler)


def html_protect(str):
    str = "&amp;".join(str.split("&"))
    str = "&lt;".join(str.split("<"))
    str = "&gt;".join(str.split(">"))
    str = "&#34;".join(str.split('"'))
    str = "&#39;".join(str.split("'"))
    return str


def emphasize_reason(str):
    if str == "unknown-package" or str == "failed-testing":
      str = "<em" + str + "</em>"
    return str


def write_log_list_page(filename, title, preface, logs):
    packages = {}
    for pathname, package, version in logs:
        packages[package] = packages.get(package, []) + [(pathname, version)]

    names = packages.keys()
    names.sort()
    lines = []
    version_count = 0
    for package in names:
        versions = []
        for pathname, version in packages[package]:
            version_count += 1
            versions.append("<a href='%s'>%s</a>" % 
                            (html_protect(pathname), 
                             html_protect(version)))
        line = "<li>%s %s</li>\n" % (html_protect(package), 
                                     ", ".join(versions))
        lines.append(line)

    htmlpage = string.Template(HTML_HEADER + LOG_LIST_BODY_TEMPLATE + HTML_FOOTER)
    f = file(filename, "w")
    f.write(htmlpage.safe_substitute( {
                "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                "title": html_protect(title),
                "preface": preface,
                "count": len(packages),
                "versioncount": version_count,
                "loglist": "".join(lines)
            }))
    f.close()


def print_by_dir(output_directory, logs_by_dir):
    for dir in logs_by_dir:
        list = []
        for basename in logs_by_dir[dir]:
            assert basename.endswith(".log")
            assert "_" in basename
            package, version = basename[:-len(".log")].split("_")
            list.append((os.path.join(dir, basename), package, version))
        write_log_list_page(os.path.join(output_directory, dir + ".html"),
                            title_by_dir[dir], 
                            desc_by_dir[dir], list)


def find_log_files(dir):
    return [name for name in os.listdir(dir) if name.endswith(".log")]


def update_file(source, target):
    if os.path.exists(target):
        aa = os.stat(source)
        bb = os.stat(target)
        if aa.st_size == bb.st_size and aa.st_mtime < bb.st_mtime:
            return
    shutil.copyfile(source, target)


def copy_logs(logs_by_dir, output_dir):
    for dir in logs_by_dir:
        fulldir = os.path.join(output_dir, dir)
        if not os.path.exists(fulldir):
            os.makedirs(fulldir)
        for basename in logs_by_dir[dir]:
            source = os.path.join(dir, basename)
            target = os.path.join(fulldir, basename)
            update_file(source, target)


def remove_old_logs(logs_by_dir, output_dir):
    for dir in logs_by_dir:
        fulldir = os.path.join(output_dir, dir)
        if os.path.exists(fulldir):
            for basename in os.listdir(fulldir):
                if basename not in logs_by_dir[dir]:
                    os.remove(os.path.join(fulldir, basename))


def write_file(filename, contents):
    f = file(filename, "w")
    f.write(contents)
    f.close()


class Section:

    def __init__(self, section):
        self._config = Config(section=section)
        self._config.read(CONFIG_FILE)
        self._output_directory = os.path.abspath(os.path.join(self._config["output-directory"], self._config.section))
        if not os.path.exists(self._output_directory):
            os.mkdir(self._output_directory)
        self._master_directory = os.path.abspath(os.path.join(self._config["master-directory"], self._config.section))

    def output(self):
        logging.debug("-------------------------------------------")
        logging.debug("Running section " + self._config.section)
        if os.path.exists(self._master_directory):

            oldcwd = os.getcwd()
            os.chdir(self._master_directory)

            logging.debug("Finding log files")
            dirs = ["pass", "fail", "bugged", "fixed", "reserved", "untestable"]
            logs_by_dir = {}
            for dir in dirs:
                logs_by_dir[dir] = find_log_files(dir)

            logging.debug("Copying log files")
            copy_logs(logs_by_dir, self._output_directory)

            logging.debug("Removing old log files")
            remove_old_logs(logs_by_dir, self._output_directory)

            logging.debug("Writing per-dir HTML pages")
            print_by_dir(self._output_directory, logs_by_dir)
    
            logging.debug("Loading and parsing Packages file")
            if 1:
                logging.info("Fetching %s" % self._config["packages-url"])
                packages_file = piupartslib.open_packages_url(self._config["packages-url"])
            else:
                packages_file = file("Packages")
            st = piupartslib.packagesdb.PackagesDB()
            st.read_packages_file(packages_file)
            packages_file.close()

            logging.debug("Writing section statistics page")    
            tablerows = ""
            for state in st.get_states():
                dir_link = ""
                for dir in dirs:
                  if state_by_dir[dir] == state:
                    dir_link += "<a href='%s.html'>%s</a> logs<br>" % (dir, html_protect(dir))
                tablerows += ("<tr class=\"normalrow\"><td class=\"contentcell2\"><a href='state-%s.html'>%s</a></td>" +
                              "<td class=\"contentcell2\">%d</td><td class=\"contentcell2\">%s</td></tr>\n") % \
                              (html_protect(state), html_protect(state),
                              len(st.get_packages_in_state(state)),
                              dir_link)
            tablerows += "<tr class=\"normalrow\"> <td class=\"labelcell\">Total</td> <td class=\"labelcell\" colspan=\"2\">%d</td></tr>\n" % \
                         st.get_total_packages()
            htmlpage = string.Template(HTML_HEADER + SECTION_STATS_BODY_TEMPLATE + HTML_FOOTER)
            write_file(os.path.join(self._output_directory, "index.html"), htmlpage.safe_substitute( {
                "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                "tablerows": tablerows,
                "packagesurl": html_protect(self._config["packages-url"]), 
               }))

            for state in st.get_states():
                logging.debug("Writing page for %s" % state)
                list = "<ul>\n"
                for package in st.get_packages_in_state(state):
                    list += "<li>%s (%s)" % (html_protect(package["Package"]),
                                             html_protect(package["Maintainer"]))
                    if package.dependencies():
                        list += "\n<ul>\n"
                        for dep in package.dependencies():
                            list += "<li>dependency %s is %s</li>\n" % \
                                     (html_protect(dep), 
                                      emphasize_reason(html_protect(st.state_by_name(dep))))
                        list += "</ul>\n"
                    list += "</li>\n"
                list += "</ul>\n"
                htmlpage = string.Template(HTML_HEADER + STATE_BODY_TEMPLATE + HTML_FOOTER)
                write_file(os.path.join(self._output_directory, "state-%s.html" % state), htmlpage.safe_substitute( {
                                            "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                                            "state": html_protect(state),
                                            "list": list
                                           }))

            os.chdir(oldcwd)


def main():
    setup_logging(logging.DEBUG, None)

    # For supporting multiple architectures and suites, we take a command-line
    # argument referring to a section in the reports configuration file.  For
    # backwards compatibility, if no argument is given, the "report" section is
    # assumed.
    section_names = []
    if len(sys.argv) > 1:
        section = sys.argv[1]
    else:
        report_config = Config(section="report")
        report_config.read(CONFIG_FILE)
        section_names = report_config["sections"].split()

    sections = []
    for section_name in section_names:
        section = Section(section_name)
        section.output()
        sections.append(section)

    logging.debug("Writing index page")
    htmlpage = string.Template(HTML_HEADER + INDEX_BODY_TEMPLATE + HTML_FOOTER)
    write_file(report_config["index-page"], htmlpage.safe_substitute( {
                                 "time": time.strftime("%Y-%m-%d %H:%M %Z"),
                              }))

if __name__ == "__main__":
    main()
