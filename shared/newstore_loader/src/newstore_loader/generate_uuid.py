#! /usr/bin/env python
# Copyright (C) 2017 NewStore Inc, all rights reserved.

"""
Generate a v5 namespace based UUID.

Copyright (C) 2017 NewStore, Inc. All rights reserved.
"""

import sys
import uuid


def create_uuid(tenant, *salt):
    """
    Create a v5 UUID for tenant and salt.
    """
    namespace = uuid.uuid5(uuid.NAMESPACE_DNS, tenant)
    return str(uuid.uuid5(namespace, "-".join(map(str, salt))))

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.stderr.write("usage: {} tenant id ...\n".format(sys.argv[0]))
        sys.stderr.write("\tfor example: generate_uuid.py newstoredev store 1\n")
        sys.exit(1)

    sys.stdout.write("{}\n".format(create_uuid(*sys.argv[1::])))
