import os

# WSDL_URL = 'https://webservices.na2.netsuite.com/wsdl/v2017_2_0/netsuite.wsdl'
#NS_EMAIL= 'eqaqi@newstore.com'
#NS_PASSWORD = 'Super@1212'
# NS_ROLE = '1000'
# Development
# NS_ACCOUNT = '1927242'
# NS_APPID = 'AC3999DD-6398-4DA1-ADA8-5EFC61FB5F33'
# Sandbox
# NS_ACCOUNT = '4196917_SB2'
# NS_APPID = 'E969EDA2-1F3C-4365-BEF5-E937A442FF83'
NS_EMAIL = os.environ.get('netsuite_email', 'NOT_SET')
NS_PASSWORD = os.environ.get('netsuite_password', 'NOT_SET')
WSDL_URL = os.environ.get('netsuite_wsdl_url', 'NOT_SET')
NS_ROLE = os.environ.get('netsuite_role_id', 'NOT_SET')  # NewStore Integration
NS_ACCOUNT = os.environ.get('netsuite_account_id', 'NOT_SET')
NS_APPID = os.environ.get('netsuite_application_id', 'NOT_SET')
