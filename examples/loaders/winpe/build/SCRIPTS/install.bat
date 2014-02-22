wpeinit
wpeutil SetKeyboardLayout 0409:00000409
cd \virtio
drvload netkvm.inf
drvload viostor.inf
cd \
diskpart /s prepdisks.txt
net use z: \\37.9.127.33\dist
z:
cd w7
setup.exe
