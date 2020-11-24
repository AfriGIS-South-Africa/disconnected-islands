# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DisconnectedIslands
                                 A QGIS plugin
 Finds disconnected "islands" in a road network layer, so that a routing tool will work between all nodes. A tolerance field allows for imperfect topology.
                              -------------------
        begin                : 2016-03-15
        git sha              : $Format:%H$
        copyright            : (C) 2016 by Peter Smythe / AfriGIS
        email                : peters@afrigis.co.za
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import absolute_import
from builtins import range
from builtins import object
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication, Qt, QVariant
from qgis.PyQt.QtWidgets import QAction, QApplication, QProgressBar
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt import QtGui
# Initialize Qt resources from file resources.py
from . import resources
# Import the code for the dialog
from .disconnected_islands_dialog import DisconnectedIslandsDialog
import os.path


#import networkx as nx
from qgis.core import Qgis, QgsProject, QgsVectorDataProvider, QgsField, QgsSymbol, QgsRendererCategory, QgsCategorizedSymbolRenderer, QgsGeometry
from qgis.gui import QgsMessageBar
#import csv
from random import randint


#import sys
#sys.path.append('/path/to/dir')


class DisconnectedIslands(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'DisconnectedIslands_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        # Create the dialog (after translation) and keep reference
        self.dlg = DisconnectedIslandsDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Disconnected Islands')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'DisconnectedIslands')
        self.toolbar.setObjectName(u'DisconnectedIslands')
        
        self.checkNetworkXModule()

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('DisconnectedIslands', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/DisconnectedIslands/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'Check for Disconnected Islands'),
            callback=self.run,
            parent=self.iface.mainWindow())


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&Disconnected Islands'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    def getAttributeIndex(self, aLayer):
        """Find the attribute index, adding a new Int column, if necessary"""
        attrName = self.dlg.attributeNameEditBox.text()
        # TODO: If attrName is longer than 10, something fails later.  Move validation to a signal that checks storageType in the UI.
        if len(attrName) > 10 and aLayer.storageType() == 'ESRI Shapefile':
            self.iface.messageBar().pushMessage("Error", "For ESRI Shapefiles, the maximum length of any attribute name is 10. Please choose a shorter attribute name.", level=Qgis.Critical)
            return -3
        attrIdx = aLayer.dataProvider().fieldNameIndex(attrName)
        if attrIdx == -1: # attribute doesn't exist, so create it
            caps = aLayer.dataProvider().capabilities()
            if caps & QgsVectorDataProvider.AddAttributes:
                res = aLayer.dataProvider().addAttributes([QgsField(attrName, QVariant.Int)])
                attrIdx = aLayer.dataProvider().fieldNameIndex(attrName)
                aLayer.updateFields()
                if attrIdx == -1:
                    self.iface.messageBar().pushMessage("Error", "Failed to create attribute!", level=Qgis.Critical)
                    return -1
            else:
                self.iface.messageBar().pushMessage("Error", "Failed to add attribute!", level=Qgis.Critical)
                return -1
        else:
            if not self.dlg.overwriteCheckBox.isChecked():
                self.iface.messageBar().pushMessage("Error", "Attribute already exists - please tick Overwrite to confirm!", level=Qgis.Critical)
                return -2
        return attrIdx

    def checkNetworkXModule(self):
        """check for NetworkX module (especially for Mac) and prompt for install if missing."""

        try:
            import networkx
