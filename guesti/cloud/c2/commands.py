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
from guesti.cloud.c2.utils import *
import guesti.constants
import boto.ec2
import logging

LOG = logging.getLogger(guesti.constants.PROGRAM_NAME + ".c2")
LOADER_NAME = "Cloud iPXE installers boot ISO image"


def add_args_c2(parser):
    p_c2 = parser.add_argument_group('CrocCloud Environment', """CROC Cloud credentials for accessing cloud services.
It's recommended to create a restricted user account if you planning to
store credentials to be able to run this tool from cron. You can also
specify this options using corresponding environment variables""")
    p_c2.add_argument('--ec2-url', action=EnvDefault, envvar='EC2_URL',
                      help='URL for cloud API')
    p_c2.add_argument('--ec2-access-key', action=EnvDefault, envvar='EC2_ACCESS_KEY',
                      help='project:user id for cloud authorization')
    p_c2.add_argument('--ec2-secret-key', action=EnvDefault, envvar='EC2_SECRET_KEY',
                      help='secret key for cloud authorization')
    return p_c2


def add_args_to_parser(parser):
    # cloud
    p_cloud = parser.add_parser('c2', help='CROC cloud')
    p_command = p_cloud.add_subparsers(title='Supported commands', help=False, dest='command')
    # install
    p_install = p_command.add_parser('install', help='Launch and snapshot a scripted install using modified iPXE image')
    p_install_template = p_install.add_argument_group('Template', """A machine template attributes to be used to register image""")
    p_install_template.add_argument('--template-name', '-t', dest='template_name', required=True,
                                    help='Name to assign to newly created template')

    p_install_instance = p_install.add_argument_group('Installator Instance Parameters', """Installation will be performed in cloud VM instance. Here you can
adjust VM attributes according to OS installer system requirements.""")
    p_install_instance.add_argument('--ipxe-snapshot-id', action=EnvDefault, envvar='IPXE_SNAPSHOT_ID',
                                    help="""Special cloud ipxe.iso boot image snapshot is required for installers boot to succeed.
It should be modified to request iPXE script from cloud user-data URL. See more info in README.
Please specify existing snapshot-id of cloud ipxe image. You can upload and create snapshot with
c2-upload-cloud-ipxe tool""")
    p_install_instance.add_argument('--install-machine', dest='instance_type', default="m1.small",
                                    help='Type of installation machine (default: m1.small)')
    p_install_instance.add_argument('--disk-size', dest='install_volume_size', default=10,
                                    help='Size of the install destination volume in GB (default: 10). Will be the same in result template.')
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

    add_args_c2(p_install)

    # upload
    p_upload = p_command.add_parser('upload_loader',
                                    help='Upload to object storage and register iPXE boot image in the cloud')
    p_upload_c2 = add_args_c2(p_upload)

    p_upload_c2.add_argument('--s3-url', action=EnvDefault, envvar='S3_URL',
                             help='URL for object storage')

    p_upload.add_argument('--s3-bucket', action=EnvDefault, envvar='S3_BUCKET',
                          help='to store temporary boot images')
    p_upload.add_argument('--ipxe-file', type=argparse.FileType('r'),
                          help='iPXE boot loader file', default="ipxe.iso")


