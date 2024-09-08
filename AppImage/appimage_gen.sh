#!/bin/bash

check_dep()
{
  DEP=$1
  if [ -z $(which $DEP) ] ; then
    echo "Error : $DEP command not found"
    exit 0
  fi
}

check_dep appimagetool
check_dep linuxdeploy
check_dep gcc

MULTIARCH=`gcc -dumpmachine`
LIBDIR=lib/${MULTIARCH}
PYVERSION="3.7"

mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
mkdir -p AppDir/usr/share/metainfo

cd AppDir

APPDIR=`pwd`

# copy executable and desktop file
cp ../../data/gospel-pdf.desktop usr/share/applications/com.ksharindam.gospel-pdf.desktop
cp ../com.ksharindam.gospel-pdf.appdata.xml usr/share/metainfo
cp ../AppRun .
chmod +x AppRun

# create required directories
mkdir -p ${APPDIR}/usr/lib/python3.7
mkdir -p ${APPDIR}/usr/lib/python3/PyQt5

# copy main program
cp ../../gospel_pdf.py usr/bin/gospel_pdf
chmod +x usr/bin/gospel_pdf
cp -r ../../gospel_pdf usr/lib/python3
# copy python3 and python3-stdlib
cp /usr/bin/python3 usr/bin

cd /usr/lib/python3.7
cat ${APPDIR}/../python3.7-stdlib.txt | sed -e "s/x86_64-linux-gnu/${MULTIARCH}/" | xargs -I % cp -r --parents % ${APPDIR}/usr/lib/python3.7

# copy python modules
cd /usr/lib/python3/dist-packages

cp popplerqt5.* ${APPDIR}/usr/lib/python3

# copy sip module
cp sipconfig*.py sip.cpython*.so sip.pyi ${APPDIR}/usr/lib/python3



# copy PyQt5 module
cd PyQt5
cp Qt.* QtCore.* QtGui.* QtWidgets.* QtXml.* QtPrintSupport.* __init__.py \
   ${APPDIR}/usr/lib/python3/PyQt5

cd $APPDIR

# ------- copy Qt5 Plugins ---------
QT_PLUGIN_PATH=${APPDIR}/usr/lib/qt5/plugins
cd /usr/${LIBDIR}/qt5/plugins/

# this is most necessary plugin for x11 support. without it application won't launch
mkdir -p ${QT_PLUGIN_PATH}/platforms
cp platforms/libqxcb.so ${QT_PLUGIN_PATH}/platforms

# jpeg plugin for saving images
mkdir -p ${QT_PLUGIN_PATH}/imageformats
cp imageformats/libqjpeg.so ${QT_PLUGIN_PATH}/imageformats

# plugin for print support
mkdir -p ${QT_PLUGIN_PATH}/printsupport
cp printsupport/libcupsprintersupport.so ${QT_PLUGIN_PATH}/printsupport

# using Fusion theme does not require bundling any style plugin


cd $APPDIR
# ----- End of Copy Qt5 Plugins ------



# Deploy dependencies
linuxdeploy --appdir .  --icon-file=../../data/gospel-pdf.png

# compile python bytecodes
find usr/lib -iname '*.py' -exec python3 -m py_compile {} \;

cd ..

# fixes firejail permission issue
chmod -R 0755 AppDir


if [ "$MULTIARCH" = "x86_64-linux-gnu" ]; then
    appimagetool -u "zsync|https://github.com/ksharindam/gospel-pdf-viewer/releases/latest/download/Gospel_PDF-x86_64.AppImage.zsync" AppDir
else
    appimagetool AppDir
fi
