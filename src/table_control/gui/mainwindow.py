import logging
import threading
import traceback

from PySide6 import QtCore, QtGui, QtStateMachine, QtWidgets

from ..core.pluginmanager import PluginManager

from . import APP_TITLE, APP_VERSION
from .preferences import PreferencesDialog
from .controller import TableController
from .connection import ConnectionDialog
from .dashboard import DashboardWidget
from .utils import loadIcon, loadText


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.pluginManager = PluginManager()

        self.tableController = TableController()
        self.tableController.failed.connect(self.showException)

        self.appliances: dict = {}

        self.quitAction = QtGui.QAction(self)
        self.quitAction.setText("&Quit")
        self.quitAction.setShortcut("Ctrl+Q")
        self.quitAction.triggered.connect(self.close)

        self.preferencesAction = QtGui.QAction(self)
        self.preferencesAction.setText("&Preferences")
        self.preferencesAction.triggered.connect(self.showPreferences)

        self.connectAction = QtGui.QAction(self)
        self.connectAction.setText("&Connect")
        self.connectAction.setIcon(loadIcon("connect.svg"))
        self.connectAction.triggered.connect(self.connectTable)

        self.disconnectAction = QtGui.QAction(self)
        self.disconnectAction.setText("&Disconnect")
        self.disconnectAction.setIcon(loadIcon("disconnect.svg"))
        self.disconnectAction.triggered.connect(self.disconnectTable)

        self.stopAction = QtGui.QAction(self)
        self.stopAction.setText("&Stop")
        self.stopAction.setIcon(loadIcon("stop.svg"))
        self.stopAction.triggered.connect(self.requestStop)

        self.aboutQtAction = QtGui.QAction(self)
        self.aboutQtAction.setText("About &Qt")
        self.aboutQtAction.triggered.connect(self.showAboutQt)

        self.aboutAction = QtGui.QAction(self)
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

        self.dashboard = DashboardWidget(self)
        self.setCentralWidget(self.dashboard)

        self.dashboard.relativeMoveRequested.connect(self.tableController.moveRelative)
        self.dashboard.absoluteMoveRequested.connect(self.tableController.moveAbsolute)
        self.dashboard.calibrateRequested.connect(self.tableController.calibrate)
        self.dashboard.rangeMeasureRequested.connect(self.tableController.rangeMeasure)
        self.dashboard.stopRequested.connect(self.tableController.requestStop)
        self.dashboard.updateIntervalChanged.connect(self.tableController.setUpdateInterval)
        self.tableController.infoChanged.connect(self.dashboard.setController)
        self.tableController.positionChanged.connect(self.dashboard.setTablePosition)
        self.tableController.calibrationChanged.connect(self.dashboard.setTableCalibration)

        # Status bar

        self.progressBar = QtWidgets.QProgressBar(self)
        self.progressBar.setRange(0, 0)
        self.progressBar.hide()

        self.statusBar().addPermanentWidget(self.progressBar)

        self.connectedState = QtStateMachine.QState()
        self.connectedState.entered.connect(self.enterConnected)

        self.disconnectedState = QtStateMachine.QState()
        self.disconnectedState.entered.connect(self.enterDisconnected)

        self.movingState = QtStateMachine.QState()
        self.movingState.entered.connect(self.enterMoving)

        self.connectedState.addTransition(self.tableController.disconnected, self.disconnectedState)
        self.disconnectedState.addTransition(self.tableController.connected, self.connectedState)
        self.disconnectedState.addTransition(self.tableController.disconnected, self.disconnectedState)
        self.connectedState.addTransition(self.tableController.movementStarted, self.movingState)
        self.connectedState.addTransition(self.dashboard.moveRequested, self.movingState)
        self.movingState.addTransition(self.tableController.movementFinished, self.connectedState)
        self.movingState.addTransition(self.tableController.disconnected, self.disconnectedState)

        self.stateMachine = QtStateMachine.QStateMachine(self)
        self.stateMachine.addState(self.connectedState)
        self.stateMachine.addState(self.disconnectedState)
        self.stateMachine.addState(self.movingState)
        self.stateMachine.setInitialState(self.disconnectedState)
        self.stateMachine.start()

    def registerPlugin(self, plugin) -> None:
        self.pluginManager.register_plugin(plugin)

    def installPlugins(self) -> None:
        self.pluginManager.dispatch("install", (self,))

    def uninstallPlugins(self) -> None:
        self.pluginManager.dispatch("uninstall", (self,))

    def registerAppliance(self, name: str, appliance: dict) -> None:
        self.appliances.update({name: appliance})

    def readSettings(self) -> None:
        settings = QtCore.QSettings()
        self.pluginManager.dispatch("beforeReadSettings", (settings,))
        settings.beginGroup("mainwindow")
        geometry: QtCore.QByteArray = settings.value("geometry", QtCore.QByteArray(), QtCore.QByteArray)  # type: ignore
        state: QtCore.QByteArray = settings.value("state", QtCore.QByteArray(), QtCore.QByteArray)  # type: ignore
        updateInterval: float = settings.value("updateInterval", 1.0, float)  # type: ignore
        settings.endGroup()
        self.restoreGeometry(geometry)
        self.restoreState(state)
        self.dashboard.setUpdateInterval(updateInterval)
        self.pluginManager.dispatch("afterReadSettings", (settings,))

    def writeSettings(self) -> None:
        settings = QtCore.QSettings()
        self.pluginManager.dispatch("beforeWriteSettings", (settings,))
        settings.beginGroup("mainwindow")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("state", self.saveState())
        settings.setValue("updateInterval", self.dashboard.updateInterval())
        settings.endGroup()
        self.pluginManager.dispatch("afterWriteSettings", (settings,))

    def showPreferences(self) -> None:
        settings = QtCore.QSettings()
        dialog = PreferencesDialog(settings, self)
        self.pluginManager.dispatch("beforePreferences", (dialog,))
        dialog.exec()
        self.pluginManager.dispatch("afterPreferences", (dialog,))
        if dialog.result() == dialog.DialogCode.Accepted:
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
        dialog.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        dialog.setDetailedText(details)
        dialog.setStandardButtons(dialog.StandardButton.Ok)
        dialog.setDefaultButton(dialog.StandardButton.Ok)
        # Fix message box width
        spacer = QtWidgets.QSpacerItem(448, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = dialog.layout()
        if isinstance(layout, QtWidgets.QGridLayout):
            layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        dialog.exec()

    def setupConnection(self) -> bool:
        dialog = ConnectionDialog(self)
        for name, appliance in self.appliances.items():
            dialog.addAppliance(name, appliance)
        dialog.readSettings()
        dialog.exec()
        if dialog.result() == dialog.DialogCode.Accepted:
            dialog.writeSettings()
            self.tableController.setAppliance(dialog.appliance())
        return dialog.result() == dialog.DialogCode.Accepted

    def connectTable(self) -> None:
        if self.setupConnection():
            self.connectAction.setEnabled(False)
            self.disconnectAction.setEnabled(False)
            self.tableController.connectTable()

    def disconnectTable(self) -> None:
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(False)
        self.tableController.disconnectTable()

    def requestStop(self) -> None:
        self.tableController.requestStop()

    def enterDisconnected(self) -> None:
        self.pluginManager.dispatch("beforeEnterDisconnected", (self,))
        self.connectAction.setEnabled(True)
        self.disconnectAction.setEnabled(False)
        self.stopAction.setEnabled(False)
        self.dashboard.enterDisconnected()
        self.progressBar.hide()
        self.pluginManager.dispatch("afterEnterDisconnected", (self,))

    def enterConnected(self) -> None:
        self.pluginManager.dispatch("beforeEnterConnected", (self,))
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(True)
        self.stopAction.setEnabled(True)
        self.dashboard.enterConnected()
        self.progressBar.hide()
        self.pluginManager.dispatch("afterEnterConnected", (self,))

    def enterMoving(self) -> None:
        self.pluginManager.dispatch("beforeEnterMoving", (self,))
        self.connectAction.setEnabled(False)
        self.disconnectAction.setEnabled(False)
        self.stopAction.setEnabled(True)
        self.dashboard.enterMoving()
        self.progressBar.show()
        self.pluginManager.dispatch("afterEnterMoving", (self,))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if not self.connectAction.isEnabled():
            result = QtWidgets.QMessageBox.question(self, "Quit?", "Close current connection?")
            if result != QtWidgets.QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.disconnectAction.trigger()
        self.tableController.shutdown()
        event.accept()
