# gospel-pdf-viewer
Poppler based pdf viewer for Linux written in PyQt

**Dependency :**  
* python3-pyqt5  
* python3-poppler-qt5  
* quikprint (for print support, optional)  
* qpdf (to unlock pdf, optional)  

### Description
This program is aimed at short startup time, with all generally used features.  
This is a evince or qpdfview alternative for linux users.

### Installation
To Install this program open terminal inside gospel-pdf-viewer-master directory.  
First compile UI and Resources file  
`cd files`  
`./compile_ui`  
`./compile_rc`  
`cd ..`  
And then run following command..  
`sudo pip3 install .`  
or  
`pip3 install --user .`  

Gospel PDF will be automatically added to application menu.

To uninstall run..  
`sudo pip3 uninstall gospel-pdf`


### Usage
To run after installing, type command..  
  `gospel-pdf`  
Or  
  `gospel-pdf filename.pdf`  
If you want to run this program without/before installing, then  
Open terminal and change directory to gospel-pdf-viewer-master and run  
  `./run.sh`  
Or  
  `./run.sh filename.pdf`  

