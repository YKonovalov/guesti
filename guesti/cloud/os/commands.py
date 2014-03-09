# This file is part of GuestI.
#
# GuestI is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SSP is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GuestI.  If not, see <http://www.gnu.org/licenses/>.

import sys
import traceback
import argparse
from time import sleep, gmtime, strftime
import abc
from guesti.cloud.common import ABS_CLOUD
from guesti.envdefault import EnvDefault
import guesti.constants

from glanceclient import client as glance_client
from cinderclient import client as cinder_client
from keystoneclient.v2_0 import client as keystone_client
from novaclient import client as nova_client

import logging

LOG = logging.getLogger(guesti.constants.PROGRAM_NAME + ".os")
LOADER_NAME = "Cloud iPXE installers boot ISO image"


def add_args_os(parser):
    p_os = parser.add_argument_group('OpenStack Environment', """OpenStack credentials for accessing cloud services.
It's recommended to create a restricted user account if you planning to
store credentials to be able to run this tool from cron. You can also
specify this options using corresponding environment variables.""")
    p_os.add_argument('--os-auth-url', action=EnvDefault, envvar='OS_AUTH_URL',
                      help='URL for keystone API endpoint')
    p_os.add_argument('--os-region-name', action=EnvDefault, envvar='OS_REGION_NAME', default=None,
                      help='Region name to use for running installator instance')
    p_os.add_argument('--os-tenant-id', action=EnvDefault, envvar='OS_TENANT_ID',
                      help='Project id to use for running installator instance')
    p_os.add_argument('--os-tenant-name', action=EnvDefault, envvar='OS_TENANT_NAME',
                      help='Project name to use for running installator instance')
    p_os.add_argument('--os-username', action=EnvDefault, envvar='OS_USERNAME',
                      help='username for keystone authentication')
    p_os.add_argument('--os-password', action=EnvDefault, envvar='OS_PASSWORD',
                      help='secret for keystone authentication')
    p_os.add_argument('--os-image-url', action=EnvDefault, envvar='OS_IMAGE_URL',
                      help='URL for Glance image storage API endpoint')
    return p_os


def add_args_to_parser(parser):
    # cloud
    p_cloud = parser.add_parser('os', help='OpenStack cloud')
    p_command = p_cloud.add_subparsers(title='Supported commands', help=False, dest='command')
    # install
    p_install = p_command.add_parser('install', help='Launch and snapshot a scripted install using modified iPXE image')
    p_install_template = p_install.add_argument_group('Template', """A machine template attributes to be used to register image""")
    p_install_template.add_argument('--template-name', '-t', dest='template_name', required=True,
                                    help='Name to assign to newly created template')

    p_install_instance = p_install.add_argument_group('Installator Instance Parameters', """Installation will be performed in cloud VM instance. Here you can
adjust VM attributes according to OS installer system requirements.""")
    p_install_instance.add_argument('--ipxe-image-id', action=EnvDefault, envvar='IPXE_IMAGE_ID',
                                    help="""Special cloud ipxe.iso boot image snapshot is required for installers boot to succeed.
It should be modified to request iPXE script from cloud user-data URL. See more info in README.
Please specify existing snapshot-id of cloud ipxe image. You can upload and create snapshot with
os-upload-cloud-ipxe tool""")
    p_install_instance.add_argument('--install-flavor-id', action=EnvDefault, envvar='INSTALL_FLAVOR_ID',
                                    help='Type of installation machine')
    p_install_instance.add_argument('--install-network-id', action=EnvDefault, envvar='INSTALL_NETWORK_ID',
                                    help='Network to use for installation')
    p_install_instance.add_argument('--virtualization-type', dest='virt_type', choices=['kvm-virtio', 'kvm-lagacy'], default="kvm-virtio",
                                    help='Specify "kvm-lagacy" for guest with no support for VirtIO (default: kvm-virtio). Will be inherited by result template.')

    p_install_loader = p_install.add_argument_group('PXE Loader Parameters', """Required iPXE loader options for booting OS installer from the network. It could
be either Linux boot options or multiboot options. For Linux you must specify --kernel and --initrd.
For multiboot --kernel and one or more --module normally required.""")
    p_install_loader.add_argument('--kernel', dest='kernel', required=True,
                                  help='URL for installer kernel file with kernel options to make auto install happend. E.g. "repo={URL} ks={URL}" for anaconda-based distros and "preseed/url={URL} ..."  for debian-based distros.')
    p_install_loader.add_argument('--initrd', dest='initrd',
                                  help='URL for installer initrd file (for normal boot)')
    p_install_loader.add_argument('--module', action='append', dest='modules',
                                  help='URL(s) for installer modules file (for multiboot)')

    add_args_os(p_install)

    # upload
    p_upload = p_command.add_parser('upload_loader',
                                    help='Upload to Glance storage and make a snapshot of iPXE boot image in the cloud')
    p_upload_os = add_args_os(p_upload)

    p_upload.add_argument('--ipxe-file', type=argparse.FileType('r'),
                          help='iPXE boot loader file', default="ipxe.iso")


