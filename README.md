GuestI
======
GuestI (Guest Installer) is a cloud machine image build automation tool.
The main idea is to facilate the fact that majority of operating systems
nowdays have their distribution and installer on the internet. So, to
create a machine template all we need - is to boot and perform a scripted
install of a selected OS directly from the internet. Cloud supported:
 -C2 - Croc Cloud platform

To boot a guest of the internet this tool needs iPXE loader, specifically
configured to read boot commands from the cloud metadata URL.

Requirements
------------

  - boto

Get source
----------

::

  git clone git://github.com/YKonovalov/guesti
  cd guesti

Install
-------
You can build and install guesti with setuptools:

::

    python setup.py install

Or build RPM package:

::

    make srpm
    mock {src.rpm file}

Portability
-----------

This library tested on Linux. Should work on UNIXes as well once
you'll have all dependancies in place.

More info
---------

Please file bug reports at https://github.com/YKonovalov/guesti

License
-------

GPLv3+
Copyright © 2013  Yury Konovalov <YKonovalov@gmail.com>
