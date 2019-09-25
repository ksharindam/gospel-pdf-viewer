#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, os
from subprocess import Popen
from PyQt5 import QtCore
from PyQt5.QtGui import ( QPainter, QColor, QPixmap, QImage, QIcon, QStandardItem,
    QIntValidator, QStandardItemModel
)
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QLabel,
    QFileDialog, QInputDialog, QAction, QLineEdit,
    QComboBox, QMessageBox,
    QDialog
)
#from PyQt4.QtGui import QDesktopServices
from popplerqt5 import Poppler
sys.path.append(os.path.dirname(__file__)) # for enabling python 2 like import

import resources_rc
from __init__ import __version__
from ui_mainwindow import Ui_window
from dialogs import ExportToImageDialog, DocInfoDialog

DEBUG = False
def debug(*args):
    if DEBUG: print(*args)

SCREEN_DPI = 100
HOMEDIR = os.path.expanduser("~")

#def pt2pixel(point, dpi):
#    return dpi*point/72.0

class Renderer(QtCore.QObject):
    rendered = QtCore.pyqtSignal(int, QImage)
    textFound = QtCore.pyqtSignal(int, list)

    def __init__(self, render_even_pages=True):
        QtCore.QObject.__init__(self)
        self.doc = None
        self.render_even_pages = render_even_pages
        self.painter = QPainter()
        self.link_color = QColor(0,0,127, 40)

    def render(self, page_no, dpi):
        """ render(int, float)
        This slot takes page no. and dpi and renders that page, then emits a signal with QImage"""
        # Returns when both is true or both is false
        if not ((page_no%2==0 and self.render_even_pages) or (page_no%2!=0 and self.render_even_pages==False)):
            return
        page = self.doc.page(page_no)
        if not page : return
        img = page.renderToImage(dpi, dpi)
        # Add Heighlight over Link Annotation
        self.painter.begin(img)
        annots = page.annotations()
        for annot in annots:
          if annot.subType() == Poppler.Annotation.ALink:
            x, y = annot.boundary().left()*img.width(), annot.boundary().top()*img.height()
            w, h = annot.boundary().width()*img.width()+1, annot.boundary().height()*img.height()+1
            self.painter.fillRect(x, y, w, h, self.link_color)
        self.painter.end()
        self.rendered.emit(page_no, img)

    def loadDocument(self, filename, password=''):
        """ loadDocument(str)
        Main thread uses this slot to load document for rendering """
        self.doc = Poppler.Document.load(filename, password.encode(), password.encode())
        self.doc.setRenderHint(Poppler.Document.TextAntialiasing | Poppler.Document.TextHinting |
                               Poppler.Document.Antialiasing | 0x00000020 )

    def findText(self, text, page_num, find_reverse):
        if find_reverse:
            pages = [i for i in range(page_num+1)]
            pages.reverse()
        else:
            pages = range(page_num, self.doc.numPages())
        for page_no in pages:
            page = self.doc.page(page_no)
            textareas = page.search(text,Poppler.Page.CaseInsensitive,0)
            if textareas != []:
                self.textFound.emit(page_no, textareas)
                break


class Frame(QFrame):
    def __init__(self, parent, scrollArea):
        QFrame.__init__(self, parent)
        self.vScrollbar = scrollArea.verticalScrollBar()
        self.hScrollbar = scrollArea.horizontalScrollBar()
        self.setMouseTracking(True)
        self.clicked = False

    def mousePressEvent(self, ev):
        self.click_pos = ev.globalPos()
        self.v_scrollbar_pos = self.vScrollbar.value()
        self.h_scrollbar_pos = self.hScrollbar.value()
        self.clicked = True

    def mouseReleaseEvent(self, ev):
        self.clicked = False

    def mouseMoveEvent(self, ev):
        if not self.clicked : return
        self.vScrollbar.setValue(self.v_scrollbar_pos + self.click_pos.y() - ev.globalY())
        self.hScrollbar.setValue(self.h_scrollbar_pos + self.click_pos.x() - ev.globalX())