class OS_CLOUD(ABS_CLOUD):

    """ OpenStack Cloud interface"""

    name = "os"
    __cleanup = True
    __quiet = None
    __menu = None
    __runid = None

    template_name = None
    installer_name = None
    installer_image_id = None
    bootdisk_size = None
    virt_type = None
    install_flavor_id = None

    auth_url = None
    tenant = None
    username = None
    password = None

    glance_url = None

    def __init__(self, args):
        super(OS_CLOUD, self).__init__(args)

        self.__cleanup = args.cleanup
        self.__quiet = args.quiet
        self.__runid = strftime("%Y%m%d-%H%M%S", gmtime())

        # Cloud endpoints and credentials
        self.auth_url = args.os_auth_url
        self.region = args.os_region_name
        self.tenant = args.os_tenant_id
        self.tenant_name = args.os_tenant_name
        self.username = args.os_username
        self.password = args.os_password
        if args.command == "upload_loader":
            self.glance_url = args.os_image_url
            LOG.debug("cloud: {0}, image storage: {1}".format(self.auth_url, self.glance_url))
        elif args.command == "install":
            # Prepare loader menu
            modules = ""
            if args.modules:
                for m in args.modules:
                    modules = modules + "module " + m + "\n"
            kernel = args.kernel
            initrd = "initrd " + args.initrd + "\n" if args.initrd else "\n"
            self.__menu = "#!ipxe\nkernel {0}\n{1}{2}boot\n".format(kernel, initrd, modules)
            LOG.debug("iPXE script:\n---\n{0}\n---\n".format(self.__menu))

            # Template params
            self.template_name = args.template_name + " (updated " + strftime("%Y-%m-%d", gmtime()) + ")"
            LOG.debug("Template: {0}".format(self.template_name))

            # Install machine params
            self.installer_name = "Installer of {0}".format(args.template_name)
            self.installer_image_id = args.ipxe_image_id
            self.install_network_id = args.install_network_id
            self.virt_type = args.virt_type
            self.install_flavor_id = args.install_flavor_id
            self.glance_url = args.os_image_url
            LOG.debug("installer: {0}, loader: {1}, boot: {2}, virt: {3}, machine: {4}".format(
                self.installer_name, self.installer_image_id, self.bootdisk_size, self.virt_type, self.install_flavor_id))
            LOG.debug("cloud: {0}".format(self.auth_url))

        LOG.info("Initialized")

    def install(self):
        """ Launch os installer, wait for it to finnish and take a snapshot """
        # run time globals
        c2c = None
        instance_id = None
        install_ok = False
        image_id = None
        image_ok = False
        success = False
        exitcode = 0

        try:
            # Install
            LOG.info("About to run install instance from {0} with disk {1} and name {2} ".format(
                self.installer_image_id,
                self.bootdisk_size,
                self.installer_name))

            osk = keystone_client.Client(username=self.username, password=self.password, tenant_id=self.tenant, auth_url=self.auth_url)
            if not osk.authenticate():
                LOG.error("Failed to authenticate to {0} tenant:{1} as:{2}.".format(self.auth_url, self.tenant, self.username))
                exitcode = 1
                sys.exit(exitcode)
            osi = glance_client.Client("1", endpoint=self.glance_url, token=osk.auth_token)
            osc = nova_client.Client('2', username=self.username, api_key=self.password, region_name=self.region, project_id=self.tenant_name, auth_url=self.auth_url, insecure=True, http_log_debug=True)
            instance = osc.servers.create(name=self.installer_name,
                                            image=self.installer_image_id,
                                            flavor=self.install_flavor_id,
                                            userdata=self.__menu,
                                            nics=[{'net-id': self.install_network_id}])
            try:
                instance_id = instance.id
            except KeyError:
                LOG.error("Failed to run instance: {0}.".format(self.installer_name))
                exitcode = 3
                sys.exit(exitcode)

            LOG.info("Installer launched: {0} {1}. Waiting for instance to stop...".format(
                     instance_id, self.installer_name))

            for i in range(120):
                instance_updated = osc.servers.get(instance_id)
                try:
                    s = instance_updated.status
                except KeyError:
                    LOG.error("Failed to find running instance {0} {1}.".format(instance_id, self.installer_name))
                    exitcode = 4
                    sys.exit(exitcode)
                if s in ["BUILD", "ACTIVE"]:
                    if not self.__quiet:
                        pass
                        #sys.stdout.write('.')
                        #sys.stdout.flush()
                elif s == "SHUTOFF":
                    LOG.info("Installation finnished {0} {1}".format(
                             instance_id, self.installer_name))
                    install_ok = True
                    break
                else:
                    LOG.warning("Instance {0} {1} is in unexpected state: {2}.".format(instance_id, self.installer_name, s))
                sleep(60)

            if not install_ok:
                LOG.error("Intallation {0} {1} timed out.".format(instance.id, self.installer_name))
                exitcode = 5
                sys.exit(exitcode)

            # Snapshot
            LOG.info("About to snapshot install instance {0} to {1}".format(
                     instance_id, self.template_name))
            image = instance.create_image(self.template_name)

            LOG.debug("image: {0}".format(image))
            try:
                image_id = image
            except KeyError:
                LOG.error("Failed to create template {1} from instance {0}".format(instance_id, self.template_name))
                exitcode = 6
                sys.exit(exitcode)

            LOG.info("Template {0} is creating. Waiting for image {1} to finnish copying...".format(
                     self.template_name, image_id))
            for i in range(120):
                try:
                    image_updated = osi.images.get(image_id)
                    s = image_updated.status
                except KeyError:
                    LOG.error("Failed to find template {0}.".format(image_id))
                    exitcode = 7
                    sys.exit(exitcode)
                else:
                    pass
                if s in ["queued","saving"]:
                    LOG.info("Template {0} is copying. Waiting.".format(image_id))
                elif s == "active":
                    LOG.info("Template {0} is ready.".format(image_id))
                    image_ok = True
                    break
                else:
                    LOG.warning("Template is in unexpected state: {0}.".format(s))
                sleep(20)
            success = True

        except Exception as e:
            LOG.error("Install failed for {0}".format(self.template_name))
            exitcode = 1
            LOG.critical("{0}\n{1}\n{2}\n".format(
                "-" * 3 + " Exception details " + "-" * 50, traceback.format_exc(), "-" * 60))

        finally:
            if self.__cleanup:
                LOG.info("Cleaning up")
                if instance_id:
                    if osc:
                        LOG.info("Terminating temporary (installer) instance ({0})".format(instance_id))
                        instance = osc.servers.get(instance_id)
                        instance.delete()
                    else:
                        LOG.debug("Not removing installer instance because we don't have a connection to cloud")
                else:
                    LOG.debug("Not removing installer instance because we don't have a instance ID")
            else:
                LOG.warning("Leaving installer instance and disk (requested by --no-cleanup)")

            if image_id:
                LOG.info("-" * 60 + "\nTemplate Details:\n    ID: {0}\n  Name: {1}\n".format(
                         image_id, self.template_name))

            sys.exit(exitcode)

    def upload_loader(self):
        """ Upload iPXE loader ISO to object storage and make a bootable snapshot. """

        cloud_ipxe_image = "ipxe.iso"
        snapshot_name = LOADER_NAME + " " + self.__runid

        c2_file = None
        image_id = None
        success = False
        exitcode = 0

        try:
            # upload
            osk = keystone_client.Client(username=self.username, password=self.password, tenant_id=self.tenant, auth_url=self.auth_url)
            if not osk.authenticate():
                LOG.error("Failed to authenticate to {0} tenant:{1} as:{2}.".format(self.auth_url, self.tenant, self.username))
                exitcode = 1
                sys.exit(exitcode)
            osi = glance_client.Client("1", endpoint=self.glance_url, token=osk.auth_token)
            LOG.info("Uploading {0} to Glance image storage ({1} name: {2})".format(cloud_ipxe_image, self.glance_url, snapshot_name))
            data = open(cloud_ipxe_image, "r")
            image = osi.images.create(name=snapshot_name,data=data,disk_format='raw',container_format='bare')
            #image = osi.images.create(name=snapshot_name,data=cloud_ipxe_image,size=os.path.getsize(cloud_ipxe_image))
            #meta = {'container_format': 'bare','disk_format': 'raw', 'data': data, 'is_public': True, 'min_disk': 0, 'min_ram': 0, 'name': snapshot_name, 'properties': {'distro': 'rhel'}}
            #image.update(**meta)

            image_id = image.id

            if not image.status:
                LOG.error("Upload failed ({0})".format(cloud_ipxe_image))
                exitcode = 4
                sys.exit(exitcode)
            LOG.info("Uploaded {0} {1}".format(image_id, snapshot_name))

        except Exception as e:
            LOG.error("Upload failed")
            exitcode = 1
            LOG.critical("{0}\n{1}\n{2}\n".format(
                "-" * 3 + " Exception details " + "-" * 50, traceback.format_exc(), "-" * 60))

        finally:
            if self.__cleanup:
                LOG.info("Cleaning up")
            else:
                LOG.warning("Leaving temporary object (requested by --no-cleanup)")

            if image_id:
                LOG.info("-" * 3 + " UPLOADED\nSnapshot Details:\n ID: {0}\n Name: {1}\n".format(
                         image_id, snapshot_name))

            sys.exit(exitcode)
