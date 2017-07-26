#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
from os import path, environ
from subprocess import Popen
from PyQt4 import QtCore
from PyQt4.QtGui import QApplication, QMainWindow, QPixmap, QImage, QWidget, QFrame, QVBoxLayout, QLabel
from PyQt4.QtGui import QFileDialog, QInputDialog, QAction, QIcon, QLineEdit, QStandardItem, QStandardItemModel
from PyQt4.QtGui import QIntValidator, QComboBox, QPainter, QColor, QMessageBox
#from PyQt4.QtGui import QDesktopServices
from popplerqt4 import Poppler
import resources
from ui_main_window import Ui_window

#from PyQt4 import uic
#main_ui = uic.loadUiType("main_window.ui")

dpi = 100
HOMEDIR = environ["HOME"]

class Renderer(QtCore.QObject):
    rendered = QtCore.pyqtSignal(int, QImage)
    textFound = QtCore.pyqtSignal(int, QtCore.QRectF)

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
            x, y = annot.boundary().left()*img.width(), annot.boundary().top()*img.height()-1
            w, h = annot.boundary().width()*img.width()-1, annot.boundary().height()*img.height()-1
            self.painter.fillRect(x, y, w, h, self.link_color)
        self.painter.end()
        self.rendered.emit(page_no, img)

    def loadDocument(self, filename, password=''):
        """ loadDocument(str)
        Main thread uses this slot to load document for rendering """
        self.doc = Poppler.Document.load(filename, password, password)
        self.doc.setRenderHint(Poppler.Document.TextAntialiasing | Poppler.Document.TextHinting |
                               Poppler.Document.Antialiasing | 0x00000020 )

    def findText(self, text, page_num, area, find_reverse):
        if find_reverse:
          pages = range(page_num+1)
          pages.reverse()
          for page_no in pages:
            page = self.doc.page(page_no)
            found = page.search(text, area, Poppler.Page.PreviousResult, Poppler.Page.CaseInsensitive )
            if found:
              self.textFound.emit(page_no, area)
              break
            area = QtCore.QRectF(page.pageSizeF().width(), page.pageSizeF().height(),0,0) if find_reverse else QtCore.QRectF()
        else:
          pages = range(page_num, self.doc.numPages())
          for page_no in pages:
            page = self.doc.page(page_no)
            found = page.search(text, area, Poppler.Page.NextResult, Poppler.Page.CaseInsensitive )
            if found:
              self.textFound.emit(page_no, area)
              break
            area = QtCore.QRectF()

