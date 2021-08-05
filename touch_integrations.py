import os

integrations = os.listdir('./integrations')
root = os.getcwd()
print(root)
for integration in integrations:
    path = os.path.join(root, 'integrations', integration, 'README.md')
    print(f'Opening {path}')
    try:
        file = open(path, 'a')
        file.write('\n')
        file.close()
    except Exception as ex:
        print(ex)
