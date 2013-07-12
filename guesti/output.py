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

"""Logging setup for output to console and files."""

import logging
import sys


class TerminalHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            if record.levelno < logging.WARNING:
                stream = sys.stdout
            else:
                stream = sys.stderr
            fs = "%s\n"

            try:
                if (isinstance(msg, unicode) and
                        getattr(stream, 'encoding', None)):
                    ufs = fs.decode(stream.encoding)
                    try:
                        stream.write(ufs % msg)
                    except UnicodeEncodeError:
                        stream.write((ufs % msg).encode(stream.encoding))
                else:
                    stream.write(fs % msg)
            except UnicodeError:
                stream.write(fs % msg.encode("UTF-8"))

            stream.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


class NoNewLinesFilter(logging.Filter):

    def filter(self, record):
        record.msg = record.msg.replace("\n", " ")
        return True


def setup_top_logger(name, syslog_loglevel=logging.ERROR, terminal_loglevel=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(syslog_loglevel)

    if terminal_loglevel != None:
        t = TerminalHandler()
        t.setLevel(terminal_loglevel)
        t_format = logging.Formatter('%(message)s')
        t.setFormatter(t_format)
        logger.addHandler(t)

    s = logging.handlers.SysLogHandler(address='/dev/log', facility=logging.handlers.SysLogHandler.LOG_DAEMON)
    s.setLevel(syslog_loglevel)
    s_format = logging.Formatter('%(name)s: %(message)s')
    s.setFormatter(s_format)
    s.addFilter(NoNewLinesFilter())
    logger.addHandler(s)

    return logger
