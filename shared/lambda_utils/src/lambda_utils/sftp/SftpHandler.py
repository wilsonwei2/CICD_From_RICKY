import logging
import paramiko

logger = logging.getLogger(__name__)


class SftpHandler:
    def __init__(self, host, port, user, password):
        self.sftp_host = host
        self.sftp_port = port
        self.sftp_user = user
        self.sftp_password = password
        self.sftp_client = None

    def __call__(self):
        if self.sftp_client is None:
            transport = paramiko.Transport((self.get_sftp_host(), int(self.get_sftp_port())))
            transport.connect(username=self.get_sftp_user(), password=self.get_sftp_password())
            self.sftp_client = paramiko.SFTPClient.from_transport(transport)

    def get_sftp_host(self):
        return self.sftp_host

    def get_sftp_user(self):
        return self.sftp_user

    def get_sftp_password(self):
        return self.sftp_password

    def get_sftp_port(self):
        return self.sftp_port

    def get_sftp_client(self):
        return self.sftp_client

    def list_filenames_in_path(self, path):
        return self.get_sftp_client().listdir(path=path)

    def delete_file(self, path):
        return self.get_sftp_client().remove(path=path)

    def send_file(self, localpath, remotepath):
        return self.get_sftp_client().put(localpath=localpath, remotepath=remotepath)

    def get_sftp_stat(self, path):
        return self.get_sftp_client().stat(path=path)

    def create_sftp_dir(self, path):
        return self.get_sftp_client().mkdir(path=path)