#            self.iface.messageBar().pushMessage("Info", "NetworkX module is present.", level=Qgis.Info)
        except ImportError:
            self.iface.messageBar().pushMessage("Error in plugin disconnected-islands", "NetworkX module is required and missing. Please install it manually by executing, in a Terminal: sudo easy_install networkx.  Then restart QGIS.", level=Qgis.Critical)
            return -1
        return 0

        
    def run(self):
        """Run method that performs all the real work"""
        
        layers = self.iface.mapCanvas().layers()
        layer_list = []
        self.dlg.layerComboBox.clear()
        for layer in layers:
            layer_list.append(layer.name())
        self.dlg.layerComboBox.addItems(layer_list)
        # TODO: Make the active layer the selected item in combo box  aLayer = qgis.utils.iface.activeLayer()
        
        # TODO: Add signal to update toleranceSpinBox.suffix (Degrees) from layerComboBox.crs.mapUnits when layer is selected:
        #my_UnitType = { 0: 'Meters', 1: 'Feet', 2: 'Degrees', 7: 'NauticalMiles', 8: 'Kilometers', 9: 'Yards', 10: 'Miles', 3: 'UnknownUnit'}
        #suffix = my_UnitType[aLayer.crs().mapUnits()]
        
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            if self.checkNetworkXModule() < 0:
                return -4
            import networkx as nx
            
            layerName = self.dlg.layerComboBox.currentText()
            try:
                aLayer = QgsProject.instance().mapLayersByName(layerName)[0]
            except:
                self.iface.messageBar().pushMessage("Error", "Failed to load layer!", level=Qgis.Critical)
                return -1

            try:

                previousEditingMode = True
                if not aLayer.isEditable():
                    aLayer.startEditing()
                    #self.iface.messageBar().pushMessage("Info", "Layer " + aLayer.name() + " needs to be in edit mode", level=Qgis.Info)
                    #self.iface.messageBar().pushMessage("Error", "Layer " + aLayer.name() + " needs to be in edit mode", level=Qgis.Critical)
                    #return -2
                    previousEditingMode = False
                     
                attrIdx = self.getAttributeIndex(aLayer)
                if attrIdx < 0:
                    return -3  

                progressMessageBar = self.iface.messageBar().createMessage("Creating network graph...")
                progress = QProgressBar()
                progress.setMaximum(aLayer.featureCount())
                progress.setAlignment(Qt.AlignLeft|Qt.AlignVCenter)
                progressMessageBar.layout().addWidget(progress)
                self.iface.messageBar().pushWidget(progressMessageBar, Qgis.Info)          
                
                G = nx.Graph()

                aLayer.beginEditCommand("Clear group attribute, create graph")
                # construct undirected graph
                tolerance = self.dlg.toleranceSpinBox.value()
                if tolerance == 0:
                    tolerance = 0.000001
                count = 0
                for feat in aLayer.getFeatures():
                    count += 1
                    progress.setValue(count)
                    done = aLayer.changeAttributeValue(feat.id(), attrIdx, -1)
                    geom = feat.geometry()
                    QgsGeometry.convertToSingleType(geom)       # QGIS 3.x seems to load single LineString as MultiLineString??
                    line = geom.asPolyline()
                    
                    for i in range(len(line)-1):
                        G.add_edges_from([((int(line[i][0]/tolerance), int(line[i][1]/tolerance)), (int(line[i+1][0]/tolerance), int(line[i+1][1]/tolerance)), 
                                          {'fid': feat.id()})])     # first scale by tolerance, then convert to int.  Before doing this, there were problems (in NetworkX v1) with floats not equating, thus creating disconnects that weren't there.
                    if count % 100 == 0:
                        QApplication.processEvents()      # keep the UI responsive, every 100 features
                        #TODO: check to see if Esc pressed

                aLayer.endEditCommand()
                
                self.iface.messageBar().pushMessage("Finding connected subgraphs, please wait...",  level=Qgis.Warning)     # WARNING - to highlight the next stage, where we cannot show progress
                QApplication.processEvents()
                connected_components = list(G.subgraph(c) for c in nx.connected_components(G))    # this takes a long time.  TODO: how to show progress?
                self.iface.messageBar().pushMessage("Updating group attribute...",  level=Qgis.Info)
                QApplication.processEvents()
                          
                # gather edges and components to which they belong
                fid_comp = {}
                for i, graph in enumerate(connected_components):
                   for edge in graph.edges(data=True):
                       fid_comp[edge[2].get('fid', None)] = i
                
                # write output to csv file
                #with open('C:/Tmp/Components.csv', 'wb') as f:
                #    w = csv.DictWriter(f, fieldnames=['fid', 'group'])
                #    w.writeheader()
                #    for (fid, group) in fid_comp.items():
                #        w.writerow({'fid': fid, 'group': group})
                
                aLayer.beginEditCommand("Update group attribute")
                for (fid, group) in fid_comp.items():
                    done = aLayer.changeAttributeValue(fid, attrIdx, group)
                aLayer.endEditCommand()
                
                groups = list(set(fid_comp.values()))            
                if self.dlg.stylingCheckBox.isChecked():
                    aLayer.beginEditCommand("Update layer styling")
                    categories = []
                    firstCat = True
                    for cat in groups:
                        symbol = QgsSymbol.defaultSymbol(aLayer.geometryType())
                        symbol.setColor(QColor(randint(0,255), randint(0,255), randint(0,255)))
                        if firstCat:
                            firstCat = False
                        else:
                            symbol.setWidth(symbol.width()*5)
                        category = QgsRendererCategory(cat, symbol, "%d" % cat)
                        categories.append(category)

                    field = self.dlg.attributeNameEditBox.text()
                    renderer = QgsCategorizedSymbolRenderer(field, categories)
                    aLayer.setRenderer(renderer)

#                    if self.iface.mapCanvas().isCachingEnabled():
#                        aLayer.setCacheImage(None)
#                    else:
#                        self.iface.mapCanvas().refresh()
                    aLayer.triggerRepaint()
                    aLayer.endEditCommand()            
                   
                self.iface.messageBar().clearWidgets()   
                self.iface.messageBar().pushMessage("Found main network and %d disconnected islands in layer %s" % (len(groups)-1, aLayer.name()),  level=Qgis.Success)

                aLayer.commitChanges()
#                if not previousEditingMode: 
    
            except Exception as e:
                self.iface.messageBar().pushMessage("Error", "Exception caught: %s.  Please report an issue to the author of the plugin." % repr(e), level=Qgis.Critical)
                