


def initialize_application_state(app_config, application_state):

    """

    :param application_state:
    :return:
    """
    application_state['symbols'] = {}
    for symbol in app_config['symbols']:
        application_state['symbols'][symbol] = {}

    application_state['is_busy_time'] = False


def initialize_application_state_for_run(app_config, application_state):

    """

    :param application_state:
    :return:
    """
    application_state['breakouts'] = {}
    application_state['retests'] = {}
    application_state['breakout_idx'] = {}
    application_state['retest_idx'] = {}
    # for symbol in app_config['symbols']:
    #     application_state['symbols'][symbol] = {}
    #
    # application_state['is_busy_time'] = False
