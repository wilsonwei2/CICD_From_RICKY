class CustomException(Exception):
    fmt = 'An unspecified error occurred'

    def __init__(self, **kwargs):
        self.msg = self.fmt.format(**kwargs)
        Exception.__init__(self, self.msg)
        self.kwargs = kwargs


class NotSupportedNewStoreWebHookException(CustomException):
    fmt = 'Webhook in path not supported: {path}'
