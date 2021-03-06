# This file is part of GuestI.
#
# GuestI is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SSP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GuestI.  If not, see <http://www.gnu.org/licenses/>.

"""Contains top level info for cloud control modules."""

import abc

__provides__ = [
    "ABS_CLOUD"
]

__all__ = __provides__


class ABS_CLOUD(object):

    """Represents an skeleton CLOUD class."""

    __metaclass__ = abc.ABCMeta
    __args = None

    def __init__(self, args=None):
        self.__args = args

    @abc.abstractmethod
    def install(self):
        """Make OS machine image by performing installation in the cloud."""
