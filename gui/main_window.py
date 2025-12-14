# gui/main_window.py

from PyQt5.QtWidgets import (QWidget, QFrame, QPushButton,
                             QFormLayout, QLabel, QSpinBox)
from PyQt5.QtGui import QFont, QColor, QPalette, QPainter
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene

from gui.items import PlaceItem, TransitionItem, ArcItem

class Mode:
    # Classe pour les différents modes d'interaction dans la vue graphique
    SELECT = 0  # Outil de sélection
    ADD_PLACE = 1
    ADD_TRANSITION = 2
    ADD_ARC = 3


class PetriGraphicsView(QGraphicsView):
    # Classe pour la vue graphique du réseau de Petri, gère les interactions utilisateur
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setSceneRect(0, 0, 1000, 1000)
        self.setRenderHints(QPainter.Antialiasing)
        self.current_mode = Mode.SELECT
        self.temp_arc_start = None

    # Définit le mode d'ajout (place, transition, arc)
    def set_mode(self, mode):
        self.mode = mode
        self.temp_arc_start = None

    # Gère les clics de souris pour ajouter des éléments ou sélectionner
    def mousePressEvent(self, event):
        pos = self.mapToScene(event.pos())
        item_under_mouse = self.scene.itemAt(pos, self.transform())

        if event.button() == Qt.LeftButton:
            if self.mode == 'place':
                # create backend place via controller
                backend_p = self.main_window.create_place_at(pos.x(), pos.y())
                self.main_window.update_properties(backend_p['item'])
            elif self.mode == 'transition':
                backend_t = self.main_window.create_transition_at(pos.x(), pos.y())
                self.main_window.update_properties(backend_t['item'])
            elif self.mode == 'arc':
                if isinstance(item_under_mouse, (PlaceItem, TransitionItem)):
                    if self.temp_arc_start is None:
                        self.temp_arc_start = item_under_mouse
                    else:
                        start = self.temp_arc_start
                        end = item_under_mouse
                        if type(start) != type(end):
                            # delegate to controller so backend arc is created
                            arc_info = self.main_window.create_arc_between(start, end)
                            if arc_info:
                                self.scene.addItem(arc_info['visual'])
                                start.add_arc(arc_info['visual'])
                                end.add_arc(arc_info['visual'])
                                self.main_window.update_properties(arc_info['visual'])
                        self.temp_arc_start = None
                else:
                    self.temp_arc_start = None

            # selection
            if item_under_mouse:
                # if clicked on a token dot or text, lift to parent
                parent = item_under_mouse.parentItem()
                if parent and isinstance(parent, (PlaceItem, TransitionItem)):
                    item_under_mouse = parent
                self.main_window.update_properties(item_under_mouse)
            else:
                self.main_window.clear_properties()

        super().mousePressEvent(event)


