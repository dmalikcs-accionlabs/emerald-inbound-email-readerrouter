import os
import datetime
import logging
import json
from dateutil.parser import parse
from pytz import timezone
from enum import Enum, unique, auto
from typing import NamedTuple, Optional, FrozenSet
from tzlocal import get_localzone

from router_instance_type import RouterInstanceType, RouterInstanceTypeConfig
from error import EmeraldEmailRouterDatabaseInitializationError


@unique
class EmailRouterDatabaseSourceType(Enum):
    JSONFILE = auto()
    UNSUPPORTED = auto()


class EmailRouterSourceIdentifier(NamedTuple):
    source_type: EmailRouterDatabaseSourceType
    source_uri: str
    source_username_or_access_key: Optional[str] = None
    source_password_or_secret_key: Optional[str] = None


class EmailRouterRuleMatchPattern(NamedTuple):
    sender_domain: Optional[str] = None
    sender_name: Optional[str] = None
    recipient_name: Optional[str] = None
    attachment_included: Optional[bool] = None
    body_size_minimum: Optional[int] = None
    body_size_maximum: Optional[int] = None


@unique
class EmailRouterRuleDestinationType(Enum):
    DIRECT_PROCESSING = auto()


class EmailRouterRule(NamedTuple):
    sequence: float
    match_pattern: EmailRouterRuleMatchPattern
    destination_type: EmailRouterRuleDestinationType = EmailRouterRuleDestinationType.DIRECT_PROCESSING
    destination_uri: Optional[str] = None


class EmailRouterRulesDatastore:
    @property
    def datastore_name(self) -> str:
        return self._datastore_name

    @property
    def revision_datetime(self) -> datetime.datetime:
        return self._revision_datetime

    @property
    def revision_number(self) -> int:
        return self._revision_number

    @property
    def instance_type(self) -> RouterInstanceType:
        return self._instance_type

    def __init__(self,
                 name: str,
                 revision_datetime: datetime.datetime,
                 revision_number: int,
                 instance_type: RouterInstanceType):
        self._datastore_name = name
        self._revision_datetime = revision_datetime
        self._revision_number = revision_number
        self._instance_type = instance_type