class C2_CLOUD(ABS_CLOUD):

    """ CROC Cloud interface"""

    name = "c2"
    __cleanup = True
    __quiet = None
    __menu = None
    __runid = None

    template_name = None
    installer_name = None
    loader_snapshot = None
    bootdisk_size = None
    virt_type = None
    instance_type = None

    c2_url = None
    access_key = None
    secret_key = None

    s3_url = None
    s3_bucket = None

    def __init__(self, args):
        super(C2_CLOUD, self).__init__(args)

        self.__cleanup = args.cleanup
        self.__quiet = args.quiet
        self.__runid = strftime("%Y%m%d-%H%M%S", gmtime())

        # Cloud endpoints and credentials
        self.c2_url = args.ec2_url
        self.access_key = args.ec2_access_key
        self.secret_key = args.ec2_secret_key
        if args.command == "upload_loader":
            self.s3_url = args.s3_url
            self.s3_bucket = args.s3_bucket
            LOG.debug("cloud: {0}, object storage: {1}, temp bucket: {2}".format(self.c2_url, self.s3_url, self.s3_bucket))
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
            self.loader_snapshot = args.ipxe_snapshot_id
            self.bootdisk_size = args.install_volume_size
            self.virt_type = args.virt_type
            self.instance_type = args.instance_type
            LOG.debug("installer: {0}, loader: {1}, boot: {2}, virt: {3}, machine: {4}".format(
                self.installer_name, self.loader_snapshot, self.bootdisk_size, self.virt_type, self.instance_type))
            LOG.debug("cloud: {0}".format(self.c2_url))

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
                self.loader_snapshot,
                self.bootdisk_size,
                self.installer_name))

            c2c = c2_connection(self.c2_url, self.access_key, self.secret_key)
            instance_id = c2_launch_install(c2c, self.loader_snapshot,
                                            volume_size=self.bootdisk_size,
                                            instance_name=self.installer_name,
                                            user_data=self.__menu,
                                            virt=self.virt_type,
                                            instance_type=self.instance_type)
            if not instance_id:
                LOG.error("Failed to run instance: {0}.".format(self.installer_name))
                exitcode = 3
                sys.exit(exitcode)
            LOG.info("Installer launched: {0} {1}. Waiting for instance to stop...".format(
                     instance_id, self.installer_name))

            for i in range(120):
                r = c2c.get_all_instances(instance_ids=[instance_id])
                try:
                    instance = r[0].instances[0]
                except KeyError:
                    LOG.error("Failed to find running instance {0} {1}.".format(instance_id, self.installer_name))
                    exitcode = 4
                    sys.exit(exitcode)
                if instance.state in ["running", "pending"]:
                    if not self.__quiet:
                        pass
                        #sys.stdout.write('.')
                        #sys.stdout.flush()
                elif instance.state == "stopped":
                    LOG.info("Installation finnished {0} {1} launched at: {2}".format(
                             instance_id, self.installer_name, instance.launch_time))
                    install_ok = True
                    break
                else:
                    LOG.warning("Instance {0} {1} is in unexpected state: {0}.".format(instance_id, self.installer_name, instance.state))
                sleep(60)

            if not install_ok:
                LOG.error("Intallation {0} {1} timed out.".format(instance_id, self.installer_name))
                exitcode = 5
                sys.exit(exitcode)

            # Snapshot
            LOG.info("About to snapshot install instance {0} to {1}".format(
                     instance_id, self.template_name))
            image_id = c2_snapshot_instance(c2c, instance_id, self.template_name)

            if not image_id:
                LOG.error("Failed to create template {1} from instance {0}".format(instance_id, self.template_name))
                exitcode = 6
                sys.exit(exitcode)

            LOG.info("Template {0} is creating. Waiting for image {1} to finnish copying...".format(
                     self.template_name, image_id))
            for i in range(120):
                images = c2c.get_all_images(image_ids=[image_id])
                try:
                    image = images[0]
                except KeyError:
                    LOG.error("Failed to find template {0}.".format(image_id))
                    exitcode = 7
                    sys.exit(exitcode)
                if image.state == "pending":
                    LOG.info("Template {0} is in 'pending' state. Waiting.".format(image_id))
                elif image.state == "available":
                    LOG.info("Template {0} is ready.".format(image_id))
                    image_ok = True
                    break
                else:
                    LOG.warning("Template is in unexpected state: {0}.".format(image.state))
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
                    if c2c:
                        LOG.info("Terminating temporary (installer) instance ({0})".format(instance_id))
                        tids = c2c.terminate_instances(instance_ids=[instance_id])
                        try:
                            tid = tids[0]
                        except KeyError:
                            LOG.error("Bad response to terminate instance {0} command. Installer instance maybe left in stopped state.".format(instance_id))
                            exitcode = 7

                        if not tid:
                            LOG.error("Empty response to terminate instance {0} command. Installer instance maybe left in stopped state.".format(instance_id))
                            exitcode = 8
                        # if user stop execution (by Ctrl-C) boto returns Instance object
                        # instead of simply string ID. Workaroud it here.
                        if not (instance_id == tid or "Instance:" + instance_id == str(tid)):
                            LOG.error("Oops. Seems like I have killed some random instance! Wanted: {0}, Killed: {1},".format(instance_id, tid))
                            exitcode = 9
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
        snapshot_id = None
        success = False
        exitcode = 0

        try:
            # upload
            LOG.info("Uploading {0} to C2 object storage (bucket {1}, key: {2})".format(cloud_ipxe_image, self.s3_bucket, snapshot_name))
            c2_file = c2os_upload(access_key=self.access_key, secret_key=self.secret_key, url=self.s3_url,
                                  image_filename=cloud_ipxe_image, bucket=self.s3_bucket, name=snapshot_name)
            if not c2_file:
                LOG.error("Upload failed ({0})".format(cloud_ipxe_image))
                exitcode = 4
                sys.exit(exitcode)
            LOG.info("Uploaded to ({0})".format(c2_file))

            # snapshot
            c2c = c2_connection(self.c2_url, self.access_key, self.secret_key)
            snapshot_id = c2_create_snapshot(c2c, c2_file, snapshot_name)
            if not snapshot_id:
                LOG.error("Error creating snapshot. Exiting")
                sys.exit(0)
            LOG.info("Snapshot: {0}".format(snapshot_id))
            for i in range(120):
                snapshot = c2c.get_all_snapshots(snapshot_ids=[snapshot_id])[0]
                if snapshot.status == "creating":
                    LOG.info("{0} percent done: {1}".format(snapshot_id, snapshot.progress))
                elif snapshot.status == "completed":
                    success = True
                    break
                else:
                    LOG.critical("Unexpected status of snapshot {0}: {1}. Exiting".format(snapshot_id, snapshot.status))
                    sys.exit(1)
                sleep(1)

        except Exception as e:
            LOG.error("Upload failed")
            exitcode = 1
            LOG.critical("{0}\n{1}\n{2}\n".format(
                "-" * 3 + " Exception details " + "-" * 50, traceback.format_exc(), "-" * 60))

        finally:
            if self.__cleanup:
                LOG.info("Cleaning up")
                if c2_file:
                    c2r_file = c2os_delete(access_key=self.access_key, secret_key=self.secret_key, url=self.s3_url,
                                           bucket=self.s3_bucket, name=snapshot_name)
                    if c2r_file:
                        LOG.debug("Removed temporary object (bucket: {0}, name: {1})".format(self.s3_bucket, snapshot_name))
                    else:
                        LOG.error("Remove of temp object failed (bucket: {0}, name: {1})".format(self.s3_bucket, snapshot_name))
                        exitcode = 4
                    if snapshot_id and not success:
                        LOG.warning("Snapshot is not complete")
                else:
                    LOG.debug("Not removing temporary object - upload was not OK")
            else:
                LOG.warning("Leaving temporary object (requested by --no-cleanup)")

            if snapshot_id:
                LOG.info("-" * 3 + " UPLOADED\nSnapshot Details:\n ID: {0}\n Name: {1}\n".format(
                         snapshot_id, snapshot_name))

            sys.exit(exitcode)