class Main(QMainWindow, Ui_window):
    renderRequested = QtCore.pyqtSignal(int, float)
    loadFileRequested = QtCore.pyqtSignal(str, str)
    findTextRequested = QtCore.pyqtSignal(str, int, bool)

    def __init__(self, parent=None):
        super(Main, self).__init__(parent)
        self.setupUi(self)
        self.dockSearch.hide()
        self.dockWidget.hide()
        self.dockWidget.setMinimumWidth(310)
        self.findTextEdit.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.treeView.setAlternatingRowColors(True)
        self.treeView.clicked.connect(self.onOutlineClick)
        self.first_document = True
        desktop = QApplication.desktop()
        self.resize_page_timer = QtCore.QTimer(self)
        self.resize_page_timer.setSingleShot(True)
        self.resize_page_timer.timeout.connect(self.onWindowResize)
        # Add shortcut actions
        self.gotoPageAction = QAction(QIcon(":/goto.png"), "GoTo Page", self)
        self.gotoPageAction.triggered.connect(self.gotoPage)
        self.copyTextAction = QAction(QIcon(":/copy.png"), "Copy Text", self)
        self.copyTextAction.setCheckable(True)
        self.copyTextAction.triggered.connect(self.toggleCopyText)
        self.findTextAction = QAction(QIcon(":/search.png"), "Find Text", self)
        self.findTextAction.setShortcut('Ctrl+F')
        self.findTextAction.triggered.connect(self.dockSearch.show)
        # connect menu actions signals
        self.openFileAction.triggered.connect(self.openFile)
        self.printAction.triggered.connect(self.printFile)
        self.quitAction.triggered.connect(self.close)
        self.toPSAction.triggered.connect(self.exportToPS)
        self.pageToImageAction.triggered.connect(self.exportPageToImage)
        self.docInfoAction.triggered.connect(self.docInfo)
        self.zoominAction.triggered.connect(self.zoomIn)
        self.zoomoutAction.triggered.connect(self.zoomOut)
        self.undoJumpAction.triggered.connect(self.undoJump)
        self.prevPageAction.triggered.connect(self.goPrevPage)
        self.nextPageAction.triggered.connect(self.goNextPage)
        self.firstPageAction.triggered.connect(self.goFirstPage)
        self.lastPageAction.triggered.connect(self.goLastPage)
        # Create widgets for menubar / toolbar
        self.gotoPageEdit = QLineEdit(self)
        self.gotoPageEdit.setPlaceholderText("Jump to page...")
        self.gotoPageEdit.setMaximumWidth(120)
        self.gotoPageEdit.returnPressed.connect(self.gotoPage)
        self.gotoPageValidator = QIntValidator(1,1, self.gotoPageEdit)
        self.gotoPageEdit.setValidator(self.gotoPageValidator)
        self.pageNoLabel = QLabel(self)
        self.pageNoLabel.setFrameShape(QFrame.StyledPanel)
        spacer = QWidget(self)
        spacer.setSizePolicy(1|2|4,1|4)
        self.zoomLevelCombo = QComboBox(self)
        self.zoomLevelCombo.addItems(["Fixed Width", "75%", "90%","100%","110%","121%","133%","146%", "175%", "200%"])
        self.zoomLevelCombo.activated.connect(self.setZoom)
        self.zoom_levels = [0, 75, 90, 100, 110 , 121, 133, 146, 175, 200]
        # Add toolbar actions
        self.toolBar.addAction(self.openFileAction)
        self.toolBar.addAction(self.printAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.docInfoAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.zoomoutAction)
        self.toolBar.addWidget(self.zoomLevelCombo)
        self.toolBar.addAction(self.zoominAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.firstPageAction)
        self.toolBar.addAction(self.prevPageAction)
        self.toolBar.addWidget(self.pageNoLabel)
        self.toolBar.addAction(self.nextPageAction)
        self.toolBar.addAction(self.lastPageAction)
        self.toolBar.addAction(self.undoJumpAction)
        self.toolBar.addWidget(self.gotoPageEdit)
        self.toolBar.addAction(self.gotoPageAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.copyTextAction)
        self.toolBar.addAction(self.findTextAction)
        self.toolBar.addWidget(spacer)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.quitAction)
        # Add widgets
        # Impoort settings
        self.settings = QtCore.QSettings("gospel-pdf", "main", self)
        self.recent_files = self.settings.value("RecentFiles", [])
        self.history_filenames = self.settings.value("HistoryFileNameList", [])
        self.history_page_no = self.settings.value("HistoryPageNoList", [])
        self.offset_x = int(self.settings.value("OffsetX", 4))
        self.offset_y = int(self.settings.value("OffsetY", 26))
        self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        self.zoomLevelCombo.setCurrentIndex(int(self.settings.value("ZoomLevel", 2)))
        # Connect Signals
        self.scrollArea.verticalScrollBar().valueChanged.connect(self.onMouseScroll)
        self.scrollArea.verticalScrollBar().sliderReleased.connect(self.onSliderRelease)
        self.findTextEdit.returnPressed.connect(self.findNext)
        self.findNextButton.clicked.connect(self.findNext)
        self.findBackButton.clicked.connect(self.findBack)
        self.findCloseButton.clicked.connect(self.dockSearch.hide)
        self.dockSearch.visibilityChanged.connect(self.toggleFindMode)
        # Create separate thread and move renderer to it
        self.thread1 = QtCore.QThread(self)
        self.renderer1 = Renderer()
        self.renderer1.moveToThread(self.thread1) # this must be moved before connecting signals
        self.renderRequested.connect(self.renderer1.render)
        self.loadFileRequested.connect(self.renderer1.loadDocument)
        self.findTextRequested.connect(self.renderer1.findText)
        self.renderer1.rendered.connect(self.setRenderedImage)
        self.renderer1.textFound.connect(self.onTextFound)
        self.thread1.start()
        self.thread2 = QtCore.QThread(self)
        self.renderer2 = Renderer(False)
        self.renderer2.moveToThread(self.thread2)
        self.renderRequested.connect(self.renderer2.render)
        self.loadFileRequested.connect(self.renderer2.loadDocument)
        self.renderer2.rendered.connect(self.setRenderedImage)
        self.thread2.start()
        # Initialize Variables
        self.filename = ''
        self.current_page = 0
        self.pages = []
        self.jumped_from = None
        self.max_preload = 1
        self.recent_files_actions = []
        self.addRecentFiles()
        # Show Window
        width = int(self.settings.value("WindowWidth", 1040))
        height = int(self.settings.value("WindowHeight", 717))
        self.resize(width, height)
        self.show()

    def addRecentFiles(self):
        self.recent_files_actions[:] = []
        self.menuRecentFiles.clear()
        for each in self.recent_files:
            name = elideMiddle(os.path.basename(each), 60)
            action = self.menuRecentFiles.addAction(name, self.openRecentFile)
            self.recent_files_actions.append(action)
        self.menuRecentFiles.addSeparator()
        self.menuRecentFiles.addAction(QIcon(':/edit-clear.png'), 'Clear Recents', self.clearRecents)

    def openRecentFile(self):
        action = self.sender()
        index = self.recent_files_actions.index(action)
        self.loadPDFfile(self.recent_files[index])

    def clearRecents(self):
        self.recent_files_actions[:] = []
        self.menuRecentFiles.clear()
        self.recent_files[:] = []

    def removeOldDoc(self):
        # Save current page number
        self.saveFileData()
        # Remove old document
        for i in range(len(self.pages)):
            self.verticalLayout.removeWidget(self.pages[-1])
        for i in range(len(self.pages)):
            self.pages.pop().deleteLater()
        self.frame.deleteLater()
        self.jumped_from = None
        self.addRecentFiles()

    def loadPDFfile(self, filename):
        """ Loads pdf document in all threads """
        filename = os.path.expanduser(filename)
        self.doc = Poppler.Document.load(filename)
        if not self.doc : return
        password = ''
        if self.doc.isLocked() :
            password = QInputDialog.getText(self, 'This PDF is locked', 'Enter Password :', 2)[0].toUtf8()
            if password == '' : sys.exit(1)
            self.doc.unlock(password.encode(), password.encode())
        if not self.first_document:
            self.removeOldDoc()
        self.doc.setRenderHint(Poppler.Document.TextAntialiasing | Poppler.Document.TextHinting |
                               Poppler.Document.Antialiasing | 0x00000020 )
        self.filename = filename
        self.total_pages = self.doc.numPages()
        self.rendered_pages = []
        self.first_document = False
        self.getOutlines(self.doc)
        # Load Document in other threads
        self.loadFileRequested.emit(self.filename, password)
        if collapseUser(self.filename) in self.history_filenames:
            self.current_page = int(self.history_page_no[self.history_filenames.index(collapseUser(self.filename))])
        self.current_page = min(self.current_page, self.total_pages-1)
        self.scroll_render_lock = False
        # Add widgets
        self.frame = Frame(self.scrollAreaWidgetContents, self.scrollArea)
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame)
        self.horizontalLayout_2.addWidget(self.frame)
        self.scrollArea.verticalScrollBar().setValue(0)

        # Render 4 pages, (Preload 3 pages)
        self.max_preload = 4 if (self.total_pages > 4) else self.total_pages
        # Add pages
        for i in range(self.total_pages):
            page = PageWidget(self.frame)
            self.verticalLayout.addWidget(page, 0, QtCore.Qt.AlignCenter)
            self.pages.append(page)
        self.resizePages()
        self.pageNoLabel.setText('<b>%i/%i</b>' % (self.current_page+1, self.total_pages) )
        self.gotoPageValidator.setTop(self.total_pages)
        self.setWindowTitle(os.path.basename(self.filename)+ " - Gospel PDF " + __version__)
        if self.current_page != 0 : QtCore.QTimer.singleShot(500, self.jumpToCurrentPage)

    def setRenderedImage(self, page_no, image):
        """ takes a QImage and sets pixmap of the specified page
            when number of rendered pages exceeds a certain number, old page image is
            deleted to save memory """
        debug("Set Rendered Image :", page_no)
        self.pages[page_no].setPageData(page_no, QPixmap.fromImage(image), self.doc.page(page_no))
        self.pages[page_no].jumpToRequested.connect(self.jumpToPage)
        # Request to render next page
        if self.current_page < page_no < (self.current_page + self.max_preload - 2):
            if (page_no+2 not in self.rendered_pages) and (page_no+2 < self.total_pages):
              self.rendered_pages.append(page_no+2)
              self.renderRequested.emit(page_no+2, self.pages[page_no+2].dpi)
        # Replace old rendered pages with blank image
        if len(self.rendered_pages)>10:
            cleared_page_no = self.rendered_pages.pop(0)
            debug("Clear Page :", cleared_page_no)
            self.pages[cleared_page_no].clear()
            self.pages[cleared_page_no].jumpToRequested.disconnect(self.jumpToPage)
        debug("Rendered Pages :", self.rendered_pages)

    def renderCurrentPage(self):
        """ Requests to render current page. if it is already rendered, then request
            to render next unrendered page """
        requested = 0
        for page_no in range(self.current_page, self.current_page+self.max_preload):
            if (page_no not in self.rendered_pages) and (page_no < self.total_pages):
                self.rendered_pages.append(page_no)
                self.renderRequested.emit(page_no, self.pages[page_no].dpi)
                requested += 1
                debug("Render Requested :", page_no)
                if requested == 2: return

    def onMouseScroll(self, pos):
        """ Gets the current page number on scrolling, then requests to render"""
        index = self.verticalLayout.indexOf(self.frame.childAt(self.frame.width()/2, pos))
        if index == -1: return
        self.pageNoLabel.setText('<b>%i/%i</b>' % (index+1, self.total_pages) )
        if self.scrollArea.verticalScrollBar().isSliderDown() or self.scroll_render_lock : return
        self.current_page = index
        self.renderCurrentPage()

    def onSliderRelease(self):
        self.onMouseScroll(self.scrollArea.verticalScrollBar().value())

    def openFile(self):
        filename, sel_filter = QFileDialog.getOpenFileName(self,
                                      "Select Document to Open", "",
                                      "Portable Document Format (*.pdf);;All Files (*)" )
        if not filename=="":
            self.loadPDFfile(filename)

    def printFile(self):
        Popen(["quikprint", self.filename])

    def exportToPS(self):
        width = self.doc.page(self.current_page).pageSizeF().width()
        height = self.doc.page(self.current_page).pageSizeF().height()
        filename = QFileDialog.getSaveFileName(self, "Select File to Save",
                                       os.path.splitext(self.filename)[0]+'.ps',
                                      "Adobe Postscript Format (*.ps)" )
        if filename == '' : return
        conv = self.doc.psConverter()
        conv.setPaperWidth(width)
        conv.setPaperHeight(height)
        conv.setOutputFileName(filename)
        conv.setPageList([i+1 for i in range(self.total_pages)])
        ok = conv.convert()
        if ok:
            QMessageBox.information(self, "Successful !","File has been successfully exported")
        else:
            QMessageBox.warning(self, "Failed !","Failed to export to Postscript")

    def exportPageToImage(self):
        dialog = ExportToImageDialog(self.current_page, self.total_pages, self)
        if dialog.exec_() == QDialog.Accepted:
            try:
                dpi = int(dialog.dpiEdit.text())
                page_no = dialog.pageNoSpin.value()
                filename = os.path.splitext(self.filename)[0]+'-'+str(page_no)+'.jpg'
                page = self.doc.page(page_no-1)
                if not page : return
                img = page.renderToImage(dpi, dpi)
                img.save(filename)
                QMessageBox.information(self, "Successful !","Page has been successfully exported")
            except:
                QMessageBox.warning(self, "Failed !","Failed to export to Image")

    def docInfo(self):
        info_keys = list(self.doc.infoKeys())
        values = [self.doc.info(key) for key in info_keys]
        page_size = self.doc.page(self.current_page).pageSizeF()
        page_size = "%s x %s pts"%(page_size.width(), page_size.height())
        info_keys += ['Embedded FIles', 'Page Size']
        values += [str(self.doc.hasEmbeddedFiles()), page_size]
        dialog = DocInfoDialog(self)
        dialog.setInfo(info_keys, values)
        dialog.exec_()

    def jumpToCurrentPage(self):
        scrolbar_pos = self.pages[self.current_page].pos().y()
        self.scrollArea.verticalScrollBar().setValue(scrolbar_pos)

    def jumpToPage(self, page_no):
        """ gets the current page no from Main.current_page variable, then scrolls to that position """
        self.jumped_from = self.current_page
        self.current_page = page_no
        self.jumpToCurrentPage()

    def undoJump(self):
        if self.jumped_from == None: return
        self.jumpToPage(self.jumped_from)

    def goNextPage(self):
        if self.current_page == self.total_pages-1 : return
        self.current_page += 1
        self.jumpToCurrentPage()

    def goPrevPage(self):
        if self.current_page == 0 : return
        self.current_page -= 1
        self.jumpToCurrentPage()

    def goFirstPage(self):
        self.current_page = 0
        self.jumpToCurrentPage()

    def goLastPage(self):
        self.current_page = self.total_pages-1
        self.jumpToCurrentPage()

    def gotoPage(self):
        text = self.gotoPageEdit.text()
        if text=="" : return
        self.jumpToPage(int(text)-1)
        self.gotoPageEdit.clear()
        self.gotoPageEdit.clearFocus()

