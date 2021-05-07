# -*- coding: utf-8 -*-
"""
Name = Gospel PDF Viewer
Executable Command = gospel-pdf
Package Name = gospel-pdf
Python Module Name = gospel_pdf
Debian Dependency = python3-pyqt5, python3-poppler-qt5

Description = A poppler based PDF viewer written in PyQt
Changes :
2.0.0   initial port to python3 pyqt5
2.0.1   print support with quikprint program
2.0.2   fixed : search highlight persisted on some cases
2.0.3   added : document info button in toolbar
2.0.4   fixed : error due to no default widow geometry
2.0.5   fixed : crashes after inputing password
2.0.6   added : statusbar to show hyperlink url
2.0.7   added : jump to exact position
2.0.8   fixed : page not rendered when jump to top=1.0
2.0.9   fixed : crash for info dialog for pdf with wrong date format
2.0.10  fixed : cropped few pixels at the borders
2.0.11  encrypt and decrypt pdf using qpdf program
2.0.12  show an icon if pdf has attached file

...........................................................................
|   Copyright (C) 2017-2021 Arindam Chaudhuri <ksharindam@gmail.com>       |
|                                                                          |
|   This program is free software: you can redistribute it and/or modify   |
|   it under the terms of the GNU General Public License as published by   |
|   the Free Software Foundation, either version 3 of the License, or      |
|   (at your option) any later version.                                    |
|                                                                          |
|   This program is distributed in the hope that it will be useful,        |
|   but WITHOUT ANY WARRANTY; without even the implied warranty of         |
|   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the          |
|   GNU General Public License for more details.                           |
|                                                                          |
|   You should have received a copy of the GNU General Public License      |
|   along with this program.  If not, see <http://www.gnu.org/licenses/>.  |
...........................................................................
"""
# TODO:
#       Show fonts list
#       resize pages when dock is hidden
# FIXME :
#       Search is not cancelled immediately, when cancel is pressed
#

__version__ = '2.0.12'
