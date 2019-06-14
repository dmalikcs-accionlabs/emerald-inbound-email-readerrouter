import os
import datetime
import logging
import json
from dateutil.parser import parse
from pytz import timezone
from typing import NamedTuple, Optional, Collection, FrozenSet, List, Set
from tzlocal import get_localzone

from email_router.email_router_config_source import EmailRouterDatastoreSourceType, EmailRouterSourceConfig
from email_router.email_router_destination import EmailRouterDestinationType, EmailRouterDestinationConfig
from email_router.router_instance_type import RouterInstanceType
from error import EmeraldEmailRouterDatabaseInitializationError, EmeraldEmailRouterDuplicateTargetError


class EmailRouterRuleMatchPattern(NamedTuple):
    sender_domain: Optional[str] = None
    sender_name: Optional[str] = None
    recipient_name: Optional[str] = None
    attachment_included: Optional[bool] = None
    body_size_minimum: Optional[int] = None
    body_size_maximum: Optional[int] = None

    # set the hash and str methods so we can use these in sets
    def __str__(self):
        return EmailRouterRuleMatchPattern.__name__ + os.linesep + \
               os.linesep.join([
                   'sender_domain=' + str(self.sender_domain),
                   'sender_name=' + str(self.sender_name),
                   'recipient_name=' + str(self.recipient_name),
                   'attachment_included=' + str(self.attachment_included),
                   'body_size_minimum=' + str(self.body_size_minimum),
                   'body_size_maximum=' + str(self.body_size_maximum)
               ])

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, EmailRouterRuleMatchPattern):
            return False

        return (
                self.sender_domain == other.sender_domain and
                self.sender_name == other.sender_name and
                self.recipient_name == other.recipient_name and
                self.attachment_included == other.attachment_included and
                self.body_size_minimum == other.body_size_minimum and
                self.body_size_maximum == other.body_size_maximum
        )

    def __ne__(self, other):
        return not (__eq__(self, other))


# router rules are sorted only by sequence - rules with identical sequence have indeterminate sort order
class EmailRouterRule(NamedTuple):
    match_priority: float
    match_pattern: EmailRouterRuleMatchPattern

    # define hash and str so we can use in sets
    def __str__(self):
        return EmailRouterRule.__name__ + os.linesep + \
               os.linesep.join([
                   'match_priority=' + str(self.match_priority),
                   'match_pattern=' + os.linesep + str(self.match_pattern)
               ])

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, other):
        if not isinstance(other, EmailRouterRule):
            return False

        if self.match_priority != other.match_priority:
            return False
        if self.match_pattern != other.match_pattern:
            return False

        return True

    def __ne__(self, other):
        return not (__eq__(self, other))

    def __lt__(self, other):
        if not isinstance(other, EmailRouterRule):
            raise TypeError('Unable to compare object of type ' + type(other).__name__ + ' to ' +
                            EmailRouterRule.__name__)

        if self.match_priority < other.match_priority:
            return True
        elif self.match_priority > other.match_priority:
            return False

        # really indeterminate results - not guaranteed to be idempotent -
        # since we don't allow same seq diff rules this will never happen
        raise NotImplementedError(
            'Comparison found on two members of ' + EmailRouterRule.__name__ +
            ' with identical priority value "' + str(self.match_priority) + '" - not supported'
        )