######################  Zoom and Size Management  ##########################

    def availableWidth(self):
        """ Returns available width for rendering a page """
        dock_width = 0 if self.dockWidget.isHidden() else self.dockWidget.width()
        return self.width() - dock_width - 50

    def resizePages(self):
        '''Resize all pages according to zoom level '''
        page_dpi = self.zoom_levels[self.zoomLevelCombo.currentIndex()]*SCREEN_DPI/100
        fixed_width = self.availableWidth()
        for i in range(self.total_pages):
            pg_width = self.doc.page(i).pageSizeF().width() # width in points
            pg_height = self.doc.page(i).pageSizeF().height()
            if self.zoomLevelCombo.currentIndex() == 0: # if fixed width
                dpi = 72.0*fixed_width/pg_width
            else: dpi = page_dpi
            self.pages[i].dpi = dpi
            self.pages[i].setFixedSize(pg_width*dpi/72.0, pg_height*dpi/72.0)
        for page_no in self.rendered_pages:
            self.pages[page_no].clear()
        self.rendered_pages = []
        self.renderCurrentPage()

    def setZoom(self, index):
        """ Gets called when zoom level is changed"""
        self.scroll_render_lock = True # rendering on scroll is locked as set scroll position
        self.resizePages()
        QtCore.QTimer.singleShot(300, self.afterZoom)

    def zoomIn(self):
        index = self.zoomLevelCombo.currentIndex()
        if index == len(self.zoom_levels) - 1 : return
        if index == 0 : index = 3
        self.zoomLevelCombo.setCurrentIndex(index+1)
        self.setZoom(index+1)

    def zoomOut(self):
        index = self.zoomLevelCombo.currentIndex()
        if index == 1 : return
        if index == 0: index = 4
        self.zoomLevelCombo.setCurrentIndex(index-1)
        self.setZoom(index-1)

    def afterZoom(self):
        scrolbar_pos = self.pages[self.current_page].pos().y()
        self.scrollArea.verticalScrollBar().setValue(scrolbar_pos)
        self.scroll_render_lock = False
