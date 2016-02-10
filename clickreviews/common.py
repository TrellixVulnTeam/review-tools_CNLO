'''common.py: common classes and functions'''
#
# Copyright (C) 2013-2016 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
import atexit
import codecs
import inspect
import json
import logging
import magic
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types


DEBUGGING = False
UNPACK_DIR = None
RAW_UNPACK_DIR = None


def cleanup_unpack():
    global UNPACK_DIR
    if UNPACK_DIR is not None and os.path.isdir(UNPACK_DIR):
        recursive_rm(UNPACK_DIR)
        UNPACK_DIR = None
    global RAW_UNPACK_DIR
    if RAW_UNPACK_DIR is not None and os.path.isdir(RAW_UNPACK_DIR):
        recursive_rm(RAW_UNPACK_DIR)
        RAW_UNPACK_DIR = None
atexit.register(cleanup_unpack)


#
# Utility classes
#
class ReviewException(Exception):
    '''This class represents Review exceptions'''
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


class Review(object):
    '''Common review class'''
    magic_binary_file_descriptions = [
        'application/x-executable; charset=binary',
        'application/x-sharedlib; charset=binary',
        'application/x-object; charset=binary',
        'application/octet-stream; charset=binary'
    ]

    def __init__(self, fn, review_type, overrides=None):
        self.pkg_filename = fn
        self._check_package_exists()

        self.review_type = review_type
        # TODO: rename as pkg_report
        self.click_report = dict()

        self.result_types = ['info', 'warn', 'error']
        for r in self.result_types:
            self.click_report[r] = dict()

        self.click_report_output = "json"

        global UNPACK_DIR
        if UNPACK_DIR is None:
            UNPACK_DIR = unpack_pkg(fn)
        self.unpack_dir = UNPACK_DIR

        global RAW_UNPACK_DIR
        if RAW_UNPACK_DIR is None:
            RAW_UNPACK_DIR = raw_unpack_pkg(fn)
        self.raw_unpack_dir = RAW_UNPACK_DIR

        self.is_click = False
        self.is_snap1 = False
        self.is_snap2 = False
        self.pkgfmt = {"type": "", "version": ""}

        (self.pkgfmt["type"], pkgver) = detect_package(fn, self.unpack_dir)

        if self._pkgfmt_type() == "snap":
            if pkgver < 2:
                self.is_snap1 = True
                self.pkgfmt["version"] = "15.04"
            else:
                self.is_snap2 = True
                self.pkgfmt["version"] = "16.04"
        elif self._pkgfmt_type() == "click":
            self.pkgfmt["version"] = "0.4"
            self.is_click = True
        else:
            error("Unknown package type: '%s'" % self._pkgfmt_type())

        # Get a list of all unpacked files
        self.pkg_files = []
        self._list_all_files()

        # Setup what is needed to get a list of all unpacked compiled binaries
        self.mime = magic.open(magic.MAGIC_MIME)
        self.mime.load()
        self.pkg_bin_files = []
        # Don't run this here since only cr_lint.py and cr_functional.py need
        # it now
        # self._list_all_compiled_binaries()

        self.overrides = overrides if overrides is not None else {}

    def _check_innerpath_executable(self, fn):
        '''Check that the provided path exists and is executable'''
        return os.access(fn, os.X_OK)

    def _extract_statinfo(self, fn):
        '''Extract statinfo from file'''
        try:
            st = os.stat(fn)
        except Exception:
            return None
        return st

    def _path_join(self, dirname, rest):
        return os.path.join(dirname, rest)

    def _get_sha512sum(self, fn):
        '''Get sha512sum of file'''
        (rc, out) = cmd(['sha512sum', fn])
        if rc != 0:
            return None
        return out.split()[0]

    def _pkgfmt_type(self):
        '''Return the package format type'''
        if "type" not in self.pkgfmt:
            return ""
        return self.pkgfmt["type"]

    def _pkgfmt_version(self):
        '''Return the package format version'''
        if "version" not in self.pkgfmt:
            return ""
        return self.pkgfmt["version"]

    def _check_package_exists(self):
        '''Check that the provided package exists'''
        if not os.path.exists(self.pkg_filename):
            error("Could not find '%s'" % self.pkg_filename)

    def _list_all_files(self):
        '''List all files included in this click package.'''
        for root, dirnames, filenames in os.walk(self.unpack_dir):
            for f in filenames:
                self.pkg_files.append(os.path.join(root, f))

    def _check_if_message_catalog(self, fn):
        '''Check if file is a message catalog (.mo file).'''
        if fn.endswith('.mo'):
            return True
        return False

    def _list_all_compiled_binaries(self):
        '''List all compiled binaries in this click package.'''
        for i in self.pkg_files:
            res = self.mime.file(i)
            if res in self.magic_binary_file_descriptions and \
               not self._check_if_message_catalog(i):
                self.pkg_bin_files.append(i)

    def _get_check_name(self, name, app='', extra=''):
        name = ':'.join([self.review_type, name])
        if app:
            name += ':' + app
        if extra:
            name += ':' + extra
        return name

    def _verify_pkgversion(self, v):
        '''Verify package name'''
        if not isinstance(v, (str, int, float)):
            return False
        re_valid_version = re.compile(r'^((\d+):)?'              # epoch
                                      '([A-Za-z0-9.+:~-]+?)'     # upstream
                                      '(-([A-Za-z0-9+.~]+))?$')  # debian
        if re_valid_version.match(str(v)):
            return True
        return False

    # click_report[<result_type>][<review_name>] = <result>
    #   result_type: info, warn, error
    #   review_name: name of the check (prefixed with self.review_type)
    #   result: contents of the review
    def _add_result(self, result_type, review_name, result, link=None,
                    manual_review=False):
        '''Add result to report'''
        if result_type not in self.result_types:
            error("Invalid result type '%s'" % result_type)

        if review_name not in self.click_report[result_type]:
            # log info about check so it can be collected into the
            # check-names.list file
            # format should be
            # CHECK|<review_type:check_name>|<link>
            msg = 'CHECK|{}|{}'
            name = ':'.join(review_name.split(':')[:2])
            link_text = link if link is not None else ""
            logging.debug(msg.format(name, link_text))
            self.click_report[result_type][review_name] = dict()

        self.click_report[result_type][review_name].update({
            'text': result,
            'manual_review': manual_review,
        })
        if link is not None:
            self.click_report[result_type][review_name]["link"] = link

    def do_report(self):
        '''Print report'''
        if self.click_report_output == "console":
            # TODO: format better
            import pprint
            pprint.pprint(self.click_report)
        elif self.click_report_output == "json":
            import json
            msg(json.dumps(self.click_report,
                           sort_keys=True,
                           indent=2,
                           separators=(',', ': ')))

        rc = 0
        if len(self.click_report['error']):
            rc = 2
        elif len(self.click_report['warn']):
            rc = 1
        return rc

    def do_checks(self):
        '''Run all methods that start with check_'''
        methodList = [name for name, member in
                      inspect.getmembers(self, inspect.ismethod)
                      if isinstance(member, types.MethodType)]
        for methodname in methodList:
            if not methodname.startswith("check_"):
                continue
            func = getattr(self, methodname)
            func()

    def set_review_type(self, name):
        '''Set review name'''
        self.review_type = name


