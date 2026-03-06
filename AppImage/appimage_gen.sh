#!/bin/bash

check_dep()
{
  DEP=$1
  if [ -z $(which $DEP) ] ; then
    echo "Error : $DEP command not found"
    exit 1
  fi
}

check_dep appimagetool
check_dep linuxdeploy
check_dep pyuic5
check_dep pyinstaller


#ARCH=`dpkg --print-architecture`
#MULTIARCH=`gcc -dumpmachine`

# enables running this script from different directory
AppDirParent="$(readlink -f "$(dirname "$0")")"
cd "$AppDirParent"

# generate resource and ui files
pyrcc5 -o ../gospel_pdf/resources_rc.py ../data/resources.qrc
pyuic5 -o ../gospel_pdf/ui_mainwindow.py ../data/mainwindow.ui
# run pyinstaller
pyinstaller ../Windows/gospel_pdf.spec
rm -r build


mkdir -p AppDir/usr/bin
mkdir -p AppDir/usr/lib
mkdir -p AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/scalable/apps
mkdir -p AppDir/usr/share/metainfo

cd AppDir

APPDIR=`pwd`

# copy executable and desktop file
cp ../../data/gospel-pdf.desktop usr/share/applications/io.github.ksharindam.gospel-pdf.desktop
cp ../../data/io.github.ksharindam.gospel-pdf.metainfo.xml usr/share/metainfo
cp ../AppRun .

# copy pyinstaller generated files
cp -r ../dist/gospel_pdf usr/lib

# remove excess library files
# NOTE : from ubuntu 22 PyQt5/Qt/ must be replaced with PyQt5/Qt5/
rm -r usr/lib/gospel_pdf/_internal/lib*.so.*
rm -r usr/lib/gospel_pdf/_internal/PyQt5/Qt/plugins/*
rm -r usr/lib/gospel_pdf/_internal/PyQt5/Qt/translations
# copy some required files we deleted earlier
cp ../dist/gospel_pdf/_internal/libpython* usr/lib/gospel_pdf/_internal
# ------- copy Qt5 Plugins ---------
QT_PLUGIN_PATH=${APPDIR}/usr/lib/gospel_pdf/_internal/PyQt5/Qt/plugins
QT_PLUGIN_SRC=${APPDIR}/../dist/gospel_pdf/_internal/PyQt5/Qt/plugins
# this is most necessary plugin for x11 support. without it application won't launch
mkdir -p ${QT_PLUGIN_PATH}/platforms
cp ${QT_PLUGIN_SRC}/platforms/libqxcb.so ${QT_PLUGIN_PATH}/platforms

# save as jpeg support
mkdir -p ${QT_PLUGIN_PATH}/imageformats
cp ${QT_PLUGIN_SRC}/imageformats/libqjpeg.so ${QT_PLUGIN_PATH}/imageformats

# Wayland support
#cp ${QT_PLUGIN_SRC}/platforms/libqwayland-generic.so ${QT_PLUGIN_PATH}/platforms
#cp -r ${QT_PLUGIN_SRC}/wayland-shell-integration ${QT_PLUGIN_PATH}
#cp -r ${QT_PLUGIN_SRC}/wayland-graphics-integration-client ${QT_PLUGIN_PATH}

# using Fusion theme does not require bundling any style plugin


# ----- End of Copy Qt5 Plugins ------

#cp /usr/lib/${MULTIARCH}/libssl.so.1.0.2 usr/lib
#cp /usr/lib/${MULTIARCH}/libcrypto.so.1.0.2 usr/lib

# cleanup
rm -r ${APPDIR}/../dist

# Deploy dependencies (--appimage-extract-and-run option is for docker)
linuxdeploy --appimage-extract-and-run --appdir .  --icon-file=../../data/gospel-pdf.png

# compile python bytecodes
#find usr/lib -iname '*.py' -exec python3 -m py_compile {} \;

# dump build info
#lsb_release -a > usr/share/BUILD_INFO
#ldd --version | grep GLIBC >> usr/share/BUILD_INFO
#python3 --version >> usr/share/BUILD_INFO

cd ..

# fixes firejail permission issue
chmod -R 0755 AppDir


#if [ "$MULTIARCH" = "x86_64-linux-gnu" ]; then
#    appimagetool -u "zsync|https://github.com/ksharindam/gospel_pdf/releases/latest/download/Gospel_Pdf-x86_64.AppImage.zsync" AppDir
appimagetool --appimage-extract-and-run AppDir

