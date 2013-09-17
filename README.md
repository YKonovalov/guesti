GuestI
======

**GuestI** ( *Guest Installer* ) - a cloud machine image build automation tool.
The main idea is to facilate the fact that majority of operating systems
nowdays have their distribution and installer on the internet. So, to
create a machine template all we need - is to boot and perform a scripted
install of a selected OS directly from the internet. Cloud supported:

 - **C2** - *Croc Cloud platform*
 - **OS** - *OpenStack cloud platform*

To boot a installer guest of the internet this tool needs iPXE loader,
specifically configured to read boot commands from the cloud metadata URL.

Using
=====

After configuring your cloud environment (see below), you can spawn and snapshot an installer instance with:

    $ U=http://mirror.yandex.ru/scientificlinux/6/x86_64/os
    $ guesti {os|c2} install \
        --template-name "Scientific Linux 6" \
        --initrd  $U/images/pxeboot/initrd.img \
        --kernel "$U/images/pxeboot/vmlinuz repo=$U ks=http://storage.cloud.croc.ru/kss/ScientificLinux-6"

There are more examples in the examples/launchers/ directory. You can use them to create machine templates in
your cloud. For example to create some images in OpenStack run:

    guesti-os-install-centos-6
    guesti-os-install-debian-7
    guesti-os-install-debian-unstable
    guesti-os-install-fedora-17
    guesti-os-install-fedora-18
    guesti-os-install-fedora-19
    guesti-os-install-fedora-20
    guesti-os-install-opensuse-factory
    guesti-os-install-scientificlinux-6

Configuring your cloud environment
==================================

Building custom iPXE image
--------------------------

In fedora:

  1. `yumdownloader --source ipx`
  2. `rpm -i ipxe*.src.rpm`
  3. `cp examples/custom-ipxe-build/SOURCES/script0.ipxe ~/rpmbuild/SOURCES/`
  4. `(cd ~/rpmbuild/SPEC; patch) < examples/custom-ipxe-build/SPEC/ipxe.spec.patch`
  5. `rpmbuild -bs ~/rpmbuild/SPEC/ipxe.spec`
  6. `mock ~/rpmbuild/SRPMS/ipxe-*.src.rpm`
  7. Get ipxe.iso from resulting rpm package.

Setting up for Croc Cloud
-------------------------

  1. Get your *c2rc file* from the web console 
  3. Build custom iPXE iso (see above).
  4. Source rc file into current shell.
  5. Upload custom iPXE iso file to c2fs. You can use command "guesti c2 upload_loader" or web UI. Please note snapshot ID.
  6. Specify ID of install loader snapshot. You can add them to your rc file for convinience: `export IPXE_SNAPSHOT_ID=snap-1F3FXXXX`.
  7. Run one of the example launcher, like `guesti-os-install-centos-6`. See if it will succeed with the installation.
  8. Run other tested examples for CrocCloud (e.g. `guesti-c2-*`) to create images for Debian, Fedora and so on.
  9. Customize examples or make your own scripted install in the cloud using *guesti*.

Setting up for OpenStack cloud
------------------------------

  1. Get your *OpenStack RC File* from the web console 
  2. Add `export OS_IMAGE_URL={your-glance-api-endpoint}` to rc file.
  3. Build custom iPXE iso. (see above).
  4. Source rc file into current shell.
  5. Upload custom iPXE iso file. You can use command "guesti os upload_loader" or web UI.
  6. Specify IDs of install loader image, install flavor and install network. You can add them to your rc file for convinience:

    export INSTALL_NETWORK_ID=bf083625-07b6-4d72-97a4-845d63945aa7
    export INSTALL_FLAVOR_ID=c9f81043-ca2e-4fab-b5b9-c4380e0beb3a
    export IPXE_IMAGE_ID=0cea4ad5-accf-4d1e-b0db-f3de0e6ceff6

  7. Run one of the example launcher, like `guesti-os-install-centos-6`. See if it succeed with the installation.
  8. Run other tested examples for OpenStack (e.g. `guesti-os-*`) to create images for Debian, Fedora and so on.
  9. Customize examples or make your own scripted install in the cloud using *guesti*.


Installing
==========

Requirements
------------

  - boto
  - novaclient
  - glanceclient
  - keystoneclient

Get source
----------

    git clone git://github.com/YKonovalov/guesti
    cd guesti

Build
-----

You can build and install guesti with setuptools:

    python setup.py install

Or build RPM package:

    make srpm
    mock {src.rpm file}
    yum install {noarch.rpm file}

Portability
-----------

This library tested on Linux. Should work on UNIXes as well once
you'll have all dependencies in place.

More info
=========

Please file bug reports at https://github.com/YKonovalov/guesti

License
=======

**GPLv3+**
Copyright © 2013  Yury Konovalov <YKonovalov@gmail.com>
