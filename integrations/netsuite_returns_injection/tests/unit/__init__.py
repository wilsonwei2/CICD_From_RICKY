import sys
path_src = sys.path[0]
if not path_src.endswith('src/'):
    sys.path[0] = '{pth}/src/'.format(pth=path_src)