#
# Utility functions
#

def error(out, exit_code=1, do_exit=True):
    '''Print error message and exit'''
    try:
        print("ERROR: %s" % (out), file=sys.stderr)
    except IOError:
        pass

    if do_exit:
        sys.exit(exit_code)


def warn(out):
    '''Print warning message'''
    try:
        print("WARN: %s" % (out), file=sys.stderr)
    except IOError:
        pass


def msg(out, output=sys.stdout):
    '''Print message'''
    try:
        print("%s" % (out), file=output)
    except IOError:
        pass


def debug(out):
    '''Print debug message'''
    global DEBUGGING
    if DEBUGGING:
        try:
            print("DEBUG: %s" % (out), file=sys.stderr)
        except IOError:
            pass


def cmd(command):
    '''Try to execute the given command.'''
    debug(command)
    try:
        sp = subprocess.Popen(command, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT)
    except OSError as ex:
        return [127, str(ex)]

    if sys.version_info[0] >= 3:
        out = sp.communicate()[0].decode('ascii', 'ignore')
    else:
        out = sp.communicate()[0]

    return [sp.returncode, out]


def cmd_pipe(command1, command2):
    '''Try to pipe command1 into command2.'''
    try:
        sp1 = subprocess.Popen(command1, stdout=subprocess.PIPE)
        sp2 = subprocess.Popen(command2, stdin=sp1.stdout)
    except OSError as ex:
        return [127, str(ex)]

    if sys.version_info[0] >= 3:
        out = sp2.communicate()[0].decode('ascii', 'ignore')
    else:
        out = sp2.communicate()[0]

    return [sp2.returncode, out]


