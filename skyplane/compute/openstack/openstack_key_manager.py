import os
from pathlib import Path

from skyplane import exceptions as skyplane_exceptions
from skyplane.compute.openstack.openstack_auth import OpenStackAuthentication
from skyplane.compute.server import key_root
from skyplane.utils import logger


class OpenStackKeyManager:
    """Stores SSH keys for access to OpenStack VMs."""

    def __init__(self, auth: OpenStackAuthentication, local_key_dir: Path = key_root / "openstack"):
        self.auth = auth
        self.local_key_dir = local_key_dir

    def key_exists_op(self, op_region: str, key_name: str) -> bool:
        """Checks if a key exists in OpenStack Project Allocation."""
        op_client = self.auth.get_openstack_client()
        return self.client.compute.find_keypair(key_name)

    def key_exists_local(self, key_name: str) -> bool:
        """Checks if a key exists locally."""
        return (self.local_key_dir / f"{key_name}").exists()

    def make_key(self, op_region: str, key_name: str) -> Path:
        """Creates a key in OpenStack and stores it locally."""
        if self.key_exists_op(op_region, key_name):
            logger.error(f"Key {key_name} already exists in OpenStack region {op_region}")
            raise skyplane_exceptions.PermissionsException(
                f"Key {key_name} already exists in OpenStack region {op_region}, please delete it first or use a different key name."
            )
        if self.key_exists_local(key_name):
            logger.error(f"Key {key_name} already exists locally")
            raise skyplane_exceptions.PermissionsException(
                f"Key {key_name} already exists locally, please delete it first or use a different key name."
            )
        op = self.auth.get_openstack_client()
        local_key_file = self.local_key_dir / f"{key_name}"
        local_key_file.parent.mkdir(parents=True, exist_ok=True)
        logger.fs.debug(f"[OpenStack] Creating keypair {key_name} in {op_region}")
        key_pair = op.create_keypair(name=key_name)
        with local_key_file.open("w") as f:
            key_str = key_pair.private_key
            if not key_str.endswith("\n"):
                key_str += "\n"
            f.write(key_str)
        os.chmod(local_key_file, 0o600)
        return local_key_file

    def delete_key(self, op_region: str, key_name: str):
        """Deletes a key from OpenStack and locally."""
        if self.key_exists_op(op_region, key_name):
            op = self.auth.get_openstack_client()
            logger.fs.debug(f"[OpenStack] Deleting keypair {key_name} in {op_region}")
            key_pair = self.key_exists_op(op_region, key_name)
            op.delete_keypair(key_pair.id)
        if self.key_exists_local(key_name):
            (self.local_key_dir / f"{key_name}").unlink()

    def get_key(self, key_name: str) -> Path:
        """Returns path to local keyfile."""
        return self.local_key_dir / f"{key_name}"

    def ensure_key_exists(self, op_region: str, key_name: str, delete_remote: bool = True) -> Path:
        """Ensures that a key exists in OpenStack and locally, creating it if necessary. Raise an exception if it's on OpenStack and not locally."""
        local_exists, remote_exists = self.key_exists_local(key_name), self.key_exists_op(op_region, key_name)
        if local_exists and remote_exists:
            return self.get_key(key_name)
        elif not local_exists and not remote_exists:
            return self.make_key(op_region, key_name)
        elif local_exists and not remote_exists:
            local_key_path = self.get_key(key_name)
            logger.warning(f"Key {key_name} exists locally but not in OpenStack region {op_region}. Moving the local key {local_key_path}.bak")
            local_key_path.rename(local_key_path.with_suffix(".pem.bak"))
            return self.make_key(op_region, key_name)
        else:
            if delete_remote:
                logger.warning(f"Key {key_name} exists in OpenStack region {op_region} but not locally. Deleting the remote key.")
                self.delete_key(op_region, key_name)
                return self.make_key(op_region, key_name)
            else:
                raise skyplane_exceptions.PermissionsException(
                    f"Key {key_name} exists in OpenStack region {op_region} but not locally. Please delete the key from OpenStack or move it locally."
                )
