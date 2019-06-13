import os
import sys
import argparse
import logging
import pkg_resources

from exitcode import ExitCode
from version import __version__

APP_NAME = 'EMERALD INBOUND EMAIL READER ROUTER'
MIN_PYTHON_VER_MAJOR=3
MIN_PYTHON_VER_MINOR=6

def get_command_info_as_string() -> str:
    the_package = __name__
    the_path = '/'.join(('reference', 'command_notes.txt'))
    the_reference_info = pkg_resources.resource_string(the_package, the_path).decode('utf-8')

    return the_reference_info


def emerald_inbound_email_readerrouter_launcher(argv):
    try:
        appname = __name__.split('.')[0]
    except KeyError:
        appname = __name__

    if sys.version_info.major < MIN_PYTHON_VER_MAJOR or (
            sys.version_info.major == MIN_PYTHON_VER_MAJOR and sys.version_info.minor < MIN_PYTHON_VER_MINOR):
        print('Unable to run this script - python interpreter must be at or above version ' +
              str(MIN_PYTHON_VER_MAJOR) + '.' + str(MIN_PYTHON_VER_MINOR) +
              os.linesep + '\tVersion is ' + str(sys.version_info.major) + '.' + str(sys.version_info.minor))
        return ExitCode.PythonVersionError
    else:
        print('Running on python interpreter version ' +
              str(sys.version_info.major) + '.' + str(sys.version_info.minor))

    parser = argparse.ArgumentParser(prog=APP_NAME,
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=get_command_info_as_string())
    parser.add_argument('--version',
                        action='version',
                        version=__version__)
    parser.add_argument('--host',
                        type=str,
                        action='store',
                        default='127.0.0.1',
                        help='Specify source IP address (defaults to localhost)')
    parser.add_argument('--port',
                        type=int,
                        default=8080,
                        action='store',
                        help='Specify TCP port for listening process ' + os.linesep +
                             '\t(>1024 to run without sudo / root)')
    parser.add_argument('--skip_connectivity_check',
                        action='store_true',
                        default=False,
                        help='Specify to avoid initial network probe - for testing with localhost only')
    parser.add_argument('--debug',
                        action='store_true',
                        default=False,
                        help='Specify to add additional logging as well as debugging mode in Flask')

    args = parser.parse_args(None if argv[0:] else ['--help'])

    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG)

    return ExitCode.SUCCESS

if __name__ == '__main__':
    retcode = emerald_inbound_email_readerrouter_launcher(sys.argv[0:])
    sys.exit(retcode)