def _unpack_cmd(cmd_args, d, dest):
    '''Low level unpack helper'''
    curdir = os.getcwd()
    os.chdir(d)

    (rc, out) = cmd(cmd_args)
    os.chdir(curdir)

    if rc != 0:
        if os.path.isdir(d):
            recursive_rm(d)
        error("unpacking failed with '%d':\n%s" % (rc, out))

    if dest is None:
        dest = d
    else:
        shutil.move(d, dest)

    return dest


def _unpack_snap_squashfs(snap_pkg, dest):
    '''Unpack a squashfs based snap package to dest'''
    d = tempfile.mkdtemp(prefix='clickreview-')
    return _unpack_cmd(['unsquashfs', '-f', '-d', d,
                        os.path.abspath(snap_pkg)], d, dest)


def _unpack_click_deb(pkg, dest):
    d = tempfile.mkdtemp(prefix='clickreview-')
    return _unpack_cmd(['dpkg-deb', '-R',
                        os.path.abspath(pkg), d], d, dest)


def unpack_pkg(fn, dest=None):
    '''Unpack package'''
    if not os.path.isfile(fn):
        error("Could not find '%s'" % fn)
    pkg = fn
    if not pkg.startswith('/'):
        pkg = os.path.abspath(pkg)

    if dest is not None and os.path.exists(dest):
        error("'%s' exists. Aborting." % dest)

    # check if its a squashfs based snap
    if is_squashfs(pkg):
        return _unpack_snap_squashfs(fn, dest)

    return _unpack_click_deb(fn, dest)


def is_squashfs(filename):
    '''Return true if the given filename as a squashfs header'''
    with open(filename, 'rb') as f:
        header = f.read(10)
    return header.startswith(b"hsqs")


def raw_unpack_pkg(fn, dest=None):
    '''Unpack raw package'''
    if not os.path.isfile(fn):
        error("Could not find '%s'" % fn)
    pkg = fn
    if not pkg.startswith('/'):
        pkg = os.path.abspath(pkg)
    # nothing to do for squashfs images
    if is_squashfs(pkg):
        return ""

    if dest is not None and os.path.exists(dest):
        error("'%s' exists. Aborting." % dest)

    d = tempfile.mkdtemp(prefix='review-')

    curdir = os.getcwd()
    os.chdir(d)
    (rc, out) = cmd(['ar', 'x', pkg])
    os.chdir(curdir)

    if rc != 0:
        if os.path.isdir(d):
            recursive_rm(d)
        error("'ar x' failed with '%d':\n%s" % (rc, out))

    if dest is None:
        dest = d
    else:
        shutil.move(d, dest)

    return dest


def open_file_read(path):
    '''Open specified file read-only'''
    try:
        orig = codecs.open(path, 'r', "UTF-8")
    except Exception:
        raise

    return orig


def recursive_rm(dirPath, contents_only=False):
    '''recursively remove directory'''
    names = os.listdir(dirPath)
    for name in names:
        path = os.path.join(dirPath, name)
        if os.path.islink(path) or not os.path.isdir(path):
            os.unlink(path)
        else:
            recursive_rm(path)
    if contents_only is False:
        os.rmdir(dirPath)


def run_check(cls):
    if len(sys.argv) < 2:
        error("Must give path to package")

    # extract args
    fn = sys.argv[1]
    if len(sys.argv) > 2:
        overrides = json.loads(sys.argv[2])
    else:
        overrides = None

    review = cls(fn, overrides=overrides)
    review.do_checks()
    rc = review.do_report()
    sys.exit(rc)


def detect_package(fn, dir=None):
    '''Detect what type of package this is'''
    pkgtype = None
    pkgver = None

    if not os.path.isfile(fn):
        error("Could not find '%s'" % fn)

    if dir is None:
        unpack_dir = unpack_pkg(fn)
    else:
        unpack_dir = dir

    if not os.path.isdir(unpack_dir):
        error("Could not find '%s'" % unpack_dir)

    pkg = fn
    if not pkg.startswith('/'):
        pkg = os.path.abspath(pkg)

    # check if its a squashfs based snap
    if is_squashfs(pkg):
        # 16.04+ squashfs snaps
        pkgtype = "snap"
        pkgver = 2
    elif os.path.exists(os.path.join(unpack_dir, "meta/package.yaml")):
        # 15.04 ar-based snaps
        pkgtype = "snap"
        pkgver = 1
    else:
        pkgtype = "click"
        pkgver = 1

    if dir is None and os.path.isdir(unpack_dir):
        recursive_rm(unpack_dir)

    return (pkgtype, pkgver)