class EmailRouter:
    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def logger(self):
        return self._logger

    @property
    def router_db_initialized(self) -> bool:
        return self._router_db_initialized

    @property
    def router_rules_datastore(self) -> Optional[EmailRouterRulesDatastore]:
        return self._router_rules_datastore

    @property
    def router_instance_type(self) -> RouterInstanceType:
        return self._router_instance_type

    @property
    def router_db_source_identifier(self) -> EmailRouterSourceIdentifier:
        return self._router_db_source_identifier

    @classmethod
    def get_required_format_datetime(self) -> str:
        return '%Y-%m-%dT%H:%M:%S %Z'

    @classmethod
    def get_supported_router_db_source_types(cls):
        return frozenset([
            EmailRouterDatabaseSourceType.JSONFILE
        ])

    def __init__(self,
                 router_db_source_identifier: EmailRouterSourceIdentifier,
                 router_instance_type: RouterInstanceType,
                 debug: bool = False):

        if not isinstance(router_db_source_identifier, EmailRouterSourceIdentifier):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'router_db_source_identifier must be of type ' +
                             EmailRouterSourceIdentifier.__name__ + os.linesep +
                             'Value provided had type "' + str(type(router_db_source_identifier)))

        # now verify the source type and make sure it is supported
        if not issubclass(type(router_db_source_identifier.source_type), EmailRouterDatabaseSourceType):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'source_type from router_db_source_identifier must be of type "' +
                             EmailRouterDatabaseSourceType.__name__ +
                             '" and have one of these values: ' +
                             ','.join([k.name for k in EmailRouterDatabaseSourceType]))
        if router_db_source_identifier.source_type not in type(self).get_supported_router_db_source_types():
            raise ValueError('Unsupported router db source type "' + str(router_db_source_identifier.source_type) +
                             os.linesep + 'Supported value(s): ' +
                             ','.join([x.name for x in type(self).get_supported_router_db_source_types()]))

        if not isinstance(router_instance_type, RouterInstanceType):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'router_instance_type must be of type ' +
                             RouterInstanceType.__name__ + os.linesep +
                             'Value provided had type "' + str(type(router_instance_type)))

        self._router_instance_type = router_instance_type
        self._router_db_source_identifier = router_db_source_identifier

        self._debug = debug

        self._logger = logging.getLogger(type(self).__name__)
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG if self.debug else logging.INFO)

        formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s',
                                      datefmt='%Y-%d-%mT%H:%M:%S')
        ch.setFormatter(formatter)

        self.logger.addHandler(ch)

        # now match the source type and initialize as needed
        self._router_db_initialized = False
        self._router_rules_datastore = None

        if self.router_db_source_identifier.source_type == EmailRouterDatabaseSourceType.JSONFILE:
            self._initialize_from_jsonfile()
        else:
            raise \
                EmeraldEmailRouterDatabaseInitializationError('Unsupported router database source type "' +
                                                              str(self.router_db_source_identifier.source_type) +
                                                              '" - must be one of ' + os.linesep +
                                                              ','.join([x.name for x in type(
                                                                  self).get_supported_router_db_source_types()]))

    def _initialize_from_jsonfile(self):
        # read the json file from the source identifier
        if type(self.router_db_source_identifier.source_uri) is not str or \
                len(self.router_db_source_identifier.source_uri) == 0:
            raise EmeraldEmailRouterDatabaseInitializationError('Empty or missing router db source identifier' +
                                                                ': for JSON file should specify a valid filename')

        try:
            with open(os.path.expanduser(self.router_db_source_identifier.source_uri),
                      encoding='utf-8',
                      mode='r') as json_config_source:
                json_data = json.load(json_config_source)
                print('JSON = ' + str(json_data))
        except json.JSONDecodeError as jdex:
            error_string = 'Source JSON file "' + \
                           str(self.router_db_source_identifier.source_uri) + '" cannot be decoded' + \
                           os.linesep + 'Exception detail: ' + str(jdex.args)
            self.logger.critical(error_string)
            raise EmeraldEmailRouterDatabaseInitializationError(error_string)
        except FileNotFoundError as fnfex:
            error_string = 'Source JSON file "' + \
                           str(self.router_db_source_identifier.source_uri) + \
                           '"' + ' not found or not accessible to this process' + os.linesep + \
                           'Exception detail: ' + str(fnfex.args)
            self.logger.critical(error_string)
            raise EmeraldEmailRouterDatabaseInitializationError(error_string)
        except Exception as ex:
            error_string = 'Exception reading router source DB JSON file "' + \
                           '"' + str(self.router_db_source_identifier.source_uri) + os.linesep + \
                           'Exception type: ' + str(type(ex)) + os.linesep + \
                           'Exception msg: ' + str(ex.args)
            self.logger.critical(error_string)
            raise EmeraldEmailRouterDatabaseInitializationError(error_string)

        # now initialize from the dictionary
        #  We only want to use the entries for our instance type

        ###########
        #  REFACTOR NOTE
        #  TODO: this is a hurry up parser - can be refactored to be table driven
        ###########

        # first parse top level parameters name and revision date - we must have these to create data
        #  store and do further work
        required_top_level_attributes = ['name',
                                         'revision_number',
                                         'revision_datetime',
                                         'instance_type',
                                         'router_rules']
        missing_but_required = []
        for this_attribute in required_top_level_attributes:
            if this_attribute not in json_data:
                missing_but_required.append(this_attribute)

        if len(missing_but_required) > 0:
            raise \
                EmeraldEmailRouterDatabaseInitializationError(
                    'Unable to initialize - source JSON missing these required attribute(s): ' +
                    os.linesep + ','.join([x for x in sorted(missing_but_required)]) +
                    os.linesep + 'Keys are CASE SPECIFIC and should be LOWERCASE' +
                    os.linesep + 'JSON found = ' + os.linesep + str(json_data) + os.linesep)

        # ok we know they are here.  In the hurry up parser we aren't being fancy in the data read
        router_db_name = json_data['name']
        if type(router_db_name) is not str or len(router_db_name) < 3:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Unable to initialize - source JSON' +
                ' must have a "name" attribute as string of at least 3 chars in length')

        router_db_revision_number = json_data['revision_number']
        if type(router_db_revision_number) is not int or router_db_revision_number < 0:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Unable to initialize - source JSON must have a "revision_number" attribute as ' +
                'non-negative integer (not a string)' + os.linesep + 'Value provided = ' +
                str(router_db_revision_number) + ' (type=' + str(type(router_db_revision_number))
            )

        #
        # timestamp will be parsed as best effort BUT only time offsets in ISO8601 format will be used
        #  In other words 2019-04-12T07:00:12 EST will be processed as a naive timestamp (ignore timezone)
        #  BUT, 2019-04-12T07:00:12-0300 WILL be processed as a timestamp with GMT offset -3
        #
        try:
            router_db_revision_datetime = parse(json_data['revision_datetime'],
                                                dayfirst=False,
                                                yearfirst=False)
        except ValueError as vex:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Unable to initialize - source JSON has invalid' +
                'revision_datetime parameter' +
                ' "' + str(json_data['revision_datetime']) + '"' +
                os.linesep + 'Unable to parse' +
                os.linesep + 'Exception data: ' + str(vex.args))
        except Exception as ex:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Unable to initialize - source JSON has invalid' +
                'revision_datetime parameter' +
                ' "' + str(json_data['revision_datetime']) + '"' +
                os.linesep + 'Exception type: ' + str(type(ex)) +
                os.linesep + 'Exception data: ' + str(ex.args))

        # and convert to UTC.  If naive, localize it to LOCAL.  Otherwise scale
        try:
            local_timezone_zone_string = get_localzone().zone
            router_db_revision_datetime_as_utc = \
                timezone(local_timezone_zone_string).localize(router_db_revision_datetime)
        except ValueError as vex:
            # not naive so scale
            router_db_revision_datetime_as_utc = router_db_revision_datetime.astimezone(timezone('UTC'))
        else:
            self.logger.info('Naive timezone')

        self.logger.info('Router datastore timestamp = ' + str(router_db_revision_datetime))
        self.logger.info('Router datastore timestamp (UTC) = ' + str(router_db_revision_datetime_as_utc))

        # now parse the instance type and make sure it matches us - abort if not
        try:
            router_db_instance_type = RouterInstanceType[json_data['instance_type'].upper()]
        except KeyError:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Unable to initialize - specified instance type "' + str(json_data['instance_type']) + '"' +
                ' is not a valid instance type' + os.linesep +
                'Must be one of ' + ','.join([x.name.lower() for x in RouterInstanceType])
            )
        # is it our type?
        if router_db_instance_type != self.router_instance_type:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Specified JSON is for a different router instance type "' + router_db_instance_type.name.lower() +
                os.linesep + 'Program specified this instance to be ' + self.router_instance_type.name.lower()
            )

        # now create the initial datastore
        self._router_rules_datastore = \
            EmailRouterRulesDatastore(name=router_db_name,
                                      revision_datetime=router_db_revision_datetime_as_utc,
                                      revision_number=router_db_revision_number,
                                      instance_type=router_db_instance_type)

        # next we have to see if included JSON has records for our instance type.  If not we will abort
        target_or_client_count = len(json_data['router_rules'])
        if target_or_client_count < 1:
            raise EmeraldEmailRouterDatabaseInitializationError(
                'Caller did not provide any target / client entries in JSON data - no rules to parse' +
                os.linesep + 'Aborting')

        # pass 1 - because of complex json we have to do two level loop to get names of the instance keys
        #  provided.  Remember, we only read rules for our specified instance type (i.e. BLUE)
        #
        target_rules_data = None
        target_or_client_keys_found = []
        for this_target_or_client in json_data['router_rules']:
            self.logger.info('Reading data for target / client = ' + str(this_target_or_client))

            for tc_name, tc_router_rules in this_target_or_client.items():
                target_or_client_keys_found.append(tc_name)

                # now we have a valid instance set - time to parse the rules
                #  If we fail here we will abort initialization
                self.logger.info('Parsing data for target / client "' + tc_name + '"')
                self.logger.info('Rules = ' + str(tc_router_rules))

                #  now make sure required elements for instance data are there
                required_elements = ['match_rules', 'destination']
                required_but_not_found = []
                for this_required in required_elements:
                    if this_required not in tc_router_rules:
                        required_but_not_found.append(this_required)
                if len(required_but_not_found) > 0:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Aborting as instance data for router instance type "' +
                        self.router_instance_type.value.instance_type_name.lower() +
                        '" did not contain required element(s): ' +
                        ','.join([x for x in required_but_not_found])
                    )
                self.logger.info('Required elements found - parsing rules')

                # match_rules is an list of elements (at least one), each of which is a dict
                rule_count = len(tc_router_rules['match_rules'])
                if rule_count < 1:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Provided match_rules structure for instance type "' +
                        self.router_instance_type.value.instance_type_name.lower() +
                        '" contains no actual rules.  Aborting'
                    )

                rules_parse_result = dict()
                for rule_count, this_rule in enumerate(tc_router_rules['match_rules'], start=1):
                    self.logger.info('Checking rule "' + str(this_rule) + '"')

                    try:
                        rule_seq = float(this_rule['seq'])
                    except KeyError as kex:
                        raise EmeraldEmailRouterDatabaseInitializationError('Parameter "seq" not found in rule #' +
                                                                            str(rule_count) + ' - aborting')

                    sender_domain = this_rule['sender_domain'] if 'sender_domain' in this_rule else None
                    sender_name = this_rule['sender_name'] if 'sender_name' in this_rule else None
                    recipient_name = this_rule['recipient_name'] if 'recipient_name' in this_rule else None
                    attachment_included = this_rule['attachment_included'] \
                        if 'attachment_included' in this_rule else None
                    body_size_minimum = this_rule['body_size_minimum'] if 'body_size_minimum' in this_rule else None
                    body_size_maximum = this_rule['body_size_maximum'] if 'body_size_maximum' in this_rule else None

                    # if neither domain nor sender nor recipient specified, abort
                    if sender_domain is None and sender_name is None and recipient_name is None:
                        if rule_seq not in rules_parse_result:
                            rules_parse_result[rule_seq] = list()
                        rules_parse_result[rule_seq].append(
                            'No sender domain, sender name or recipient pattern specified - at least one required'
                        )
                        continue

                    if body_size_minimum is not None and (type(body_size_minimum) is not int or body_size_minimum < 0):
                        if rule_seq not in rules_parse_result:
                            rules_parse_result[rule_seq] = list()
                        rules_parse_result[rule_seq].append(
                            'body_size_minimum if specified must be a nonnegative integer (type given = ' +
                            type(body_size_minimum).__name__ + ')'
                        )
                        continue

                    if body_size_maximum is not None and (type(body_size_maximum) is not int or body_size_maximum < 0):
                        if rule_seq not in rules_parse_result:
                            rules_parse_result[rule_seq] = list()
                        rules_parse_result[rule_seq].append(
                            'body_size_maximum if specified must be a nonnegative integer (type given = ' +
                            type(body_size_maximum).__name__ + ')'
                        )
                        continue

                    if attachment_included is not None and type(attachment_included) is not bool:
                        if rule_seq not in rules_parse_result:
                            rules_parse_result[rule_seq] = list()
                        rules_parse_result[rule_seq].append(
                            'attachment_included must be a boolean if present (type given = ' +
                            type(attachment_included).__name__ + ')'
                        )
                        continue

                if len(rules_parse_result) > 0:
                    error_data = []
                    error_data.append('Unable to initialize - rule(s) had following errors: ')
                    for rule_seq in rules_parse_result:
                        error_data.append('Rule seq ' + str(rule_seq) + os.linesep + '\t' +
                                          (os.linesep + '\t').join([x for x in rules_parse_result[rule_seq]]))
                    raise EmeraldEmailRouterDatabaseInitializationError(os.linesep.join(error_data) + os.linesep)

                # ok now we can initialize our rule
                this_rule_match_pattern = EmailRouterRuleMatchPattern(
                    sender_domain=sender_domain,
                    sender_name=sender_name,
                    recipient_name=recipient_name,
                    attachment_included=attachment_included,
                    body_size_maximum=body_size_maximum,
                    body_size_minimum= body_size_minimum
                )

                #
                #  Next make sure the destination works - we only support a limited number of options
                #  We have already done null checking for this required parameter
                destination = tc_router_rules['destination']
                destination_uri = tc_router_rules['destination_uri'] if 'destination_uri' in tc_router_rules else None

                self.logger.warn('CODE IN PROGRESS UPDATE - add final routing rules entry for ' + tc_name)

        # getting here means success
        self._router_db_initialized = True
