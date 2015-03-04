'''test_cr_systemd.py: tests for the cr_systemd module'''
#
# Copyright (C) 2014 Canonical Ltd.
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

from clickreviews.cr_systemd import ClickReviewSystemd
import clickreviews.cr_tests as cr_tests


class TestClickReviewSystemd(cr_tests.TestClickReview):
    """Tests for the lint review tool."""
    def setUp(self):
        # Monkey patch various file access classes. stop() is handled with
        # addCleanup in super()
        cr_tests.mock_patch()
        super()

    def test_check_required(self):
        '''Test check_required() - has start and description'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="description",
                              value="something")
        c = ClickReviewSystemd(self.test_name)
        c.check_required()
        r = c.click_report
        expected_counts = {'info': 2, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_required_empty_value(self):
        '''Test check_required() - empty start'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="")
        self.set_test_systemd(self.default_appname,
                              key="description",
                              value="something")
        c = ClickReviewSystemd(self.test_name)
        c.check_required()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)

    def test_check_required_bad_value(self):
        '''Test check_required() - bad start'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value=[])
        self.set_test_systemd(self.default_appname,
                              key="description",
                              value="something")
        c = ClickReviewSystemd(self.test_name)
        c.check_required()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)

    def test_check_required_multiple(self):
        '''Test check_required() - multiple'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="description",
                              value="something")
        c = ClickReviewSystemd(self.test_name)
        c.check_required()
        r = c.click_report
        expected_counts = {'info': -1, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_required_multiple(self):
        '''Test check_required() - multiple with nonexistent'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="description",
                              value="something")
        self.set_test_systemd(self.default_appname,
                              key="nonexistent",
                              value="foo")
        c = ClickReviewSystemd(self.test_name)
        c.check_required()
        r = c.click_report
        expected_counts = {'info': 2, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_optional_none(self):
        '''Test check_optional() - start only'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': 3, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_optional_stop_empty(self):
        '''Test check_optional() - with empty stop'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value="")
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)

    def test_check_optional_stop_bad(self):
        '''Test check_optional() - with bad stop'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value=[])
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)

    def test_check_optional_stop_nonexistent(self):
        '''Test check_optional() - with stop plus nonexistent'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value="bin/bar")
        self.set_test_systemd(self.default_appname,
                              key="nonexistent",
                              value="foo")
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': 3, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_optional_stop_without_start(self):
        '''Test check_optional() - with stop, no start'''
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value="/bin/bar")
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': 3, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_optional_stop_without_start2(self):
        '''Test check_optional() - with stop, nonexistent, no start'''
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value="/bin/bar")
        self.set_test_systemd(self.default_appname,
                              key="nonexistent",
                              value="example.com")
        c = ClickReviewSystemd(self.test_name)
        c.check_optional()
        r = c.click_report
        expected_counts = {'info': 3, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_unknown(self):
        '''Test check_unknown()'''
        self.set_test_systemd(self.default_appname,
                              key="nonexistent",
                              value="foo")
        c = ClickReviewSystemd(self.test_name)
        c.check_unknown()
        r = c.click_report
        expected_counts = {'info': 0, 'warn': 1, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_unknown_multiple(self):
        '''Test check_unknown() - multiple with nonexistent'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        self.set_test_systemd(self.default_appname,
                              key="stop",
                              value="bin/bar")
        self.set_test_systemd(self.default_appname,
                              key="nonexistent",
                              value="foo")
        c = ClickReviewSystemd(self.test_name)
        c.check_unknown()
        r = c.click_report
        expected_counts = {'info': 0, 'warn': 1, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_peer_hooks(self):
        '''Test check_peer_hooks()'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        c = ClickReviewSystemd(self.test_name)

        # create a new hooks database for our peer hooks tests
        tmp = dict()

        # add our hook
        tmp["snappy-systemd"] = "meta/foo.snappy-systemd"

        # add required hooks
        tmp["apparmor"] = "meta/foo.apparmor"

        # update the manifest and test_manifest
        c.manifest["hooks"][self.default_appname] = tmp
        self._update_test_manifest()

        # do the test
        c.check_peer_hooks()
        r = c.click_report
        # We should end up with 2 info
        expected_counts = {'info': 2, 'warn': 0, 'error': 0}
        self.check_results(r, expected_counts)

    def test_check_peer_hooks_disallowed(self):
        '''Test check_peer_hooks() - disallowed'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        c = ClickReviewSystemd(self.test_name)

        # create a new hooks database for our peer hooks tests
        tmp = dict()

        # add our hook
        tmp["snappy-systemd"] = "meta/foo.snappy-systemd"

        # add required hooks
        tmp["apparmor"] = "meta/foo.apparmor"

        # add something not allowed
        tmp["bin-path"] = "bin/bar"

        c.manifest["hooks"][self.default_appname] = tmp
        self._update_test_manifest()

        # do the test
        c.check_peer_hooks()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)

    def test_check_peer_hooks_disallowed2(self):
        '''Test check_peer_hooks() - disallowed (nonexistent)'''
        self.set_test_systemd(self.default_appname,
                              key="start",
                              value="/bin/foo")
        c = ClickReviewSystemd(self.test_name)

        # create a new hooks database for our peer hooks tests
        tmp = dict()

        # add our hook
        tmp["snappy-systemd"] = "meta/foo.snappy-systemd"

        # add required hooks
        tmp["apparmor"] = "meta/foo.apparmor"

        # add something not allowed
        tmp["nonexistent"] = "nonexistent-hook"

        c.manifest["hooks"][self.default_appname] = tmp
        self._update_test_manifest()

        # do the test
        c.check_peer_hooks()
        r = c.click_report
        expected_counts = {'info': None, 'warn': 0, 'error': 1}
        self.check_results(r, expected_counts)