
# -*- coding: utf-8 -*-
import time
from email.utils import parsedate_tz, mktime_tz

from PyQt5 import QtCore
from PyQt5.QtGui import QIcon, QIntValidator
from PyQt5.QtWidgets import ( QDialog, QDialogButtonBox, QGridLayout, QLineEdit, QSpinBox,
    QLabel, QVBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
)

class ExportToImageDialog(QDialog):
    def __init__(self, page_no, total_pages, parent):
        QDialog.__init__(self, parent)
        self.setWindowTitle('Export Page to Image')
        self.resize(300, 140)
        layout = QGridLayout(self)
        dpiLabel = QLabel('DPI :', self)
        self.dpiEdit = QLineEdit("300", self)
        self.dpiEdit.setAlignment(QtCore.Qt.AlignHCenter)
        self.dpiEdit.setValidator(QIntValidator(75, 1200, self))
        pageNoLabel = QLabel('Page No. :', self)
        self.pageNoSpin = QSpinBox(self)
        self.pageNoSpin.setAlignment(QtCore.Qt.AlignHCenter)
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.setStandardButtons(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        layout.addWidget(dpiLabel, 0,0,1,1)
        layout.addWidget(self.dpiEdit, 0,1,1,1)
        layout.addWidget(pageNoLabel, 1,0,1,1)
        layout.addWidget(self.pageNoSpin, 1,1,1,1)
        layout.addWidget(self.buttonBox, 2, 0, 1, 2)

        # set values
        self.pageNoSpin.setRange(1, total_pages)
        self.pageNoSpin.setValue(page_no)
        # connect signals
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)


class DocInfoDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        self.resize(560, 320)
        self.tableWidget = QTableWidget(0, 2, self)
        vLayout = QVBoxLayout(self)
        vLayout.addWidget(self.tableWidget)
        self.tableWidget.setAlternatingRowColors(True)
        closeBtn = QPushButton(QIcon(':/quit.png'), "Close", self)
        closeBtn.setMaximumWidth(120)
        vLayout.addWidget(closeBtn, 0, QtCore.Qt.AlignRight)
        closeBtn.clicked.connect(self.accept)
        self.tableWidget.horizontalHeader().setDefaultSectionSize(150)
        self.tableWidget.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tableWidget.horizontalHeader().setVisible(False)
        self.tableWidget.verticalHeader().setVisible(False)

    def setInfo(self, info_keys, values):
        for i in range(len(info_keys)):
            if info_keys[i] in ['ModDate', 'CreationDate']:
                values[i] = parsePdfTime(values[i])
            self.tableWidget.insertRow(i)
            self.tableWidget.setItem(i,0, QTableWidgetItem(info_keys[i]))
            self.tableWidget.setItem(i,1, QTableWidgetItem(values[i]))

# Takes D:20130501200439+01'00' like format and returns a local timezone based format
# In some pdfs date does not start with D:
def parsePdfTime(t):
    t = t.replace('D:', '')
    try:
        ts = time.strptime(t[:14], "%Y%m%d%H%M%S")
    except:
        return t
    rfc2822 = time.strftime("%a, %d %b %Y %H:%M:%S "+t[-5:], ts) # to rfc2822 time format
    py_time = mktime_tz(parsedate_tz(rfc2822))
    return time.strftime("%d %b %Y at %I:%M:%S %p", time.localtime(py_time))


