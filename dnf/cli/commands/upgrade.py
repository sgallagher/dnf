# upgrade.py
# Upgrade CLI command.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import logging

import dnf.exceptions
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

logger = logging.getLogger('dnf')


class UpgradeCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    update command.
    """
    aliases = ('upgrade', 'update', 'upgrade-to', 'update-to', 'up')
    summary = _('upgrade a package or packages on your system')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', help=_('Package to upgrade'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        """Verify that conditions are met so that this command can run.

        These include that there are enabled repositories with gpg
        keys, and that this command is being run by the root user.
        """
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        if not self.opts.filenames:
            commands._checkEnabledRepo(self.base)
        self.upgrade_minimal = None
        self.all_security = None

    def run(self):
        self.cli._populate_update_security_filter(self.opts,
                                                  minimal=self.upgrade_minimal,
                                                  all=self.all_security)

        if self.opts.filenames or self.opts.pkg_specs or self.opts.grp_specs:
            if any([fn() for fn in [self._update_modules,
                                    self._update_files,
                                    self._update_packages,
                                    self._update_groups]]):
                return
        else:
            self._update_modules_all()
            self.base.upgrade_all()
            return

        raise dnf.exceptions.Error(_('No packages marked for upgrade.'))

    def _update_modules_all(self):
        self.cli.demands.transaction_display = self.base.repo_module_dict.transaction_callback
        self.base.repo_module_dict.upgrade(list(self.base.repo_module_dict.keys()))

    def _update_modules(self):
        self.cli.demands.transaction_display = self.base.repo_module_dict.transaction_callback

        modules = self.get_modules_from_spec(self.opts.pkg_specs)
        modules.extend(self.get_modules_from_spec(self.opts.grp_specs))

        self.base.repo_module_dict.upgrade(modules)
        return len(modules) != 0

    def get_modules_from_spec(self, specs):
        modules = list()
        for spec in specs:
            try:
                if spec in self.base.repo_module_dict:
                    specs.remove(spec)
                    modules.append(spec)
            except KeyError:
                logger.debug("Not a valid module: {}".format(spec))

        return modules

    def _update_files(self):
        success = False
        if self.opts.filenames:
            for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=False):
                try:
                    self.base.package_upgrade(pkg)
                    success = True
                except dnf.exceptions.MarkingError as e:
                    self.base._report_icase_hint(pkg_spec)
                    logger.info(_('No match for argument: %s'),
                                self.base.output.term.bold(pkg.location))
        return success

    def _update_packages(self):
        success = False
        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.upgrade(pkg_spec)
                success = True
            except dnf.exceptions.MarkingError as e:
                logger.info(_('No match for argument: %s'),
                            self.base.output.term.bold(pkg_spec))
        return success

    def _update_groups(self):
        if self.opts.grp_specs:
            self.base.read_comps(arch_filter=True)
            self.base.env_group_upgrade(self.opts.grp_specs)
            return True
        return False
