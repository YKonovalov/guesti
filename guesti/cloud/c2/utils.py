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

import os
import sys
import urlparse

import boto
from boto.ec2.connection import EC2Connection
from boto.ec2.regioninfo import RegionInfo
from boto.s3.connection import S3Connection
from boto.exception import S3ResponseError, S3PermissionsError
from boto.s3.key import Key
from xml.dom.minidom import parseString
from xml.dom.ext import PrettyPrint
from StringIO import StringIO
from time import time
import base64
import logging
import guesti.constants

LOG = logging.getLogger(guesti.constants.PROGRAM_NAME + ".c2.utils")

callback_out_period = 1  # sec
callback_last_out_time = int(time())


def toprettyxml_fixed(node, encoding='utf-8'):
    tmpStream = StringIO()
    PrettyPrint(node, stream=tmpStream, encoding=encoding)
    return tmpStream.getvalue()


def c2_connection(url, access_key, secret_key):
    if not boto.config.has_section("Boto"):
        boto.config.add_section("Boto")
    boto.config.set("Boto", "num_retries", "0")

    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    host, port, rest = (netloc + "::").split(":", 2)
    conn = EC2Connection(
        is_secure=(scheme == 'https'),
        region = RegionInfo(name="croc", endpoint=host),
        port = int(port) if port else None,
        path = path,
        aws_access_key_id = access_key,
        aws_secret_access_key = secret_key
    )
    return conn


def c2_request(action, args):
    if not boto.config.has_section("Boto"):
        boto.config.add_section("Boto")
    boto.config.set("Boto", "num_retries", "0")

    scheme, netloc, path, params, query, fragment = urlparse.urlparse(
        os.environ['EC2_URL'])
    host, port, rest = (netloc + "::").split(":", 2)
    conn = EC2Connection(
        is_secure=(scheme == 'https'),
        region = RegionInfo(name="croc", endpoint=host),
        port = int(port) if port else None,
        path = path,
        aws_access_key_id = os.environ['EC2_ACCESS_KEY'],
        aws_secret_access_key = os.environ['EC2_SECRET_KEY']
    )

    resp = conn.make_request(action, args)
    print toprettyxml_fixed(parseString(resp.read())).strip()
    dom = parseString(resp.read())
    print dom.getElementsByTagName("snapshotId")[0]
    return resp


def c2_create_snapshot(conn, volume, description):
    resp = conn.make_request(
        "CreateSnapshot", {"VolumeId": volume, "Description": description})
    if resp.status == 200:
        dom = parseString(resp.read())
        sid = dom.getElementsByTagName("snapshotId")[0].childNodes[0].data
        return sid


def c2_launch_install(conn, snapshot_id, instance_name=None, volume_size=10, user_data=None, virt="kvm-virtio", instance_type="m1.small"):
    resp = conn.make_request("RunInstances", {"ImageId": "cmi-00000000",
                                              "BlockDeviceMapping.1.DeviceName": "cdrom1",
                                              "BlockDeviceMapping.1.Ebs.SnapshotId": snapshot_id,
                                              "BlockDeviceMapping.2.DeviceName": "disk1",
                                              "BlockDeviceMapping.2.Ebs.VolumeSize": volume_size,
                                              "VirtualizationType": virt,
                                              "MinCount": 1, "MaxCount": 1,
                                              "Description": instance_name,
                                              "InstanceType": instance_type,
                                              "UserData": base64.b64encode(user_data)})
    if resp.status == 200:
        dom = parseString(resp.read())
        iid = dom.getElementsByTagName("instanceId")[0].childNodes[0].data
        return iid
    else:
        print "Unable to run instance. Code {0}".format(resp.status)
        print toprettyxml_fixed(parseString(resp.read())).strip()


def c2_snapshot_instance(conn, instance_id, description=None):
    resp = conn.make_request("SnapshotInstance", {"InstanceId": instance_id,
                                                  "ImageDescription": description})
    if resp.status == 200:
        dom = parseString(resp.read())
        iid = dom.getElementsByTagName("ImageId")[0].childNodes[0].data
        return iid
    else:
        print "Unable to snapshot instance. Code {0}".format(resp.status)
        print toprettyxml_fixed(parseString(resp.read())).strip()


def progress_cb(bytes_complete, bytes_total):
    global callback_last_out_time
    now = int(time())
    if now - callback_last_out_time > callback_out_period:
        LOG.info("Transfered {0} of {1} bytes".format(bytes_complete, bytes_total))
        callback_last_out_time = now


def c2os_upload(image_filename, access_key, secret_key, url, bucket, name):
    LOG.debug("Got {0}".format(url))
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    host, port, rest = (netloc + "::").split(":", 2)
    is_secure = scheme == "https"
    port = int(port) if port else None
    conn = S3Connection(access_key, secret_key, host=host, port=port,
                        is_secure=is_secure, calling_format=boto.s3.connection.OrdinaryCallingFormat())
    try:
        b = conn.get_bucket(bucket)
    except S3ResponseError as e:
        LOG.error("Can't access bucket {0}: {1}, code {2}".format(bucket, e.reason, e.status))
        LOG.info("Please make sure that bucket specified exists and is accessible")
        return None
    except S3PermissionsError as e:
        LOG.error("Can't access bucket {0}: {1}, code {2}".format(bucket, e.reason, e.status))
        LOG.info("Please make sure that the user is allowed to access the bucket specified")
        return None

    k = Key(b)
    k.key = name
    r = k.set_contents_from_filename(image_filename, cb=progress_cb, num_cb=4)
    LOG.debug(str(r))
    return "/" + bucket + "/" + name


def c2os_delete(access_key, secret_key, url, bucket, name):
    LOG.debug("Got {0}".format(url))
    scheme, netloc, path, params, query, fragment = urlparse.urlparse(url)
    host, port, rest = (netloc + "::").split(":", 2)
    is_secure = scheme == "https"
    port = int(port) if port else None
    conn = S3Connection(access_key, secret_key, host=host, port=port,
                        is_secure=is_secure, calling_format=boto.s3.connection.OrdinaryCallingFormat())
    try:
        b = conn.get_bucket(bucket)
    except S3ResponseError as e:
        LOG.error("Can't access bucket {0}: {1}, code {2}".format(bucket, e.reason, e.status))
        LOG.info("Please make sure that bucket specified exists and is accessible")
        return None
    except S3PermissionsError as e:
        LOG.error("Can't access bucket {0}: {1}, code {2}".format(bucket, e.reason, e.status))
        LOG.info("Please make sure that the user is allowed to access the bucket specified")
        return None

    k = Key(b)
    k.key = name
    b.delete_key(k)
    return "/" + bucket + "/" + name
