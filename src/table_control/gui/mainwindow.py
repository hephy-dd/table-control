import logging
import threading
import traceback
from typing import Optional

from PyQt5 import QtCore, QtGui, QtWidgets

from . import APP_TITLE, APP_VERSION
from .pluginmanager import PluginManager
from .preferences import PreferencesDialog
from .controller import TableController
from .connection import ConnectionDialog
from .dashboard import DashboardWidget
from .utils import loadIcon, loadText


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)

        self.pluginManager = PluginManager()

        self.tableController = TableController()
        self.tableController.failed.connect(self.showException)

        self.appliances: dict = {}

        self.quitAction = QtWidgets.QAction(self)
        self.quitAction.setText("&Quit")
        self.quitAction.setShortcut("Ctrl+Q")
        self.quitAction.triggered.connect(self.close)

        self.preferencesAction = QtWidgets.QAction(self)
        self.preferencesAction.setText("&Preferences")
        self.preferencesAction.triggered.connect(self.showPreferences)

        self.connectAction = QtWidgets.QAction(self)
        self.connectAction.setText("&Connect")
        self.connectAction.setIcon(loadIcon("connect.svg"))
        self.connectAction.triggered.connect(self.connect)

        self.disconnectAction = QtWidgets.QAction(self)
        self.disconnectAction.setText("&Disconnect")
        self.disconnectAction.setIcon(loadIcon("disconnect.svg"))
        self.disconnectAction.triggered.connect(self.disconnect)

        self.stopAction = QtWidgets.QAction(self)
        self.stopAction.setText("&Stop")
        self.stopAction.setIcon(loadIcon("stop.svg"))
        self.stopAction.triggered.connect(self.requestStop)

        self.aboutQtAction = QtWidgets.QAction(self)
        self.aboutQtAction.setText("About &Qt")
        self.aboutQtAction.triggered.connect(self.showAboutQt)

        self.aboutAction = QtWidgets.QAction(self)
        self.aboutAction.setText("&About")
        self.aboutAction.triggered.connect(self.showAbout)

        self.fileMenu = self.menuBar().addMenu("&File")
        self.fileMenu.addAction(self.quitAction)

        self.editMenu = self.menuBar().addMenu("&Edit")
        self.editMenu.addAction(self.preferencesAction)

        self.viewMenu = self.menuBar().addMenu("&View")
        self.viewMenu.menuAction().setVisible(False)  # not used at default

        self.tableMenu = self.menuBar().addMenu("&Table")
        self.tableMenu.addAction(self.connectAction)
        self.tableMenu.addAction(self.disconnectAction)
        self.tableMenu.addSeparator()
        self.tableMenu.addAction(self.stopAction)

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.aboutQtAction)
        self.helpMenu.addAction(self.aboutAction)

        # Toolbars

        self.mainToolBar = self.addToolBar("main")
        self.mainToolBar.setObjectName("mainToolBar")
        self.mainToolBar.addActions(self.tableMenu.actions())

        # Central widget

        self.dashboard = DashboardWidget(self.tableController)
        self.setCentralWidget(self.dashboard)

        self.tableController.infoChanged.connect(self.dashboard.setController)
        self.tableController.positionChanged.connect(self.dashboard.setTablePosition)
        self.tableController.calibrationChanged.connect(self.dashboard.setTableCalibration)

        # Status bar

        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setRange(0, 0)
        self.progressBar.hide()

        self.statusBar().addPermanentWidget(self.progressBar)

        self.connectedState = QtCore.QState()
        self.connectedState.entered.connect(self.enterConnected)

        self.disconnectedState = QtCore.QState()
        self.disconnectedState.entered.connect(self.enterDisconnected)

        self.movingState = QtCore.QState()
        self.movingState.entered.connect(self.enterMoving)

        self.connectedState.addTransition(self.tableController.disconnected, self.disconnectedState)
        self.disconnectedState.addTransition(self.tableController.connected, self.connectedState)
        self.disconnectedState.addTransition(self.tableController.disconnected, self.disconnectedState)
        self.connectedState.addTransition(self.tableController.movementStarted, self.movingState)
        self.connectedState.addTransition(self.dashboard.moveRequested, self.movingState)
        self.movingState.addTransition(self.tableController.movementFinished, self.connectedState)
        self.movingState.addTransition(self.tableController.disconnected, self.disconnectedState)

        self.stateMachine = QtCore.QStateMachine(self)
        self.stateMachine.addState(self.connectedState)
        self.stateMachine.addState(self.disconnectedState)
        self.stateMachine.addState(self.movingState)
        self.stateMachine.setInitialState(self.disconnectedState)
        self.stateMachine.start()

    def registerPlugin(self, plugin) -> None:
        self.pluginManager.registerPlugin(plugin)

    def installPlugins(self) -> None:
        self.pluginManager.dispatch("install", (self,))

    def uninstallPlugins(self) -> None:
        self.pluginManager.dispatch("uninstall", (self,))

    def registerAppliance(self, name: str, appliance: dict) -> None:
        self.appliances.update({name: appliance})

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("mainwindow")
        geometry = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)
        settings.endGroup()
        self.restoreGeometry(geometry)

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("mainwindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.endGroup()

    def showPreferences(self) -> None:
        dialog = PreferencesDialog(self)
        self.pluginManager.dispatch("beforePreferences", (dialog,))
        dialog.exec()
        self.pluginManager.dispatch("afterPreferences", (dialog,))
        if dialog.result() == dialog.Accepted:
            ...

    def showAboutQt(self) -> None:
        QtWidgets.QMessageBox.aboutQt(self, "About Qt")

    def showAbout(self) -> None:
        QtWidgets.QMessageBox.about(self, "About", loadText("about.txt").format(title=APP_TITLE, version=APP_VERSION))

    def showException(self, exc) -> None:
        details = "".join(traceback.format_tb(exc.__traceback__))
        dialog = QtWidgets.QMessageBox(self)
        dialog.setWindowTitle("Exception")
        dialog.setText(format(exc))
        dialog.setIcon(QtWidgets.QMessageBox.Critical)
        dialog.setDetailedText(details)
        dialog.setStandardButtons(dialog.Ok)
        dialog.setDefaultButton(dialog.Ok)
        # Fix message box width
        spacer = QtWidgets.QSpacerItem(448, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        dialog.layout().addItem(spacer, dialog.layout().rowCount(), 0, 1, dialog.layout().columnCount())
        dialog.exec()

    def setupConnection(self) -> None:
        dialog = ConnectionDialog(self)
        for name, appliance in self.appliances.items():
            dialog.addAppliance(name, appliance)
        dialog.readSettings()
        dialog.exec()
        if dialog.result() == dialog.Accepted:
            dialog.writeSettings()
            self.tableController.setAppliance(dialog.appliance())
        return dialog.result() == dialog.Accepted

    def connect(self) -> None:
        if self.setupConnection():
            self.connectAction.setEnabled(False)
            self.disconnectAction.setEnabled(False)
            self.tableController.connect()

    def disconnect(self) -> None:
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(False)
        self.tableController.disconnect()

    def requestStop(self) -> None:
        self.tableController.requestStop()

    def enterDisconnected(self) -> None:
        self.connectAction.setEnabled(True)
        self.disconnectAction.setEnabled(False)
        self.stopAction.setEnabled(False)
        self.dashboard.enterDisconnected()
        self.progressBar.hide()

    def enterConnected(self) -> None:
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(True)
        self.stopAction.setEnabled(True)
        self.dashboard.enterConnected()
        self.progressBar.hide()

    def enterMoving(self) -> None:
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(False)
        self.stopAction.setEnabled(True)
        self.dashboard.enterMoving()
        self.progressBar.show()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self.connectAction.isEnabled():
            result = QtWidgets.QMessageBox.question(self, "Quit?", "Close current connection?")
            if result != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
            self.disconnectAction.trigger()
        self.tableController.shutdown()
        event.accept()