class MainWindow(QWidget):
    def __init__(self, petri_net, simulation):
        super().__init__()
        self.net = petri_net
        self.sim = simulation

        self.initUI()

    def initUI(self):
        self.setGeometry(100, 100, 1020, 650)
        self.setWindowTitle("Petri Editor (integrated)")

        # Buttons frame
        self.frame_button = QFrame(self)
        self.frame_button.setGeometry(720, 20, 280, 250)
        self.frame_button.setStyleSheet("background-color: #FFD166; border-radius: 10px;")

        self.buttonPlace = QPushButton("Add Place", self.frame_button)
        buttonPlace_font = QFont("Futura", 12)
        self.buttonPlace.setFont(buttonPlace_font)
        self.buttonPlace.setStyleSheet("background-color: #EF476F; border-radius: 10px;")
        self.buttonPlace.setGeometry(20, 20, 240, 40)

        self.buttonTransition = QPushButton("Add Transition", self.frame_button)
        buttonTransition_font = QFont("Futura", 12)
        self.buttonTransition.setFont(buttonTransition_font)
        self.buttonTransition.setStyleSheet("background-color: #EF476F; border-radius: 10px;")
        self.buttonTransition.setGeometry(20, 80, 240, 40)

        self.buttonArc = QPushButton("Add Arc", self.frame_button)
        self.buttonArc.setGeometry(20, 140, 240, 40)
        buttonArc_font = QFont("Futura", 12)
        self.buttonArc.setFont(buttonArc_font)
        self.buttonArc.setStyleSheet("background-color: #EF476F; border-radius: 10px;")

        # Info frame
        self.frame_info = QFrame(self)
        self.frame_info.setGeometry(720, 290, 280, 300)
        self.frame_info.setStyleSheet("background-color: #5393CA; border-radius: 10px;")
        self.info_layout = QFormLayout(self.frame_info)

        # view
        self.view = PetriGraphicsView(self)
        self.view.setParent(self)
        self.view.setGeometry(20, 20, 680, 760)

        # connect buttons
        self.buttonPlace.clicked.connect(lambda: self.view.set_mode('place'))
        self.buttonTransition.clicked.connect(lambda: self.view.set_mode('transition'))
        self.buttonArc.clicked.connect(lambda: self.view.set_mode('arc'))

        # mapping visual->backend: store dict name->item
        self.visual_places = {}   # name -> PlaceItem
        self.visual_transitions = {}
        self.visual_arcs = []     # list of ArcItem

    # ------- Controller methods (bridge GUI <-> backend) -------
    def create_place_at(self, x, y):
        # create backend place then visual
        backend_place = self.net.add_place()
        backend_place.initial_tokens = 0
        backend_place.tokens = 0
        item = PlaceItem(x, y, name=backend_place.name)
        self.view.scene.addItem(item)
        self.visual_places[backend_place.name] = item
        return {'backend': backend_place, 'item': item}

    def create_transition_at(self, x, y):
        backend_t = self.net.add_transition()
        item = TransitionItem(x, y, name=backend_t.name)
        self.view.scene.addItem(item)
        self.visual_transitions[backend_t.name] = item
        return {'backend': backend_t, 'item': item}

    def create_arc_between(self, start_item, end_item):
        # determine names for add_arc
        a = start_item.name
        b = end_item.name
        # call backend add_arc. It infers direction
        try:
            arc_backend = self.net.add_arc(a, b)
        except Exception as e:
            print("Arc creation failed:", e)
            return None

        # create visual arc
        visual = ArcItem(start_item, end_item, weight=arc_backend.weight)
        self.view.scene.addItem(visual)
        # link visual to nodes
        start_item.add_arc(visual)
        end_item.add_arc(visual)
        self.visual_arcs.append(visual)
        return {'backend': arc_backend, 'visual': visual}

    # properties panel
    def clear_properties(self):
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def delete_item(self, item):
        if isinstance(item, (PlaceItem, TransitionItem)):
            # remove backend object too
            name = item.name
            if isinstance(item, PlaceItem):
                self.net.delete_place(name)
                self.visual_places.pop(name, None)
            else:
                self.net.delete_transition(name)
                self.visual_transitions.pop(name, None)

            for arc in item.arcs[:]:
                self.view.scene.removeItem(arc)
                other = arc.start_item if arc.start_item != item else arc.end_item
                other.remove_arc(arc)
            self.view.scene.removeItem(item)

        elif isinstance(item, ArcItem):
            # remove backend arc: find arc by matching endpoints and direction
            a = item.start_item.name
            b = item.end_item.name
            # try remove both direction possibilities
            self.net.delete_arc = getattr(self.net, 'delete_arc', None)
            # our backend doesn't have delete_arc implemented as public; simple approach:
            # remove matching arcs in net.arcs manually:
            place = None
            trans = None
            if a in self.visual_places:
                place_name = a; trans_name = b
            elif b in self.visual_places:
                place_name = b; trans_name = a
            else:
                place_name = None; trans_name = None
            if place_name and trans_name:
                # remove arcs that match either direction
                new_arcs = []
                for arc in self.net.arcs:
                    if not ((arc.place.name == place_name and arc.transition.name == trans_name) or
                            (arc.place.name == place_name and arc.transition.name == trans_name)):
                        new_arcs.append(arc)
                self.net.arcs = new_arcs

            item.start_item.remove_arc(item)
            item.end_item.remove_arc(item)
            self.view.scene.removeItem(item)

        self.clear_properties()
        self.view.scene.update()

    def update_properties(self, item):
        self.clear_properties()
        lbl_title = QLabel("Propriétés")
        lbl_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        lbl_title_font = QFont("Futura", 12)
        lbl_title.setFont(lbl_title_font)
        palette = lbl_title.palette()
        palette.setColor(QPalette.WindowText, QColor("#FFFFFF"))
        lbl_title.setPalette(palette)
        self.info_layout.addRow(lbl_title)

        if isinstance(item, PlaceItem):
            self.info_layout.addRow(QLabel(f"Type: Place ({item.name})"))
            spin_tokens = QSpinBox()
            spin_tokens.setRange(0, 99)
            # backend token value:
            backend_p = self.net.places.get(item.name)
            spin_tokens.setValue(backend_p.tokens if backend_p else item.tokens)
            def on_token_change(v):
                # update backend then visual
                self.net.set_tokens(item.name, v)
                item.set_tokens(v)
            spin_tokens.valueChanged.connect(on_token_change)
            self.info_layout.addRow("Jetons :", spin_tokens)

        elif isinstance(item, TransitionItem):
            self.info_layout.addRow(QLabel(f"Type: Transition ({item.name})"))

        elif isinstance(item, ArcItem):
            self.info_layout.addRow(QLabel("Type: Arc"))
            spin_weight = QSpinBox()
            spin_weight.setRange(1, 999)
            spin_weight.setValue(item.weight)
            def on_weight_change(v):
                item.set_weight(v)
                # update backend arc weight
                # find the backend arc and update
                for arc in self.net.arcs:
                    if arc.place.name == item.start_item.name and arc.transition.name == item.end_item.name:
                        arc.weight = v
                        break
                    if arc.place.name == item.end_item.name and arc.transition.name == item.start_item.name:
                        arc.weight = v
                        break
            spin_weight.valueChanged.connect(on_weight_change)
            self.info_layout.addRow("Poids :", spin_weight)

        btn_delete = QPushButton("Supprimer")
        btn_delete.setStyleSheet("background-color: #ffcccc; color: red; font-weight: bold; border-radius: 5px;")
        btn_delete.clicked.connect(lambda: self.delete_item(item))
        self.info_layout.addRow(btn_delete)