#class Main(main_ui[0], main_ui[1]):
class Main(QMainWindow, Ui_window):
    renderRequested = QtCore.pyqtSignal(int, float)
    loadFileRequested = QtCore.pyqtSignal(unicode, QtCore.QByteArray)
    findTextRequested = QtCore.pyqtSignal(str, int, QtCore.QRectF, bool)

    def __init__(self, parent=None):
        super(Main, self).__init__(parent)
        self.setupUi(self)
        self.dockSearch.hide()
        self.dockWidget.hide()
        self.dockWidget.setMinimumWidth(310)
        self.findTextEdit.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.findCloseButton.setIcon(QIcon(':/close.png'))
        self.treeView.setAlternatingRowColors(True)
        self.treeView.clicked.connect(self.onOutlineClick)
        self.first_document = True
        desktop = QApplication.desktop()
        # Impoort settings
        self.settings = QtCore.QSettings("gospel-pdf", "main", self)
        global dpi
        dpi = int(self.settings.value("DPI", 100).toString())
        self.history_filenames = list( self.settings.value("HistoryFileNameList", []).toStringList())
        self.history_page_no = list( self.settings.value("HistoryPageNoList", []).toStringList() )
        self.offset_x = int(self.settings.value("OffsetX", 4).toString())
        self.offset_y = int(self.settings.value("OffsetY", 26).toString())
        self.available_area = [desktop.availableGeometry().width(), desktop.availableGeometry().height()]
        self.fixed_width = int(self.settings.value("FixedWidth", 900).toString())
        # Add shortcut actions
        self.openFileAction = QAction(QIcon(":/open.png"), "Open", self)
        self.openFileAction.setShortcut("Ctrl+O")
        self.openFileAction.triggered.connect(self.openFile)
        self.quitAction = QAction(QIcon(":/quit.png"), "Quit", self)
        self.quitAction.setShortcut("Ctrl+Q")
        self.quitAction.triggered.connect(self.close)
        self.firstPageAction = QAction(QIcon(":/go-first.png"), "First Page", self)
        self.firstPageAction.triggered.connect(self.goFirstPage)
        self.prevPageAction = QAction(QIcon(":/prev.png"), "Prev Page", self)
        self.prevPageAction.setShortcut("Left")
        self.prevPageAction.triggered.connect(self.goPrevPage)
        self.nextPageAction = QAction(QIcon(":/next.png"), "Next Page", self)
        self.nextPageAction.setShortcut("Right")
        self.nextPageAction.triggered.connect(self.goNextPage)
        self.lastPageAction = QAction(QIcon(":/go-last.png"), "Last Page", self)
        self.lastPageAction.triggered.connect(self.goLastPage)
        self.gotoPageAction = QAction(QIcon(":/goto.png"), "GoTo Page", self)
        self.gotoPageAction.triggered.connect(self.gotoPage)
        self.undoJumpAction = QAction(QIcon(":/undo-jump.png"), "Jump Back", self)
        self.undoJumpAction.setShortcut("Shift+Backspace")
        self.undoJumpAction.triggered.connect(self.undoJump)
        self.zoominAction = QAction(QIcon(":/zoomin.png"), "Zoom In", self)
        self.zoominAction.setShortcut("Ctrl++")
        self.zoominAction.triggered.connect(self.zoomIn)
        self.zoomoutAction = QAction(QIcon(":/zoomout.png"), "Zoom Out", self)
        self.zoomoutAction.setShortcut("Ctrl+-")
        self.zoomoutAction.triggered.connect(self.zoomOut)
        self.copyTextAction = QAction(QIcon(":/copy.png"), "Copy Text", self)
        self.copyTextAction.setCheckable(True)
        self.copyTextAction.triggered.connect(self.toggleCopyText)
        self.findTextAction = QAction(QIcon(":/search.png"), "Find Text", self)
        self.findTextAction.setShortcut('Ctrl+F')
        self.findTextAction.triggered.connect(self.dockSearch.show)
        # Create menu actions
        self.menuFile.addAction(self.openFileAction)
        self.menuFile.addAction(self.quitAction)
        self.menuView.addAction(self.zoominAction)
        self.menuView.addAction(self.zoomoutAction)
        self.menuNavigate.addAction(self.prevPageAction)
        self.menuNavigate.addAction(self.nextPageAction)
        self.menuNavigate.addAction(self.undoJumpAction)
        # Create widgets for menubar / toolbar
        self.totalPagesLabel = QLabel(self)
        self.totalPagesLabel.setMinimumWidth(100)
        self.menubar.setCornerWidget(self.totalPagesLabel)
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
        if dpi in self.zoom_levels: 
            self.zoomLevelCombo.setCurrentIndex(self.zoom_levels.index(dpi))
        else:
            self.zoomLevelCombo.setCurrentIndex(2)
        # Add toolbar actions
        self.toolBar.addAction(self.openFileAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.zoominAction)
        self.toolBar.addWidget(self.zoomLevelCombo)
        self.toolBar.addAction(self.zoomoutAction)
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
        # Show Window
        self.show()
        # Initialize Variables
        self.pages = []
        self.filename = None
        self.jumped_from = None

    def removeOldDoc(self):
        # Save current page number
        if self.filename in self.history_filenames:
            index = self.history_filenames.index(self.filename)
            self.history_page_no[index] = self.current_page
        else:
            self.history_filenames.append(self.filename)
            self.history_page_no.append(self.current_page)
        # Remove old document
        for i in range(len(self.pages)):
            self.verticalLayout.removeWidget(self.pages[-1])
        for i in range(len(self.pages)):
            self.pages.pop().deleteLater()
        self.frame.deleteLater()

    def loadPDFfile(self, filename):
        """ Loads pdf document in all threads """
        self.filename = unicode(filename)
        self.doc = Poppler.Document.load(filename)
        if not self.doc : return
        password = ''
        if self.doc.isLocked() : 
            password = QInputDialog.getText(self, 'This PDF is locked', 'Enter Password :', 2)[0].toUtf8()
            if password == '' : sys.exit(1)
            self.doc.unlock(password, password)
        if not self.first_document:
            self.removeOldDoc()
        # Load Document in other threads
        self.loadFileRequested.emit(filename, password)
        self.total_pages = self.doc.numPages()
        try : self.current_page = int(self.history_page_no[self.history_filenames.index(self.filename)])
        except : self.current_page = 0
        self.rendered_pages = []
        self.first_document = False
        self.scroll_render_lock = False
        # Add widgets
        self.frame = QFrame(self.scrollAreaWidgetContents)
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
        self.renderCurrentPage()
        # Resize window
        self.larger_page = 2 if (self.total_pages > 2) else 0
        self.getOutlines(self.doc)
        self.move((self.available_area[0]-(self.width()+2*self.offset_x))/2,
                    (self.available_area[1]-(self.height()+self.offset_y+self.offset_x))/2 )
        #scrolbar_pos = self.pages[self.current_page].pos().y()
        #self.scrollArea.verticalScrollBar().setValue(scrolbar_pos)
        self.totalPagesLabel.setText("Total "+str(self.total_pages)+" pages")
        self.pageNoLabel.setText(str(self.current_page+1))
        self.gotoPageValidator.setTop(self.total_pages)
        self.setWindowTitle(path.basename(self.filename)+ " - Gospel PDF")
        if self.current_page != 0 : QtCore.QTimer.singleShot(300, self.jumpToCurrentPage)

    def setRenderedImage(self, page_no, image):
        """ takes a QImage and sets pixmap of the specified page 
            when number of rendered pages exceeds a certain number, old page image is
            deleted to save memory """
        self.pages[page_no].setPageData(page_no, QPixmap.fromImage(image), self.doc.page(page_no))
        # Request to render next page
        if page_no < self.current_page + self.max_preload - 2: 
            if page_no+2 not in self.rendered_pages and page_no+2 < self.total_pages:
              self.rendered_pages.append(page_no+2)
              self.renderRequested.emit(page_no+2, self.pages[page_no+2].dpi)
              self.pages[page_no+2].jumpToRequested.connect(self.jumpToPage)
        # Replace old rendered pages with blank image
        if len(self.rendered_pages)>10:
            self.pages[self.rendered_pages[0]].clear()
            self.pages[self.rendered_pages[0]].jumpToRequested.disconnect(self.jumpToPage)
            self.rendered_pages.pop(0)
        print page_no, self.rendered_pages

    def renderCurrentPage(self):
        """ Requests to render current page. if it is already rendered, then request
            to render next unrendered page """
        requested = 0
        for page_no in range(self.current_page, self.current_page+self.max_preload):
            if page_no not in self.rendered_pages and page_no < self.total_pages:
                #dpi = self.pages[page_no].dpi
                self.rendered_pages.append(page_no)
                self.renderRequested.emit(page_no, self.pages[page_no].dpi)
                self.pages[page_no].jumpToRequested.connect(self.jumpToPage)
                requested += 1
                print page_no
                if requested == 2: return

    def onMouseScroll(self, pos):
        """ Gets the current page number on scrolling, then requests to render"""
        index = self.verticalLayout.indexOf(self.frame.childAt(self.frame.width()/2, pos))
        if index == -1: return
        self.pageNoLabel.setText(str(index+1))
        if self.scrollArea.verticalScrollBar().isSliderDown() or self.scroll_render_lock : return
        self.current_page = index
        self.renderCurrentPage()

    def onSliderRelease(self):
        self.onMouseScroll(self.scrollArea.verticalScrollBar().value())

    def openFile(self):
        filename = QFileDialog.getOpenFileName(self.centralwidget.window(),
                                      "Select Document to Open", "",
                                      "Portable Document Format (*.pdf)" )
        if not filename.isEmpty():
            self.loadPDFfile(filename)

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
        if text.isEmpty() : return
        #self.current_page = int(text)-1
        self.jumpToPage(int(text)-1)
        self.gotoPageEdit.clear()
        self.gotoPageEdit.clearFocus()

    def resizePages(self):
        global dpi
        for i in range(self.total_pages):
            if self.zoomLevelCombo.currentIndex() == 0:
                DPI = 72.0*self.fixed_width/self.doc.page(i).pageSizeF().width()
            else: DPI = dpi
            self.pages[i].dpi = DPI
            self.pages[i].setFixedSize(self.doc.page(i).pageSizeF().width()*DPI/72.0, self.doc.page(i).pageSizeF().height()*DPI/72.0)
        for page_no in self.rendered_pages:
            self.pages[page_no].clear()

    def setZoom(self, index):
        """ Gets called when zoom level is changed"""
        self.scroll_render_lock = True # rendering on scroll is locked as set scroll position 
        global dpi
        if index==0:
            dpi = 0
            self.fixed_width = self.pages[self.current_page].width()
        else:
            dpi = self.zoom_levels[index]
        self.resizePages()
        self.rendered_pages = []
        self.renderCurrentPage()
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
    def findNext(self):
        text = self.findTextEdit.text()
        area = self.search_area.adjusted(self.search_area.width(), 1, self.search_area.width(), 1)
        self.findTextRequested.emit(text, self.search_page_no, area, False)
        if self.search_text == text: return
        self.search_text = text
        self.search_area = QtCore.QRectF()
        self.search_page_no = self.current_page

    def findBack(self):
        text = self.findTextEdit.text()
        area = self.search_area.adjusted(-self.search_area.width(), -1, -self.search_area.width(), -1)
        self.findTextRequested.emit(text, self.search_page_no, area, True)
        if self.search_text == text: return
        self.search_text = text
        self.search_area = QtCore.QRectF()
        self.search_page_no = self.current_page

    def onTextFound(self, page_no, area):
        zoom = self.pages[page_no].dpi/72.0
        self.pages[page_no].highlight_area = QtCore.QRectF(area.left()*zoom, area.top()*zoom,
                                                           area.width()*zoom, area.height()*zoom)
        # Alternate method of above two lines
        #matrix = QMatrix(self.pages[page_no].dpi/72.0, 0,0, self.pages[page_no].dpi/72.0,0,0)
        #self.pages[page_no].highlight_area = matrix.mapRect(area).toRect()
        if self.pages[page_no].pixmap():
            self.pages[page_no].updateImage()
        else:
            self.rendered_pages.append(page_no)
            self.renderRequested.emit(page_no, self.pages[page_no].dpi)
        if page_no != self.search_page_no :
            self.pages[self.search_page_no].highlight_area = None
            self.pages[self.search_page_no].updateImage()
            self.jumpToPage(page_no)
        self.search_area = area
        self.search_page_no = page_no

    def toggleFindMode(self, enable):
        if enable:
          self.findTextEdit.setFocus()
          self.search_text = ''
          self.search_area = QtCore.QRectF()
          self.search_page_no = self.current_page
        else:
          self.pages[self.search_page_no].highlight_area = None
          self.pages[self.search_page_no].updateImage()
          self.search_text = ''
          self.search_area = QtCore.QRectF()
          self.findTextEdit.setText('')

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
        #self.treeView.setColumnWidth(2, 30)
        toc = doc.toc()
        if not toc:
            self.dockWidget.hide()
            self.resize(self.pages[self.larger_page].width() + 56, self.available_area[1]-self.offset_y)
            return
        self.dockWidget.show()
        outline_model = QStandardItemModel(self)
        parent_item = outline_model.invisibleRootItem()
        node = toc.firstChild()
        loadOutline(doc, node, parent_item)
        self.treeView.setModel(outline_model)
        self.treeView.expandToDepth(0)
        self.treeView.setHeaderHidden(True)
        self.treeView.header().setResizeMode(0, 1)
        self.treeView.header().setResizeMode(1, 3)
        self.treeView.header().setStretchLastSection(False)
        self.resize(self.pages[self.larger_page].width() + 56 + 310, self.available_area[1]-self.offset_y)

    def onOutlineClick(self, m_index):
        page = self.treeView.model().data(m_index, QtCore.Qt.UserRole+1).toString()
        if page == "": return
        self.jumpToPage(int(page)-1)

    def closeEvent(self, ev):
        """ Save all settings on window close """
        self.settings.setValue("OffsetX", self.geometry().x()-self.x())
        self.settings.setValue("OffsetY", self.geometry().y()-self.y())
        self.settings.setValue("DPI", dpi)
        self.settings.setValue("FixedWidth", self.fixed_width)
        if self.filename:
            if self.filename in self.history_filenames:
                index = self.history_filenames.index(self.filename)
                self.history_page_no[index] = self.current_page
            else:
                self.history_filenames.append(self.filename)
                self.history_page_no.append(self.current_page)
        self.settings.setValue("HistoryFileNameList", self.history_filenames)
        self.settings.setValue("HistoryPageNoList", self.history_page_no)
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
                x, y = annot.boundary().left()*pixmap.width(), annot.boundary().top()*pixmap.height()-1
                w, h = annot.boundary().width()*pixmap.width()-1, annot.boundary().height()*pixmap.height()-1
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
        self.unsetCursor()
        for area in self.link_areas:
            if area.contains(ev.pos()): 
                self.setCursor(QtCore.Qt.PointingHandCursor)
                break

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
                if p.startsWith("http"):
                  confirm = QMessageBox.question(self, "Open Url in Browser", 
                            "Do you want to open browser to open...\n%s"%p, QMessageBox.Yes|QMessageBox.Cancel)
                  if confirm == 0x00004000:
                    Popen(["x-www-browser", p])
              return

    def mouseReleaseEvent(self, ev):
        if self.copy_text_mode:
            self.copyTextRequested.emit(self.click_point, ev.pos())
            self.click_point = None
            self.setPixmap(self.pm)

    def updateImage(self):
        #if self.image.isNull() : return
        if self.highlight_area:
            img = self.image.copy()
            painter = QPainter(img)
            painter.fillRect(self.highlight_area, QColor(0,255,0, 127))
            painter.end()
            self.setPixmap(img)
        else:
            self.setPixmap(self.image)

def main():
    app = QApplication(sys.argv)
    win = Main()
    if len(sys.argv)>1 and path.exists(path.abspath(sys.argv[-1])):
        win.loadPDFfile(QtCore.QString.fromUtf8(path.abspath(sys.argv[-1])))
    app.aboutToQuit.connect(win.onAppQuit)
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
