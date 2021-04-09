import json

def get_local_testconfig(testconfig_default={}):
    """ load local test configuration (when exists) """
    loaded_testconfig = {}
    try:
        with open("/project/testconfig.local.json", "r") as testconfig_file:
            testconfig_data = testconfig_file.read()
        loaded_testconfig = json.loads(testconfig_data)
    except FileNotFoundError:
        pass

    return dict(testconfig_default, **loaded_testconfig)