class EmailRouterTargetConfig(NamedTuple):
    target_name: str
    target_priority: float
    router_rules: FrozenSet[EmailRouterRule]
    destinations: FrozenSet[EmailRouterDestinationConfig]

    # add the hash and str methods so we can put in (generally immutable) sets
    def __str__(self):
        return EmailRouterTargetConfig.__name__ + os.linesep + \
               os.linesep.join([
                   'target_name=' + str(self.target_name),
                   'target_priority=' + str(self.target_priority),
                   'router_rules=' + os.linesep + str(self.router_rules),
                   'destinations=' + os.linesep + str(self.destinations)
               ])

    def __lt__(self, other):
        if not isinstance(other, EmailRouterTargetConfig):
            raise TypeError('Unable to compare object of type ' + type(other).__name__ + ' to ' +
                            EmailRouterTargetConfig.__name__)

        if self.target_priority < other.target_priority:
            return True
        elif self.target_priority > other.target_priority:
            return False

        # really indeterminate results if equal - our collections using these abstractions will not allow
        #  so it should never happen
        raise NotImplementedError(
            'Comparison found on two members of ' + EmailRouterRule.__name__ +
            ' with identical priority value "' + str(self.target_priority) + '" - not supported'
        )


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

        # create the dictionary that will store rules by target name
        #  its members will have collections of sortable (prioritized) router rules and destinations
        self._router_config_by_target: Set[EmailRouterTargetConfig] = set()

    def add_target_routing_config(self,
                                  target_config: EmailRouterTargetConfig):
        # parse step 1 - make sure the parameter is really a target config
        if not isinstance(target_config, EmailRouterTargetConfig):
            raise TypeError('Unable to add target_config (type=' + type(target_config).__name__ +
                            ') is not of type ' + EmailRouterTargetConfig.__name__)

        # parse step 2 - do not allow multiple target configs that are identical or have identical
        #  target name
        if target_config in self._router_config_by_target:
            # callers will have option of ignoring or letting this halt operation
            raise EmeraldEmailRouterDuplicateTargetError(
                'Duplicate target config entry (' + target_config.target_name +
                ') found in source data - skipping this entry'
            )

        # parse step 3 - look for conflicting names (i.e. same name, different data) OR equal target priority
        for this_target in self._router_config_by_target:
            if target_config.target_name == this_target.target_name:
                raise EmeraldEmailRouterDatabaseInitializationError(
                    'Conflicting entry found for target name "' + this_target.target_name + '" - aborting new add' +
                    os.linesep + 'Duplicate target name with different configuration data'
                )
            if target_config.target_priority == this_target.target_priority:
                raise EmeraldEmailRouterDatabaseInitializationError(
                    'Conflicting entry found for target name "' + this_target.target_name + '" - aborting new add' +
                    os.linesep + 'Duplicate target priority - each must be unique for sorting'
                )

        # now add to the collection
        self._router_config_by_target.add(target_config)

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
    def router_db_source_identifier(self) -> EmailRouterSourceConfig:
        return self._router_db_source_identifier

    @classmethod
    def get_supported_router_db_source_types(cls):
        return frozenset([
            EmailRouterDatastoreSourceType.JSONFILE
        ])

    def __init__(self,
                 router_db_source_identifier: EmailRouterSourceConfig,
                 router_instance_type: RouterInstanceType,
                 debug: bool = False):

        if not isinstance(router_db_source_identifier, EmailRouterSourceConfig):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'router_db_source_identifier must be of type ' +
                             EmailRouterSourceConfig.__name__ + os.linesep +
                             'Value provided had type "' + str(type(router_db_source_identifier)))

        # now verify the source type and make sure it is supported
        if not issubclass(type(router_db_source_identifier.source_type), EmailRouterDatastoreSourceType):
            raise ValueError('Cannot initialize ' + type(self).__name__ + ': ' +
                             'source_type from router_db_source_identifier must be of type "' +
                             EmailRouterDatastoreSourceType.__name__ +
                             '" and have one of these values: ' +
                             ','.join([k.name for k in EmailRouterDatastoreSourceType]))
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

        if self.router_db_source_identifier.source_type == EmailRouterDatastoreSourceType.JSONFILE:
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
        except ValueError:
            # not naive so scale
            self.logger.debug('Provided timestamp includes timezone so scaling to UTC')
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
                required_elements = [
                    'match_rules',
                    'destination',
                    'target_priority']

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

                # target priority specifies which target is examined and handled first, since one inbound email
                #  may be handled to multiple targets.  The priority CANNOT BE THE SAME for multiple entries
                #  This will be enforced in the database initialization
                target_priority_from_json = tc_router_rules['target_priority']
                try:
                    target_priority = float(target_priority_from_json)
                    if target_priority <= 0:
                        raise ValueError('Negative number not allowed for target_priority')
                except ValueError as vex:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Cannot initialize as target "' + tc_name + '" contains an invalid target_priority value' +
                        os.linesep + 'Must be a positive number' +
                        os.linesep + 'Value provided = ' + str(target_priority_from_json) + ' (input type = ' +
                        type(target_priority_from_json).__name__ + ')' +
                        os.linesep + 'Exception message: ' + str(vex.args[0])
                    )

                # match_rules is an list of elements (at least one), each of which is a dict
                rule_count = len(tc_router_rules['match_rules'])
                if rule_count < 1:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Provided match_rules structure for instance type "' +
                        self.router_instance_type.value.instance_type_name.lower() +
                        '" contains no actual rules.  Aborting'
                    )

                rules_parse_error_log = dict()
                # accumulate all the rules in the source datastore and then we will write into config if all valid
                rules_for_target: List[EmailRouterRule] = list()

                for rule_count, this_rule in enumerate(tc_router_rules['match_rules'], start=1):
                    self.logger.info('Checking rule "' + str(this_rule) + '"')

                    try:
                        rule_match_priority = float(this_rule['match_priority'])
                    except KeyError:
                        raise EmeraldEmailRouterDatabaseInitializationError(
                            'Parameter "match_priority" not found in rule #' +
                            str(rule_count) + ' - aborting')

                    # initialize our text based fields, noting we treat empty strings as nulls
                    sender_domain = this_rule['sender_domain'] \
                        if ('sender_domain' in this_rule and len(this_rule['sender_domain']) > 0) \
                        else None
                    sender_name = this_rule['sender_name'] \
                        if ('sender_name' in this_rule and len(this_rule['sender_name']) > 0) \
                        else None
                    recipient_name = this_rule['recipient_name'] \
                        if ('recipient_name' in this_rule and len(this_rule['recipient_name'])) \
                        else None
                    attachment_included = this_rule['attachment_included'] \
                        if 'attachment_included' in this_rule else None
                    body_size_minimum = this_rule['body_size_minimum'] if 'body_size_minimum' in this_rule else None
                    body_size_maximum = this_rule['body_size_maximum'] if 'body_size_maximum' in this_rule else None

                    # if neither domain nor sender nor recipient specified, abort
                    if sender_domain is None and sender_name is None and recipient_name is None:
                        if rule_match_priority not in rules_parse_error_log:
                            rules_parse_error_log[rule_match_priority] = list()
                        rules_parse_error_log[rule_match_priority].append(
                            'No sender domain, sender name or recipient pattern specified - at least one required'
                        )
                        continue

                    if body_size_minimum is not None and (type(body_size_minimum) is not int or body_size_minimum < 0):
                        if rule_match_priority not in rules_parse_error_log:
                            rules_parse_error_log[rule_match_priority] = list()
                        rules_parse_error_log[rule_match_priority].append(
                            'body_size_minimum if specified must be a nonnegative integer (type given = ' +
                            type(body_size_minimum).__name__ + ')'
                        )
                        continue

                    if body_size_maximum is not None and (type(body_size_maximum) is not int or body_size_maximum < 0):
                        if rule_match_priority not in rules_parse_error_log:
                            rules_parse_error_log[rule_match_priority] = list()
                        rules_parse_error_log[rule_match_priority].append(
                            'body_size_maximum if specified must be a nonnegative integer (type given = ' +
                            type(body_size_maximum).__name__ + ')'
                        )
                        continue

                    if attachment_included is not None and type(attachment_included) is not bool:
                        if rule_match_priority not in rules_parse_error_log:
                            rules_parse_error_log[rule_match_priority] = list()
                        rules_parse_error_log[rule_match_priority].append(
                            'attachment_included must be a boolean if present (type given = ' +
                            type(attachment_included).__name__ + ')'
                        )
                        continue

                    # ok now we can initialize our rule
                    this_rule_match_pattern = EmailRouterRuleMatchPattern(
                        sender_domain=sender_domain,
                        sender_name=sender_name,
                        recipient_name=recipient_name,
                        attachment_included=attachment_included,
                        body_size_maximum=body_size_maximum,
                        body_size_minimum=body_size_minimum
                    )
                    # now incorporate the sequence so we can prioritize
                    rules_for_target.append(
                        EmailRouterRule(
                            match_pattern=this_rule_match_pattern,
                            match_priority=rule_match_priority
                        )
                    )

                if len(rules_parse_error_log) > 0:
                    error_data = list()
                    error_data.append('Unable to initialize - rule(s) had following errors: ')
                    for rule_match_priority in rules_parse_error_log:
                        error_data.append('Rule match priority ' + str(rule_match_priority) + os.linesep + '\t' +
                                          (os.linesep + '\t').join(
                                              [x for x in rules_parse_error_log[rule_match_priority]]))
                    raise EmeraldEmailRouterDatabaseInitializationError(os.linesep.join(error_data) + os.linesep)

                # at this point we can trust our rules_for_target collection and will shortly add to configuration
                #  first we need to validate the destination
                self.logger.info('Validated rules collection (count=' + str(len(rules_for_target)) +
                                 ') for target ' + tc_name)

                #
                #  Next make sure the destination works - we only support a limited number of options
                #  We have already done null checking for this required parameter
                destination_as_string = tc_router_rules['destination']
                if len(destination_as_string) == 0:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Unable to initialize - destination for target config "' + tc_name + '" is null - check JSON'
                    )
                try:
                    destination = EmailRouterDestinationType[destination_as_string.upper()]
                except KeyError:
                    raise EmeraldEmailRouterDatabaseInitializationError(
                        'Unable to initialize - destination for target config "' + tc_name + '" is not valid' +
                        os.linesep + 'Value provided = ' + destination_as_string +
                        os.linesep +
                        'Must be one of following: ' + ','.join([x.name for x in EmailRouterDestinationType])
                    )

                destination_uri = tc_router_rules['destination_uri'] \
                    if 'destination_uri' in tc_router_rules and len(tc_router_rules['destination_uri']) > 0 \
                    else None

                self.logger.info('Validated destination for target config + ' + tc_name)

                target_config = EmailRouterTargetConfig(
                    target_name=tc_name,
                    target_priority=target_priority,
                    router_rules=frozenset(rules_for_target),
                    destinations=frozenset([
                        EmailRouterDestinationConfig(destination_sequence=10,
                                                     destination_type=destination,
                                                     destination_uri=destination_uri)
                    ])
                )

                self.logger.debug('The target config = ' + os.linesep + str(target_config))

                # now make a rules entry for the specified tc_name (target)
                #  FIXME - noting that JSON only supports one destination per target config right now, but
                #  rules database will support multiple ones.  Hard-coding sequence now
                self.router_rules_datastore.add_target_routing_config(target_config)

                self.logger.info('Completed initialization of rules configuration for target config ' + tc_name)

        # getting here means success
        self._router_db_initialized = True