#########            Search Text            #########
    def findNext(self, direction=1):
        text = self.findTextEdit.text()
        if text == "" : return
        # search from current page when text changed
        if self.search_text != text or self.search_page_no == -1:
            search_page_no = self.current_page
        else:
            search_page_no = self.search_page_no + 1
        self.findTextRequested.emit(text, search_page_no, False)
        if self.search_page_no != -1:     # clear previous highlights
            self.pages[self.search_page_no].highlight_area = None
            self.pages[self.search_page_no].updateImage()
            self.search_page_no = -1
        self.search_text = text

    def findBack(self):
        text = self.findTextEdit.text()
        if text == "" : return
        if self.search_text != text or self.search_page_no == -1:
            search_page_no = self.current_page
        else:
            search_page_no = self.search_page_no - 1
        self.findTextRequested.emit(text, search_page_no, True)
        if self.search_page_no != -1:
            self.pages[self.search_page_no].highlight_area = None
            self.pages[self.search_page_no].updateImage()
            self.search_page_no = -1
        self.search_text = text

    def onTextFound(self, page_no, areas):
        self.pages[page_no].highlight_area = areas
        self.search_page_no = page_no
        if self.pages[page_no].pixmap():
            self.pages[page_no].updateImage()
        else:
            self.rendered_pages.append(page_no)
            self.renderRequested.emit(page_no, self.pages[page_no].dpi)
        self.jumpToPage(page_no)

    def toggleFindMode(self, enable):
        if enable:
          self.findTextEdit.setText('')
          self.findTextEdit.setFocus()
          self.search_text = ''
          self.search_page_no = -1
        elif self.search_page_no!= -1:
          self.pages[self.search_page_no].highlight_area = None
          self.pages[self.search_page_no].updateImage()

