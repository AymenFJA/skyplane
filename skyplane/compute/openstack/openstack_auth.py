import os
import openstack

from typing import Optional
from skyplane.config_paths import config_path
from skyplane.config import SkyplaneConfig
from skyplane.utils import imports

PUBLIC_ENDPOINT = "https://js2.jetstream-cloud.org:5000/v3/"
PRIVATE_ENDPOINT = "https://js2.jetstream-cloud.org:5000/v3/"
DIRECT_ENDPOINT = "https://js2.jetstream-cloud.org:5000/v3/"

OBJ_REQ_RETRIES = 5
CONN_READ_TIMEOUT = 10
VPC_API_VERSION = "2021-09-21"


class OpenStackAuthentication:
    def __init__(self, config: Optional[SkyplaneConfig] = None):
        """Loads OpenStack Cloud authentication details."""
        if not config is None:
            self.config = config
        else:
            self.config = SkyplaneConfig.load_config(config_path)

        self._auth_url = os.environ.get('JET_OS_AUTH_URL')
        self._auth_type = os.environ.get('JET_OS_AUTH_TYPE')
        self._compute_api_version = 2
        self._identity_interface = os.environ.get('JET_OS_INTERFACE')
        self._application_credential_secret = os.environ.get('JET_OS_APPLICATION_CREDENTIAL_SECRET')
        self._application_credential_id = os.environ.get('JET_OS_APPLICATION_CREDENTIAL_ID')


    def get_openstack_client(self):
        def get_openstack_creds():
            return {
                'auth_url': self.auth_url,
                'auth_type': self.auth_type,
                'compute_api_version': self.compute_api_version,
                'identity_interface': self.identity_interface,
                'application_credential_secret': self.application_credential_secret,
                'application_credential_id': self.application_credential_id
            }
        return openstack.connect(**get_openstack_creds())


    @property
    def auth_url(self):
        return self._auth_url

    @auth_url.setter
    def auth_url(self, value):
        self._auth_url = value

    @property
    def auth_type(self):
        return self._auth_type

    @property
    def compute_api_version(self):
        return self._compute_api_version

    @property
    def identity_interface(self):
        return self._identity_interface


    @property
    def application_credential_secret(self):
        return self._application_credential_secret


    @property
    def application_credential_id(self):
        return self._application_credential_id
