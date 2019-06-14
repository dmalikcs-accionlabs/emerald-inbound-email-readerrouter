import os
import sys
import argparse
import logging
import pkg_resources

from error import EmeraldEmailRouterDatabaseInitializationError
from exitcode import ExitCode
from version import __version__
from email_router import EmailRouterDatabaseSourceType, EmailRouter, EmailRouterSourceIdentifier
from router_instance_type import RouterInstanceType
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
    # see comment below about using complex types in argparse
    parser.add_argument('--router_instance_type',
                        required=True,
#                        type=RouterInstanceType.from_string,
                        type=str,
                        help='Specify instance type (defines location, data class, etc. - see devops docs)' +
                        os.linesep + 'Must be one of following: ' + ','.join([x.name for x in RouterInstanceType])),
    parser.add_argument('--router_db_source_file',
                        type=str,
                        help='Specify to include a JSON file that contains the email router database' +
                        os.linesep + 'Other methods may be supported')
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

    args = parser.parse_args(argv[1:])

    logger = logging.getLogger('main')
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if args.debug else logging.INFO)

    formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s',
                                  datefmt='%Y-%d-%mT%H:%M:%S%z')
    ch.setFormatter(formatter)

    logger.addHandler(ch)

    # initialize the router source type since there is no standard way to do this in argparse
    #  You can do it by setting the type, but the Namespace doesn't handle accessing the values
    # properly so it is better to make a string and then initialize complex type here
    try:
        router_instance_type = RouterInstanceType.from_string(type_name=args.router_instance_type)
    except ValueError:
        logger.critical('User specified invalid or unsupported router instance type with --router_instance_type' +
                        os.linesep + '\tMust be one of: ' + ','.join([x.name for x in RouterInstanceType]))
        return ExitCode.ARGUMENT_ERROR

    router_source_identifier = None
    if args.router_db_source_file is not None and len(args.router_db_source_file) > 0:
        # this means we assume our initialization will come from JSON file first
        logger.info('Add read of JSON file here')

        router_source_identifier = EmailRouterSourceIdentifier(
            source_type=EmailRouterDatabaseSourceType.JSONFILE,
            source_uri=args.router_db_source_file
        )

    # at this point fail if no source provided
    if router_source_identifier is None:
        logger.critical('Initialization error: no valid router initialization source provided' +
                        os.linesep + 'Specify with file using --router_db_source_file')
        return ExitCode.ARGUMENT_ERROR

    # log key provided arguments
    logger.info('Command line arguments: ' + os.linesep + '\t' +
                (os.linesep + '\t').join([k + ': ' + str(v) for k,v in sorted(vars(args).items())]))

    try:
        test = EmailRouter(router_db_source_identifier=router_source_identifier,
                           router_instance_type=router_instance_type,
                           debug=args.debug)
    except EmeraldEmailRouterDatabaseInitializationError as eex:
        logger.critical('Unable to initialize ' + appname + ': email router initialization error' +
                        os.linesep + 'Router database initialization error: ' + eex.message)
        return ExitCode.INITIALIZATION_ERROR
    except ValueError as vex:
        logger.critical('Unable to initialize ' + appname + ': email router initialization error' +
                        os.linesep + 'Exception: ' + str(vex.args[0]))
        return ExitCode.ARGUMENT_ERROR

    return ExitCode.SUCCESS

if __name__ == '__main__':
    retcode = emerald_inbound_email_readerrouter_launcher(sys.argv[0:])
    sys.exit(retcode)