#########      Cpoy Text to Clip Board      #########
    def toggleCopyText(self, checked):
        if checked:
            self.copy_text_pages = [self.current_page]
            if self.current_page+1 < self.total_pages: # add next page when current page is not last page
                self.copy_text_pages.append(self.current_page+1)
            for page_no in self.copy_text_pages:
                self.pages[page_no].copy_text_mode = True
                self.pages[page_no].copyTextRequested.connect(self.copyText)
        else:
            self.disableCopyText()

    def disableCopyText(self):
        for page_no in self.copy_text_pages:
            self.pages[page_no].copy_text_mode = False
            self.pages[page_no].copyTextRequested.disconnect(self.copyText)
        self.copy_text_pages = []
        self.copyTextAction.setChecked(False)

    def copyText(self, top_left, bottom_right):
        # Get page number and page zoom level
        page_no = self.pages.index(self.sender())
        zoom = float(self.pages[page_no].height())/float(self.doc.page(page_no).pageSize().height())
        # Copy text to clipboard
        text = self.doc.page(page_no).text(QtCore.QRectF(top_left/zoom, bottom_right/zoom))
        QApplication.clipboard().setText(text)
        self.disableCopyText()
#########      Cpoy Text to Clip Board      ##### ... end

    def getOutlines(self, doc):
        toc = doc.toc()
        if not toc:
            self.dockWidget.hide()
            return
        self.dockWidget.show()
        outline_model = QStandardItemModel(self)
        parent_item = outline_model.invisibleRootItem()
        node = toc.firstChild()
        loadOutline(doc, node, parent_item)
        self.treeView.setModel(outline_model)
        if parent_item.rowCount() < 4:
            self.treeView.expandToDepth(0)
        self.treeView.setHeaderHidden(True)
        self.treeView.header().setSectionResizeMode(0, 1)
        self.treeView.header().setSectionResizeMode(1, 3)
        self.treeView.header().setStretchLastSection(False)

    def onOutlineClick(self, m_index):
        page = self.treeView.model().data(m_index, QtCore.Qt.UserRole+1)
        if not page: return
        self.jumpToPage(page-1)

    def resizeEvent(self, ev):
        QMainWindow.resizeEvent(self, ev)
        if self.filename == '' : return
        if self.zoomLevelCombo.currentIndex() == 0:
            self.resize_page_timer.start(200)

    def onWindowResize(self):
        for i in range(self.total_pages):
            self.pages[i].annots_listed = False # Clears prev link annotation positions
        self.resizePages()
        wait(300)
        self.jumpToCurrentPage()
        if not self.isMaximized():
            self.settings.setValue("WindowWidth", self.width())
            self.settings.setValue("WindowHeight", self.height())

    def saveFileData(self):
        if self.filename != '':
            filename = collapseUser(self.filename)
            if filename in self.history_filenames:
                index = self.history_filenames.index(filename)
                self.history_page_no[index] = self.current_page
            else:
                self.history_filenames.insert(0, filename)
                self.history_page_no.insert(0, self.current_page)
            if filename in self.recent_files:
                self.recent_files.remove(filename)
            self.recent_files.insert(0, filename)

    def closeEvent(self, ev):
        """ Save all settings on window close """
        self.saveFileData()
        self.settings.setValue("OffsetX", self.geometry().x()-self.x())
        self.settings.setValue("OffsetY", self.geometry().y()-self.y())
        self.settings.setValue("ZoomLevel", self.zoomLevelCombo.currentIndex())
        self.settings.setValue("HistoryFileNameList", self.history_filenames[:100])
        self.settings.setValue("HistoryPageNoList", self.history_page_no[:100])
        self.settings.setValue("RecentFiles", self.recent_files[:10])
        return super(Main, self).closeEvent(ev)

    def onAppQuit(self):
        """ Close running threads """
        loop1 = QtCore.QEventLoop()
        loop2 = QtCore.QEventLoop()
        self.thread1.finished.connect(loop1.quit)
        self.thread2.finished.connect(loop2.quit)
        self.thread1.quit()
        loop1.exec_()
        self.thread2.quit()
        loop2.exec_()


