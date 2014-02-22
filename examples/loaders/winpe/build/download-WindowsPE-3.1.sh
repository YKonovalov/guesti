#!/bin/bash

# Windows PE 3.1 (Based on Windows 7) provided by WAIK free of charge
URL="http://www.microsoft.com/ru-ru/download/details.aspx?id=5753"
echo "Requesting $URL"
RESPONSE="$(curl -f $URL 2>/dev/null)"

FILE_URL=$(echo "$RESPONSE"|tr -d '\r'|grep -i 'http://download[^"]*.iso'|sed -n 's;.*"\(http://download[^"]\+.iso\)".*;\1;p'|tr -d '[[:blank:]]'|head -1) #"
echo "ISO URL to download:	$FILE_URL"
FILE=${FILE_URL##*/}
echo $FILE |grep "^[[:alnum:]_]\+\.iso$" >/dev/null || (echo "Bad filename $FILE"; exit 1)
echo "Downloading $FILE"
curl --progress-bar -o "$FILE" "$FILE_URL" || (echo "Download failed"; exit 2)
