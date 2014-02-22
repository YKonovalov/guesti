WAIK_ISO_FILE ?= ../build/PREREQ/KB3AIK_RU.iso
VIRTIO_ISO_FILE ?= ../build/PREREQ/virtio-win-0.1-74.iso
EXTRA ?=../build/SCRIPTS
ALTWIM   ?= winpe-wmi-scripting-mdac-hta.wim

ARCH = amd64
#ARCH = x86
ARCHU := $(shell echo $(ARCH)|tr a-z A-Z)
ARCHP := $(shell echo $(ARCH)|tr -d [:digit:]'\n' |wc -c)

CABS_MATCH   = WinPE.cab wAIK$(ARCHU).msi Neutral.cab WinPE_LangPacks/$(ARCH)/en-us/winpe-wmi_en-us.cab

FILES_WAIK  = f_winpe_$(ARCH)_etfsboot.com f$(ARCHP)_bootmgr f_winpe_$(ARCH)_bcd f_winpe_$(ARCH)_boot.sdi
FILES_WPE   = f$(ARCHP)_winpe.wim
FILES_ISO   = etfsboot.com bootmgr boot/bcd boot/boot.sdi sources/boot.wim
FILES_WMI   = f_winpeoc_$(ARCH)__winpe_winpe_wmi.cab winpe-wmi_en-us.cab

CABS_ORIG   := $(shell echo $(CABS_MATCH) | sed -e "s;[^[:blank:]]\+/;;g")
CABS_FILES  := $(shell echo $(CABS_ORIG) | tr A-Z a-z)
TOPCABS      = $(CABS_FILES:%=topcabs/%)

CACHE_WAIK   = $(shell echo $(FILES_WAIK:%=cache/%))
CACHE_WPE    = $(FILES_WPE:%=cache/%)
CACHE        = $(CACHE_WAIK) $(CACHE_WPE)

PACK_WMI     = $(FILES_WMI:%=packs/%)
PACKS        = $(PACK_WMI)

ISO_CONTENT  = $(FILES_ISO:%=iso/%)

ISO  = winpe$(ARCH).iso
ISOA = winpe$(ARCH)_alt.iso
HDDP = winpe_$(ARCH).hddpart
HDD  = winpe_$(ARCH).hdd

ifeq ($(wildcard altwim/$(ALTWIM)),)
	WIM=cache/f$(ARCHP)_winpe.wim
else
	WIM = altwim/$(ALTWIM)
endif

all: $(ISO)

#$(WAIK_ISO_FILE):
#	$(get_waik) $(WAIK_ISO_FILE)

$(CABS_ORIG):
	7z e $(WAIK_ISO_FILE) $(CABS_MATCH)

$(ISOA): $(CABS_ORIG) extra
	mkwinpeimg --iso --waik-dir=./ --overlay=extra $(@)

$(TOPCABS): $(CABS_ORIG)
	mkdir -p topcabs
	for f in $(CABS_ORIG); do cp -f $$f topcabs/$$(echo $$f|tr A-Z a-z); done

$(CACHE_WAIK): topcabs/waik$(ARCH).msi
	cabextract -d cache --lowercase -F $(@:cache/%=%) $<
	touch $(@)

$(CACHE_WPE): topcabs/winpe.cab
	cabextract -d cache --lowercase -F $(@:cache/%=%) $<
	touch $(@)

packs/winpe-wmi_en-us.cab:
	cp -f topcabs/winpe-wmi_en-us.cab $(@)

$(PACK_WMI): topcabs/neutral.cab
	cabextract -d packs --lowercase -F $(@:packs/%=%) $<
	touch $(@)

$(ISO_CONTENT): $(CACHE)
	mkdir -p -- iso/boot iso/sources
	install cache/f_winpe_$(ARCH)_etfsboot.com iso/etfsboot.com
	install cache/f$(ARCHP)_bootmgr                   iso/bootmgr
	install cache/f_winpe_$(ARCH)_bcd          iso/boot/bcd
	install cache/f_winpe_$(ARCH)_boot.sdi     iso/boot/boot.sdi
	install $(WIM)                             iso/sources/boot.wim
#	install cache/f$(ARCHP)_winpe.wim                 iso/sources/boot.wim

extra:
	mkdir -p extra/VirtIO
	7z e -oextra/VirtIO $(VIRTIO_ISO_FILE) 'WIN7/$(ARCHU)/*.*'
	rsync -a $(EXTRA)/ extra/

iso/extra: extra
	mkdir -p -- iso/extra
	mkdir -p -- wim
	wimlib-imagex mountrw iso/sources/boot.wim wim
	cp -r extra/* wim/
	sleep 3
	wimlib-imagex unmount --commit wim
	rmdir wim


$(ISO): $(ISO_CONTENT) iso/extra
	genisoimage -sysid "" -A "" -V "Microsoft Windows PE ($(ARCH))" -d -N -b etfsboot.com -no-emul-boot \
	 -c boot.cat -hide etfsboot.com -hide boot.cat -o $(ISO) iso

$(HDDP): $(ISO_CONTENT)
	#dd if=/dev/zero of=$(HDDP) count=264000
	dd if=/dev/zero of=$(HDDP) count=2264000
	/sbin/mkfs.vfat -F32 $(HDDP)
	grep "mtools_skip_check=1" ~/.mtoolsrc >/dev/null || echo "mtools_skip_check=1" >> ~/.mtoolsrc
	mmd -i $(HDDP) boot
	mmd -i $(HDDP) sources
	mcopy -i $(HDDP) iso/bootmgr ::/bootmgr
	mcopy -i $(HDDP) iso/boot/bcd ::/boot/bcd
	mcopy -i $(HDDP) iso/boot/boot.sdi ::/boot/boot.sdi
	mcopy -i $(HDDP) iso/sources/boot.wim ::/sources/boot.wim
	mcopy -i $(HDDP) /usr/share/syslinux/chain.c32 ::/chain.c32
	mcopy -i $(HDDP) syslinux.cfg ::/syslinux.cfg
	syslinux $(HDDP)

$(HDD): $(HDDP)
	dd if=/dev/zero of=$(HDD) count=2264032
	parted $(HDD) --script -- mklabel msdos
	parted $(HDD) --script -- mkpart primary fat32 0 -1
	parted $(HDD) --script -- set 1 boot on
	parted $(HDD) --script -- print
	dd if=$(HDDP) of=$(HDD) seek=32
#dd if=/usr/share/syslinux/mbr.bin of=$(HDD) bs=446 count=1 conv=notrunc

install: $(ISO)
	sudo cp /usr/share/syslinux/memdisk /boot/
	sudo cp $(ISO) /boot/winpe.iso
	sudo grep 'menuentry \"Windows PE BIOS Update\"' /etc/grub.d/40_custom || cat grub2-menu.cfg|sudo tee -a /etc/grub.d/40_custom
	sudo grep 'menuentry \"Windows PE BIOS Update\"' /boot/grub2/grub.cfg || sudo grub2-mkconfig -o /boot/grub2/grub.cfg

clean:
	rm -rf iso cache packs extra
	rm -f $(ISO) $(ISOA) $(HDD) $(HDDP)

dist-clean: clean
	rm -rf topcabs
	rm -f $(CABS_ORIG)