def loadOutline(document, node, prnt_item):
    """void loadOutline(Poppler::Document* document, const QDomNode& node, QStandardItem* prnt_item) """
    element = node.toElement()
    item = QStandardItem(element.tagName())

    linkDestination = None
    if element.hasAttribute("Destination"):
        linkDestination = Poppler.LinkDestination(element.attribute("Destination"))
    elif element.hasAttribute("DestinationName"):
        linkDestination = document.linkDestination(element.attribute("DestinationName"))

    if linkDestination:
        page = linkDestination.pageNumber()
        if page < 1 : page = 1
        if page > document.numPages(): page = document.numPages()

        item.setData(page, QtCore.Qt.UserRole + 1)

        pageItem = item.clone()
        pageItem.setText(str(page))
        pageItem.setTextAlignment(QtCore.Qt.AlignRight)

        prnt_item.appendRow([item, pageItem])
    else:
        prnt_item.appendRow(item)

    # Load next sibling
    siblingNode = node.nextSibling()
    if not siblingNode.isNull():
        loadOutline(document, siblingNode, prnt_item)

    # Load its child
    childNode = node.firstChild()
    if not childNode.isNull():
        loadOutline(document, childNode, item)

class PageWidget(QLabel):
    jumpToRequested = QtCore.pyqtSignal(int)
    copyTextRequested = QtCore.pyqtSignal(QtCore.QPoint, QtCore.QPoint)

    def __init__(self, parent=None):
        QLabel.__init__(self, parent)
        self.setMouseTracking(True)
        self.setSizePolicy(0,0)
        self.setFrameShape(QFrame.StyledPanel)
        self.link_areas = []
        self.link_annots = []
        self.annots_listed, self.copy_text_mode, self.click_point, self.highlight_area = False, False, None, None
        self.image = QPixmap()

    def setPageData(self, page_no, pixmap, page):
        self.image = pixmap
        self.updateImage()
        if self.annots_listed : return
        annots = page.annotations()
        for annot in annots:
            if annot.subType() == Poppler.Annotation.ALink:
                x, y = annot.boundary().left()*pixmap.width(), annot.boundary().top()*pixmap.height()
                w, h = annot.boundary().width()*pixmap.width()+1, annot.boundary().height()*pixmap.height()+1
                self.link_areas.append(QtCore.QRectF(x,y, w, h))
                self.link_annots.append(annot)
        self.annots_listed = True

    def clear(self):
        QLabel.clear(self)
        self.image = QPixmap()

    def mouseMoveEvent(self, ev):
        # Draw rectangle when mouse is clicked and dragged in copy text mode.
        if self.copy_text_mode:
            if self.click_point:
                pm = self.pm.copy()
                painter = QPainter()
                painter.begin(pm)
                painter.drawRect(QtCore.QRect(self.click_point, ev.pos()))
                painter.end()
                self.setPixmap(pm)
            return

        # Change cursor if cursor is over link annotation
        for area in self.link_areas:
            if area.contains(ev.pos()):
                self.setCursor(QtCore.Qt.PointingHandCursor)
                return
        self.unsetCursor()
        ev.ignore()         # pass to underlying frame if not over link or copy text mode

    def mousePressEvent(self, ev):
        #if self.cursor() != QtCore.Qt.PointingHandCursor: return
        # In text copy mode
        if self.copy_text_mode:
            self.click_point = ev.pos()
            self.pm = self.pixmap().copy()
            return
        # In normal mode
        for i, area in enumerate(self.link_areas):
            if area.contains(ev.pos()):
              # For jump to page link
              if self.link_annots[i].linkDestination().linkType() == Poppler.Link.Goto:
                p = self.link_annots[i].linkDestination().destination().pageNumber()
                self.jumpToRequested.emit(p-1)
              # For URL link
              elif self.link_annots[i].linkDestination().linkType() == Poppler.Link.Browse:
                p = self.link_annots[i].linkDestination().url()
                if p.startswith("http"):
                  confirm = QMessageBox.question(self, "Open Url in Browser",
                            "Do you want to open browser to open...\n%s"%p, QMessageBox.Yes|QMessageBox.Cancel)
                  if confirm == 0x00004000:
                    Popen(["x-www-browser", p])
              return
        ev.ignore()

    def mouseReleaseEvent(self, ev):
        if self.copy_text_mode:
            self.copyTextRequested.emit(self.click_point, ev.pos())
            self.click_point = None
            self.setPixmap(self.pm)
            return
        ev.ignore()

    def updateImage(self):
        #if self.image.isNull() : return
        if self.highlight_area:
            img = self.image.copy()
            painter = QPainter(img)
            zoom = self.dpi/72.0
            for area in self.highlight_area:
                box = QtCore.QRectF(area.left()*zoom, area.top()*zoom,
                                    area.width()*zoom, area.height()*zoom)
                painter.fillRect(box, QColor(0,255,0, 127))
            painter.end()
            self.setPixmap(img)
        else:
            self.setPixmap(self.image)


def wait(millisec):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(millisec, loop.quit)
    loop.exec_()

def collapseUser(path):
    ''' converts /home/user/file.ext to ~/file.ext '''
    if path.startswith(HOMEDIR):
        return path.replace(HOMEDIR, '~', 1)
    return path

def elideMiddle(text, length):
    if len(text) <= length: return text
    return text[:length//2] + '...' + text[len(text)-length+length//2:]

def main():
    app = QApplication(sys.argv)
    win = Main()
    if len(sys.argv)>1 and os.path.exists(os.path.abspath(sys.argv[-1])):
        win.loadPDFfile(os.path.abspath(sys.argv[-1]))
    app.aboutToQuit.connect(win.onAppQuit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
