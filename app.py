import os
import sys
import argparse
import logging
import pkg_resources

from error import EmeraldEmailRouterDatabaseInitializationError
from exitcode import ExitCode
from version import __version__

from emerald_message.logging.logger import EmeraldLogger
from emerald_message.error import EmeraldEmailParsingError
from emerald_message.parsers.email.sendgrid_email_parser import ParsedEmail

from email_router.email_router_config_source import \
    EmailRouterDatastoreSourceType, EmailRouterSourceConfig
from email_router.email_router_datastore import EmailRouter
from email_router.router_instance_type import RouterInstanceType
from email_router.email_router_datastore import EmailRouterMatchResultCollection

from flask import Flask, request, render_template

APP_NAME = 'EMERALD INBOUND EMAIL READER ROUTER'
MIN_PYTHON_VER_MAJOR = 3
MIN_PYTHON_VER_MINOR = 6


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
                             os.linesep + 'Must be one of following: ' + ','.join(
                            [x.name for x in RouterInstanceType])),
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

    logger = EmeraldLogger(logging_module_name='main',
                           console_logging_level=logging.DEBUG if args.debug else logging.INFO)

    logger.logger.info('Starting ' + APP_NAME + ' Version ' + __version__)

    # initialize the router source type since there is no standard way to do this in argparse
    #  You can do it by setting the type, but the Namespace doesn't handle accessing the values
    # properly so it is better to make a string and then initialize complex type here
    try:
        router_instance_type = RouterInstanceType.from_string(type_name=args.router_instance_type)
    except ValueError:
        logger.logger.critical('User specified invalid or unsupported router instance type with --router_instance_type' +
                        os.linesep + '\tMust be one of: ' + ','.join([x.name for x in RouterInstanceType]))
        return ExitCode.ARGUMENT_ERROR

    router_source_identifier = None
    if args.router_db_source_file is not None and len(args.router_db_source_file) > 0:
        # this means we assume our initialization will come from JSON file first
        logger.logger.info('Add read of JSON file here')

        router_source_identifier = EmailRouterSourceConfig(
            source_type=EmailRouterDatastoreSourceType.JSONFILE,
            source_uri=args.router_db_source_file
        )

    # at this point fail if no source provided
    if router_source_identifier is None:
        logger.logger.critical('Initialization error: no valid router initialization source provided' +
                        os.linesep + 'Specify with file using --router_db_source_file')
        return ExitCode.ARGUMENT_ERROR

    # log key provided arguments
    logger.logger.info('Command line arguments: ' + os.linesep + '\t' +
                (os.linesep + '\t').join([k + ': ' + str(v) for k, v in sorted(vars(args).items())]))

    try:
        email_router = EmailRouter(router_db_source_identifier=router_source_identifier,
                                   router_instance_type=router_instance_type,
                                   debug=args.debug)
    except EmeraldEmailRouterDatabaseInitializationError as eex:
        logger.logger.critical('Unable to initialize ' + appname + ': email router initialization error' +
                        os.linesep + 'Router database initialization error: ' + eex.message)
        return ExitCode.INITIALIZATION_ERROR
    except ValueError as vex:
        logger.logger.critical('Unable to initialize ' + appname + ': email router initialization error' +
                        os.linesep + 'Exception: ' + str(vex.args[0]))
        return ExitCode.ARGUMENT_ERROR

    # now start the app
    logger.logger.warning('Initializing ' + APP_NAME + ' Version ' + __version__)

    app = Flask(__name__)

    @app.route('/', methods=['GET'])
    def index():
        """Show index page to confirm that server is running."""
        return render_template('index.html')

    @app.route('/inbound/' + router_instance_type.name.lower() + '/', methods=['POST'])
    def inbound_parse():
        """Process POST from Inbound Parse and print received data."""
        print('Type of request = ' + type(request).__name__)

        try:
            parsed_email = ParsedEmail(inbound_request=request)
        except EmeraldEmailParsingError as epex:
            logger.error('Error parsing email received for instance type ' + router_instance_type.name.lower() +
                         os.linesep + 'Exception: ' + os.linesep + epex.args[0]
                         )
            # DET FIXME - add logging here

        # now get a router destination for this
        match_result_set = \
            email_router.match_inbound_email(
                address_to_collection=parsed_email.email_container.email_envelope.address_to_collection,
                address_from=parsed_email.email_container.email_envelope.address_from,
                sender_ip=parsed_email.email_container.email_container_metadata.email_sender_ip)
        for result_count, this_result in enumerate(match_result_set.matched_target_results, start=1):
            print('Result #' + str(result_count) + ': ' + 'Target ' + str(this_result.matched_target_name) +
                  os.linesep + 'Destinations: ' + os.linesep + '\t' +
                  (os.linesep + '\t').join([str(x) for x in this_result.destinations]))

        # we expect to see these fields in the immutable dict:
        #
        #        print(str(payload) + os.linesep)
        # Tell SendGrid's Inbound Parse to stop sending POSTs
        # Everything is 200 OK :)
        return "OK"

    logger.logger.warning('Starting app using host=' + args.host + ' and port=' + str(args.port))
    app.run(debug=args.debug,
            host=args.host,
            port=args.port)

    return ExitCode.SUCCESS


def make_test_entry(email_router: EmailRouter):
    # now make a test entry
    match_result_set = \
        email_router.match_inbound_email(address_to_collection=['hello@my.com', 'bse@blue.ingestion.'],
                                         address_from='william@bseglobal.net',
                                         sender_ip='9.0.1.1')
    for result_count, this_result in enumerate(match_result_set.matched_target_results, start=1):
        print('Result #' + str(result_count) + ': ' + 'Target ' + str(this_result.matched_target_name) +
              os.linesep + 'Destinations: ' + os.linesep + '\t' +
              (os.linesep + '\t').join([str(x) for x in this_result.destinations]))

    print(os.linesep + 'The result set log ' + os.linesep +
          os.linesep.join(match_result_set.matched_info_log) + os.linesep)


if __name__ == '__main__':
    retcode = emerald_inbound_email_readerrouter_launcher(sys.argv[0:])
    sys.exit(retcode)
