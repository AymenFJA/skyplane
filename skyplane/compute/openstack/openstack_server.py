import functools
import logging
import warnings

from cryptography.utils import CryptographyDeprecationWarning
from typing import Dict, Optional

from skyplane.compute.openstack.openstack_key_manager import OpenStackKeyManager

with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)
    import paramiko

from skyplane import exceptions
from skyplane.compute.openstack.openstack_auth import OpenStackAuthentication
from skyplane.compute.server import Server, ServerState, key_root
from skyplane.utils import imports, logger
from skyplane.utils.cache import ignore_lru_cache


class OpenStackServer(Server):
    """OpenStack Server class to support basic SSH operations"""

    def __init__(self, region_tag, instance_id, log_dir=None):
        super().__init__(region_tag, log_dir=log_dir)
        assert self.region_tag.split(":")[0] == "openstack"
        self.auth = OpenStackAuthentication()
        self.key_manager = OpenStackKeyManager(self.auth)
        self.op_region = self.region_tag.split(":")[1]
        self.instance_id = instance_id

    @property
    @functools.lru_cache(maxsize=None)
    def login_name(self) -> str:
        return "ubuntu"
    
    def uuid(self):
        return f"{self.region_tag}:{self.instance_id}"

    def get_openstack_instance_resource(self):
        op = self.auth.get_openstack_client()
        instance = op.get_server(self.instance_id)
        return instance

    @ignore_lru_cache()
    def public_ip(self) -> str:
        # todo maybe eventually support VPC peering?
        return self.get_openstack_instance_resource().public_v4

    @ignore_lru_cache()
    def private_ip(self) -> str:
        return self.get_openstack_instance_resource().private_v4

    @ignore_lru_cache()
    def instance_class(self) -> str:
        return self.get_openstack_instance_resource().flavor.original_name

    @ignore_lru_cache(ignored_value={})
    def tags(self) -> Dict[str, str]:
        raise NotImplementedError

    @ignore_lru_cache()
    def instance_name(self) -> Optional[str]:
        return self.get_openstack_instance_resource().name

    def network_tier(self):
        return "PREMIUM"

    def region(self):
        return self.op_region

    def instance_state(self):
        return self.get_openstack_instance_resource().status

    @property
    @ignore_lru_cache()
    def local_keyfile(self):
        key = self.auth.get_keypair(key_name)
        key_name = key.name
        if self.key_manager.key_exists_local(key_name):
            return self.key_manager.get_key(key_name)
        else:
            raise exceptions.BadConfigException(
                f"Failed to connect to AWS server {self.uuid()}. Delete local AWS keys and retry: `rm -rf {key_root / 'aws'}`"
            )

    def __repr__(self):
        return f"OpenStackServer(region_tag={self.region_tag}, instance_id={self.instance_id})"


    def terminate_instance_impl(self):
        servers = self.auth.list_servers()
        for server in servers:
            if server.id == self.instance_id:
                server.delete()
                return

    def get_ssh_client_impl(self):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                self.public_ip(),
                # username="ec2-user",
                username=self.login_name,
                # todo generate keys with password "skyplane"
                pkey=paramiko.RSAKey.from_private_key_file(str(self.local_keyfile)),
                look_for_keys=False,
                allow_agent=False,
                banner_timeout=200,
            )
            return client
        except paramiko.AuthenticationException as e:
            raise exceptions.BadConfigException(
                f"Failed to connect to AWS server {self.uuid()}. Delete local AWS keys and retry: `rm -rf {key_root / 'aws'}`"
            ) from e

    def get_sftp_client(self):
        t = paramiko.Transport((self.public_ip(), 22))
        # t.connect(username="ec2-user", pkey=paramiko.RSAKey.from_private_key_file(str(self.local_keyfile)))
        t.connect(username=self.login_name, pkey=paramiko.RSAKey.from_private_key_file(str(self.local_keyfile)))
        return paramiko.SFTPClient.from_transport(t)

    def open_ssh_tunnel_impl(self, remote_port):
        import sshtunnel

        sshtunnel.DEFAULT_LOGLEVEL = logging.FATAL
        return sshtunnel.SSHTunnelForwarder(
            (self.public_ip(), 22),
            # ssh_username="ec2-user",
            ssh_username=self.login_name,
            ssh_pkey=str(self.local_keyfile),
            host_pkey_directories=[],
            local_bind_address=("127.0.0.1", 0),
            remote_bind_address=("127.0.0.1", remote_port),
        )

    def get_ssh_cmd(self):
        # return f"ssh -i {self.local_keyfile} ec2-user@{self.public_ip()}"
        return f"ssh -i {self.local_keyfile} {self.login_name}@{self.public_ip()}"
