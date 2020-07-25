from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2 import QtWidgets, QtCore, QtGui
import sys
from functools import partial
from math import sqrt
from os import path
import json
from copy import deepcopy
from style_sheet import STYLE


VERSION = "0.0.1"


def normalize(vector):
    if vector.x() + vector.y() != 0:
        kn = 1/sqrt(pow(vector.x(), 2) + pow(vector.y(), 2))
    else:
        kn = 1
    return QtCore.QPointF(vector.x() * kn, vector.y() * kn)


def vec_length(vector):
    if vector.x() + vector.y() != 0:
        return sqrt(pow(vector.x(), 2) + pow(vector.y(), 2))
    else:
        return 1


def delete_instance(name):
    name.setVisible(False)
    name.setParentItem(None)


def get_node_info(item, relative=False, viewer=None):
    node_out = {}
    outputs = {}
    if isinstance(item, Node):
        for node, con in item.outputs.items():
            outputs[str(node.id)] = con.inputIndex
        node_out["type"] = item.answer_type
        node_out["pos"] = (item.scenePos().x(), item.scenePos().y())
        if relative:
            center = viewer.mapToScene(QtCore.QPoint(int(viewer.width() / 2), int(viewer.height() / 2)))
            pos = item.scenePos()
            pos = pos - center
            node_out["pos"] = (pos.x(), pos.y())
        node_out["wh"] = (item.w, item.h)
        node_out["root"] = item.root
        node_out["question"] = item.question
        node_out["focus_answer"] = item.focus_answer
        node_out["options"] = deepcopy(item.options)
        node_out["answers"] = deepcopy(item.answers)
        node_out["outputs"] = deepcopy(outputs)
    return node_out


def create_node(type_name, parent, scene, viewer):
    if type_name == "choice":
        box = Choice(parent=parent, scene=scene, viewer=viewer)
    elif type_name == "str_input":
        box = StrInput(parent=parent, scene=scene, viewer=viewer)
    elif type_name == "grade":
        box = Grade(parent=parent, scene=scene, viewer=viewer)
    elif type_name == "checkbox":
        box = CheckBox(parent=parent, scene=scene, viewer=viewer)
    else:
        return
    scene.addItem(box)

    box.setPos(viewer.mapToScene(QtCore.QPoint(viewer.width() / 2, viewer.height() / 2)))
    return box


class Connection(QtWidgets.QGraphicsLineItem):
    def __init__(self, line, parent=None):
        super(Connection, self).__init__(line, parent=parent)
        self.parent = parent
        self.pen = QPen()
        self.pen.setWidth(2)
        self.pen.setCapStyle(Qt.RoundCap)
        self.pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(self.pen)
        self.inputNode = None
        self.outputNode = None
        self.inputIndex = None
        self.outputIndex = None
        # self.ItemIsSelectable = False
        # self.ItemIsFocusable = False
        # self.setVisible(False)
        # self.setEnabled(False)
        # self.setLine(QLineF(QPointF(), QPointF()))

    def set_input_pos(self, pos):
        line = self.line()
        line.setP1(pos)
        self.setLine(line)
        return line

    def set_output_pos(self, pos):
        line = self.line()
        line.setP2(pos)
        self.setLine(line)
        return line

    def set_pos(self, p1, p2):
        line = QtCore.QLineF(p1, p2)
        self.setLine(line)
        return line

    def update_pos(self):
        dot1 = self.inputNode.answers_dot[self.inputIndex].get_global_center()
        dot1 = self.mapFromScene(dot1)
        dot2 = self.outputNode.input_dot.get_global_center()
        dot2 = self.mapFromScene(dot2)
        p1 = QtCore.QPointF(dot1)
        p2 = QtCore.QPointF(dot2)
        # print(p1, p2)
        line = QtCore.QLineF(p1, p2)
        self.setLine(line)


class Dot(QtWidgets.QGraphicsEllipseItem):
    def __init__(self, rect, parent=None):
        super(Dot, self).__init__(rect, parent=parent)
        self.parent = parent
        self.scene = parent.scene
        self.viewer = parent.viewer
        self.pen = self.parent.pen
        self.pen.setColor(QtGui.QColor(0, 0, 0, 255))
        self.setPen(self.pen)

        self.draw_line = False
        self.line = None
        # 0 = input, 1 = output
        self.is_output = 0

    def mousePressEvent(self, event):
        # gpos = self.mapToScene(self.pos())
        self.line = Connection(QLineF(self.get_center(), self.pos()), self)
        self.draw_line = True

    def mouseMoveEvent(self, event):
        if self.draw_line:
            direction = normalize(event.pos() - self.get_center())
            dist = vec_length(event.pos() - self.get_center())
            endpoint = self.get_center() + direction * (dist * 0.9)
            self.line.set_pos(self.get_center(), endpoint)

    def mouseReleaseEvent(self, event):
        self.draw_line = False
        item = self.scene.itemAt(event.scenePos(), self.viewer.transform())
        if item and ((isinstance(item, Dot) and self.is_output == 1 and item.is_output == 0) or
                     isinstance(item, QtWidgets.QGraphicsTextItem)):
            # node.add_connection(is_connection_input, connection, node, input_id, output_id)
            self.parent.add_connection(1, self.line, item.parent, self.get_output_id(), 0)
        elif item and isinstance(item, Dot) and self.is_output == 0 and item.is_output == 1:
            # Question dot connecting to answer dot
            self.parent.add_connection(0, self.line, item.parent, item.get_output_id(), 0)
        elif item and isinstance(item, Node) and self.is_output == 1:
            # Brute force connect to question dot
            # node.add_connection(is_connection_input, connection, node, input_id, output_id)
            self.parent.add_connection(1, self.line, item, self.get_output_id(), 0)
        else:
            delete_instance(self.line)
        # Remove input connection
        if not item and self.is_output == 0:
            self.parent.remove_input_connection()

    def get_output_id(self):
        if self.is_output:
            if self in self.parent.answers_dot:
                return self.parent.answers_dot.index(self)
        return 0

    def get_center(self):
        rect = self.boundingRect()
        center = QtCore.QPointF(rect.x() + rect.width() / 2, rect.y() + rect.height() / 2)
        # center = self.mapToScene(center)
        return center

    def get_global_center(self):
        rect = self.boundingRect()
        center = QtCore.QPointF(rect.x() + rect.width() / 2, rect.y() + rect.height() / 2)
        center = self.mapToScene(center)
        return center


class Node(QtWidgets.QGraphicsRectItem):
    def __init__(self, x=0, y=0, parent=None, scene=None, viewer=None):
        # QPainterPath
        # roundRectPath;
        # roundRectPath.moveTo(80.0, 35.0);
        # roundRectPath.arcTo(70.0, 30.0, 10.0, 10.0, 0.0, 90.0);
        # roundRectPath.lineTo(25.0, 30.0);
        # roundRectPath.arcTo(20.0, 30.0, 10.0, 10.0, 90.0, 90.0);
        # roundRectPath.lineTo(20.0, 65.0);
        # roundRectPath.arcTo(20.0, 60.0, 10.0, 10.0, 180.0, 90.0);
        # roundRectPath.lineTo(75.0, 70.0);
        # roundRectPath.arcTo(70.0, 60.0, 10.0, 10.0, 270.0, 90.0);
        # roundRectPath.closeSubpath();
        super(Node, self).__init__()
        self.parent = parent
        self.scene = scene
        self.viewer = viewer
        self.id = self.scene.get_node_id()
        self.w = 200
        self.h = 80
        self.line_inc = 30
        self.options = {}
        self.focus_answer = None
        self.answers_item = []
        self.answers = []
        self.answers_dot = []
        self.init_pos(x, y)
        self.offset = QPointF(0, 0)
        self.drag = False
        self.root = False
        self.question_item = QtWidgets.QGraphicsTextItem(parent=self)
        self.question_item.parent = self
        self.question = "Question"
        self.question_item.setPlainText(self.question)
        self.question_item.setTextWidth(self.w - 10)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsSelectable)
        # inputs = {Node: Connection, Node: Connection,}
        self.inputs = {}
        # outputs = {Node: Connection, Node: Connection,}
        self.outputs = {}

        # node style
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.SolidPattern)
        self.brush.setColor(QtGui.QColor(230, 233, 235, 220))
        self.pen = QPen()
        self.pen.setWidth(3)
        self.pen.setCapStyle(Qt.RoundCap)
        self.pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(self.pen)
        self.setBrush(self.brush)

        # question dot
        self.input_dot = Dot(QRect(0, 0, 10, 10), parent=self)
        self.input_dot.setPos(QPointF(-9, 6))

    def init_pos(self, x, y):
        self.setRect(x, y, self.w, self.h)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.drag = True

    def mouseMoveEvent(self, event):
        for node in self.inputs:
            self.inputs[node].update_pos()
        for node in self.outputs:
            self.outputs[node].update_pos()
        super(Node, self).mouseMoveEvent(event)

    def mouse_move(self, event):
        pos = event.scenePos()
        self.setPos(self.offset + pos)

    def delete_node(self):
        # delete input
        for answer in self.answers:
            self.remove_answer(answer)
        # delete outputs
        self.remove_input_connection()
        # delete self
        delete_instance(self)

    def set_root(self, check):
        self.root = check
        if check:
            self.pen.setColor(QtGui.QColor(230, 100, 100, 255))
            self.setPen(self.pen)
        else:
            self.pen.setColor(QtGui.QColor(0, 0, 0, 255))
            self.setPen(self.pen)

    def add_connection(self, is_connection_input, connection, node, input_id, output_id):
        if is_connection_input:
            if self.outputs.get(node):
                delete_instance(self.outputs[node])
            if node.inputs:
                delete_instance(list(node.inputs.values())[0])
            node.inputs = {self: connection}
            self.outputs[node] = connection
            connection.inputNode = self
            connection.outputNode = node
            connection.inputIndex = input_id
            connection.outputIndex = output_id
            connection.update_pos()
        else:
            if self.inputs:
                delete_instance(list(self.inputs.values())[0])
            if node.outputs.get(self):
                delete_instance(node.outputs[self])
            self.inputs = {node: connection}
            node.outputs[self] = connection
            connection.inputNode = node
            connection.outputNode = self
            connection.inputIndex = input_id
            connection.outputIndex = output_id
            connection.update_pos()

    def set_offset(self, event):
        self.offset = self.scenePos() - event.scenePos()

    def get_question(self):
        return self.question

    def set_question(self, question):
        self.question = question
        if len(question) > self.w * 0.3 - 30:
            self.question_item.setPlainText(question[:int(self.w * 0.3 - 30)] + "...")
        else:
            self.question_item.setPlainText(question)

    def add_answer(self, answer):
        self.focus_answer = len(self.answers)
        text_item = QtWidgets.QGraphicsTextItem(parent=self)
        text_item.parent = self
        text_item.setPlainText("{} - {}".format(len(self.answers) + 1, answer))
        text_item.setTextWidth(self.w - 10)
        posy = 30 + (len(self.answers_item)) * 30
        text_item.setPos(0, posy)
        self.answers_item.append(text_item)
        self.answers.append(answer)
        # Dot
        dot = Dot(QRect(0, 0, 10, 10), parent=self)
        dot.is_output = 1
        dot.setPos(QPointF(self.w, posy + 6))
        self.answers_dot.append(dot)
        self.h += self.line_inc
        self.init_pos(0, 0)

    def remove_answer(self, answer):
        """Remove an answer and it's dot.
        Will replace the other answer in the list."""
        if answer in self.answers:
            index = self.answers.index(answer)
            connections = self.remove_output_connection(index)
            delete_instance(self.answers_item[index])
            delete_instance(self.answers_dot[index])
            self.answers.pop(index)
            self.answers_item.pop(index)
            self.answers_dot.pop(index)
            self.replace_answer_pos()
            self.h -= self.line_inc
            self.init_pos(0, 0)
            for connection in connections:
                connection.update_pos()
            if self.focus_answer == index:
                if len(self.answers):
                    self.focus_answer = 0
                else:
                    self.focus_answer = None

    def remove_output_connection(self, index):
        """Delete the connection from an answer id.
        Will return any connection with greaterindex to be repllaced."""
        connections = []
        out_nodes = []
        for node, connection in self.outputs.items():
            if connection.inputIndex == index:
                connection.outputNode.inputs = {}
                out_nodes.append(connection.outputNode)
                delete_instance(connection)
            if connection.inputIndex > index:
                connection.inputIndex -= 1
                connection.update_pos()
                connections.append(connection)
        for node in out_nodes:
            self.outputs.pop(node)
        return connections

    def remove_input_connection(self):
        if self.inputs:
            connection = list(self.inputs.values())[0]
            node = list(self.inputs.keys())[0]
            node.outputs.pop(self)
            delete_instance(connection)
        self.inputs = {}

    def replace_answer_pos(self):
        for i, answer_item in enumerate(self.answers_item):
            posy = 30 + (i * 30)
            answer_item.setPos(0, posy)
            # dot pos
            dot_pos = QPointF(self.w, posy + 6)
            self.answers_dot[i].setPos(dot_pos)

    def redraw_answers(self):
        for i, answer in enumerate(self.answers):
            self.set_answer_on_item(i, answer)

    def get_answer_text(self, number):
        if number < len(self.answers):
            return self.answers[number]
        return ""

    def get_answer_item(self, number):
        if number < len(self.answers_item):
            return self.answers_item[number]
        return

    def set_answer_on_item(self, number, answer):
        self.answers[number] = answer
        if len(answer) > self.w * 0.3 - 40:
            self.get_answer_item(number).setPlainText("{} - {}...".format(number + 1, answer[:int(self.w * 0.3 - 40)]))
        else:
            self.get_answer_item(number).setPlainText("{} - {}".format(number + 1, answer))

    def get_focus_answer(self):
        if len(self.answers) and self.focus_answer < len(self.answers):
            return self.focus_answer
        elif len(self.answers):
            self.focus_answer = 0
            return self.focus_answer
        return None

    def set_focus_answer(self, focus_number):
        if len(self.answers) and focus_number < len(self.answers):
            self.focus_answer = focus_number
            return focus_number
        elif len(self.answers):
            self.focus_answer = 0
            return self.focus_answer
        return None


class Choice(Node):
    def __init__(self, parent=None, scene=None, viewer=None):
        super(Choice, self).__init__(parent=parent, scene=scene, viewer=viewer)
        self.answer_type = "choice"
        self.add_answer("Oui")
        self.add_answer("Non")
        self.brush.setColor(QtGui.QColor(245, 210, 205, 220))
        self.setBrush(self.brush)


class StrInput(Node):
    def __init__(self, parent=None, scene=None, viewer=None):
        super(StrInput, self).__init__(parent=parent, scene=scene, viewer=viewer)
        self.answer_type = "str_input"
        super(StrInput, self).add_answer("Answer")
        # Number of line for the text
        self.size = 5
        self.brush.setColor(QtGui.QColor(245, 245, 212, 220))
        self.setBrush(self.brush)
        self.options['size'] = self.size

    def add_answer(self, answer):
        pass

    def remove_answer(self, answer):
        pass


class CheckBox(Node):
    def __init__(self, parent=None, scene=None, viewer=None):
        super(CheckBox, self).__init__(parent=parent, scene=scene, viewer=viewer)
        self.answer_type = "checkbox"
        self.brush.setColor(QtGui.QColor(230, 222, 245, 220))
        self.setBrush(self.brush)


class Grade(Node):
    def __init__(self, parent=None, scene=None, viewer=None):
        super(Grade, self).__init__(parent=parent, scene=scene, viewer=viewer)
        self.answer_type = "grade"
        # Grade x, y, z where x is start, y is end, z is step default is 1, 10, 1
        self.grade = [1, 10, 1]
        # Comments are meant to be start comment, end comment to explain what the lowest and highest values mean
        self.comments = ["", ""]
        super(Grade, self).add_answer("Can still trigger new question")
        self.brush.setColor(QtGui.QColor(222, 242, 236, 220))
        self.setBrush(self.brush)
        self.options['grade'] = self.grade
        self.options['comments'] = self.comments

    def add_answer(self, answer):
        pass

    def remove_answer(self, answer):
        pass


class Options(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(Options, self).__init__()
        self.parent = parent
        self.setTitle("Options")
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.current_widgets = []

        # Choice options

        # StrInput options
        self.size_option = None
        self.size_option_label = None

        # Checkbox options

        # Grade options
        self.grade_option_label = None
        self.grade_min_option = None
        self.grade_max_option = None
        self.grade_step_option = None
        self.comments_option_label = None
        self.comments_min_option = None
        self.comments_max_option = None

    def add_options(self, item):
        if isinstance(item, StrInput):
            self.size_option = QtWidgets.QLineEdit()
            v = QIntValidator(1, 10)
            self.size_option.setValidator(v)
            self.size_option_label = QtWidgets.QLabel("Size :")

            self.layout.addWidget(self.size_option_label, 0, 1)
            self.layout.addWidget(self.size_option, 1, 1)
            self.size_option.textEdited.connect(partial(self.update_field, item=item, field="size"))
            self.size_option.setText(str(item.options['size']))
            self.current_widgets.append(self.size_option_label)
            self.current_widgets.append(self.size_option)
        elif isinstance(item, Grade):
            self.grade_option_label = QtWidgets.QLabel("Min, max, step :")
            self.grade_min_option = QtWidgets.QLineEdit()
            v = QIntValidator(-1000, 1000)
            self.grade_min_option.setValidator(v)
            self.grade_min_option.textEdited.connect(partial(self.update_field, item=item, field="grade_min"))
            self.grade_max_option = QtWidgets.QLineEdit()
            self.grade_max_option.setValidator(v)
            self.grade_max_option.textEdited.connect(partial(self.update_field, item=item, field="grade_max"))
            self.grade_step_option = QtWidgets.QLineEdit()
            self.grade_step_option.setValidator(v)
            self.grade_step_option.textEdited.connect(partial(self.update_field, item=item, field="grade_step"))
            self.comments_option_label = QtWidgets.QLabel("Comments for min, max :")
            self.comments_min_option = QtWidgets.QLineEdit()
            self.comments_min_option.textEdited.connect(partial(self.update_field, item=item, field="comment_min"))
            self.comments_max_option = QtWidgets.QLineEdit()
            self.comments_max_option.textEdited.connect(partial(self.update_field, item=item, field="comment_max"))

            self.grade_min_option.setText(str(item.options['grade'][0]))
            self.grade_max_option.setText(str(item.options['grade'][1]))
            self.grade_step_option.setText(str(item.options['grade'][2]))
            self.comments_min_option.setText(str(item.options['comments'][0]))
            self.comments_max_option.setText(str(item.options['comments'][1]))

            self.layout.addWidget(self.grade_option_label, 0, 0)
            self.layout.addWidget(self.grade_min_option, 1, 0)
            self.layout.addWidget(self.grade_max_option, 1, 1)
            self.layout.addWidget(self.grade_step_option, 1, 2)
            self.layout.addWidget(self.comments_option_label, 2, 0)
            self.layout.addWidget(self.comments_min_option, 3, 0)
            self.layout.addWidget(self.comments_max_option, 3, 1)
            self.current_widgets.append(self.grade_option_label)
            self.current_widgets.append(self.grade_min_option)
            self.current_widgets.append(self.grade_max_option)
            self.current_widgets.append(self.grade_step_option)
            self.current_widgets.append(self.comments_option_label)
            self.current_widgets.append(self.comments_min_option)
            self.current_widgets.append(self.comments_max_option)

    def update_field(self, event, item=None, field=""):
        # print(item, field)
        if field == "size":
            item.options['size'] = self.size_option.text()
        elif field == "grade_min":
            item.options['grade'][0] = self.grade_min_option.text()
        elif field == "grade_max":
            item.options['grade'][1] = self.grade_max_option.text()
        elif field == "grade_step":
            item.options['grade'][2] = self.grade_step_option.text()
        elif field == "comment_min":
            item.options['comments'][0] = self.comments_min_option.text()
        elif field == "comment_max":
            item.options['comments'][1] = self.comments_max_option.text()

    def empty(self):
        for i in self.current_widgets:
            self.layout.removeWidget(i)
            i.deleteLater()
        self.current_widgets = []


class TopBar(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(TopBar, self).__init__()
        self.parent = parent
        self.setTitle("Top Bar")
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.scene = None
        self.viewer = None
        # self.focused_answer = 0
        # Question Menu
        self.question_bar = QtWidgets.QMenuBar(parent=self)
        self.question_menu = QtWidgets.QMenu("Question")
        self.set_root_btn = self.question_menu.addAction("Set Root")
        self.unset_root_btn = self.question_menu.addAction("UnSet Root")
        self.set_root_btn.triggered.connect(self.set_root)
        self.unset_root_btn.triggered.connect(self.unset_root)
        self.question_bar.addMenu(self.question_menu)
        # Answer Menu
        self.answers_action = []
        self.answer_bar = QtWidgets.QMenuBar(parent=self)
        self.answer_menu = QtWidgets.QMenu("Answer")
        self.add_answer_btn = self.answer_menu.addAction("Add Answer")
        self.remove_answer_btn = self.answer_menu.addAction("Remove Current Answer")
        self.answer_menu.addSeparator()
        self.add_answer_btn.triggered.connect(self.add_answer)
        self.remove_answer_btn.triggered.connect(self.remove_answer)
        self.answer_bar.addMenu(self.answer_menu)

        # Create widgets
        self.answer_label = QtWidgets.QLabel("Answer :")
        self.answer = QtWidgets.QLineEdit()
        self.answer.textEdited.connect(self.set_answer_on_item)

        self.question_label = QtWidgets.QLabel("Question :")
        self.question = QtWidgets.QLineEdit()
        self.question.textEdited.connect(self.set_question_on_item)

        self.options = Options(self)

        # add to layout
        self.layout.addWidget(self.question_bar, 0, 0)
        self.layout.addWidget(self.question_label, 1, 0)
        self.layout.addWidget(self.question, 2, 0)

        self.layout.addWidget(self.answer_bar, 0, 2)
        self.layout.addWidget(self.answer_label, 1, 2)
        self.layout.addWidget(self.answer, 2, 2)

        self.layout.addWidget(self.options, 0, 4, 4, 1)

        self.layout.setColumnStretch(0, 1)
        self.layout.setColumnStretch(2, 1)
        self.layout.setColumnStretch(4, 1)
        self.layout.setColumnMinimumWidth(1, 15)
        self.layout.setColumnMinimumWidth(3, 15)

        self.layout.setRowStretch(0, 0)
        self.layout.setRowStretch(1, 0)
        self.layout.setRowStretch(2, 0)
        self.layout.setRowStretch(3, 1)
        self.layout.setRowMinimumHeight(3, 50)

    def update(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            self.add_answer_btn.setEnabled(True)
            self.question.setText(first_item.get_question())
            self.populate_answer(first_item)
            self.focus_answer(first_item.get_focus_answer())
            self.options.add_options(first_item)
        else:
            self.add_answer_btn.setEnabled(False)
            self.question.setText("")
            self.answer.setText("")
            self.answer_label.setText("Answer :")
            self.options.empty()

    def set_question_on_item(self):
        if self.scene.selectedItems():
            self.scene.selectedItems()[0].set_question(self.question.text())

    def add_answer(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            first_item.add_answer("test")
            self.update()

    def remove_answer(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            first_item.remove_answer(self.answer.text())
            first_item.redraw_answers()
            self.update()

    def set_root(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            first_item.set_root(True)

    def unset_root(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            first_item.set_root(False)

    def populate_answer(self, item):
        for action in self.answers_action:
            self.answer_menu.removeAction(action)
        for i, answer in enumerate(item.answers):
            action = self.answer_menu.addAction("answer_{}".format(i + 1))
            action.triggered.connect(partial(self.focus_answer, i))
            self.answers_action.append(action)

    def focus_answer(self, number):
        if self.scene.selectedItems() and number is not None:
            self.answer_label.setText("Answer {}:".format(number + 1))
            first_item = self.scene.selectedItems()[0]
            focused_answer = first_item.set_focus_answer(number)
            if focused_answer is not None:
                self.answer.setText(first_item.answers[focused_answer])
            else:
                self.answer.setText("")
            # self.focused_answer = number
        else:
            self.answer.setText("")

    def set_answer_on_item(self):
        if self.scene.selectedItems():
            first_item = self.scene.selectedItems()[0]
            focused_answer = first_item.get_focus_answer()
            first_item.set_answer_on_item(focused_answer, self.answer.text())


class SideBar(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(SideBar, self).__init__()
        self.parent = parent
        self.setTitle("Side Bar")
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        self.scene = self.parent.open_space.scene
        self.viewer = self.parent.open_space.viewer

        # Space widget
        self.line = QtWidgets.QLabel("_" * 20)
        self.space = QtWidgets.QLabel(" ")

        # Create button
        self.choice_button = QtWidgets.QPushButton("Create Choice")
        self.choice_button.clicked.connect(self.create_choice)
        self.strinput_button = QtWidgets.QPushButton("Create Essay")
        self.strinput_button.clicked.connect(self.create_str_input)
        self.checkbox_button = QtWidgets.QPushButton("Create Checkbox")
        self.checkbox_button.clicked.connect(self.create_checkbox)
        self.grade_button = QtWidgets.QPushButton("Create Grade")
        self.grade_button.clicked.connect(self.create_grade)
        self.delete_button = QtWidgets.QPushButton("Delete Selected nodes")
        self.delete_button.clicked.connect(self.delete_selected)
        # add to layout
        self.layout.addWidget(QtWidgets.QLabel("Add Questions"))
        self.layout.setStretch(1, 0)
        self.layout.addWidget(self.choice_button)
        self.layout.addWidget(self.strinput_button)
        self.layout.addWidget(self.checkbox_button)
        self.layout.addWidget(self.grade_button)
        self.layout.insertSpacing(5, 30)
        self.layout.addWidget(self.delete_button)
        self.layout.addStretch(2)

    def create_choice(self):
        # print(self.viewer.mapToScene(QtCore.QPoint(self.viewer.width() / 2, self.viewer.height() / 2)))
        return create_node("choice", self, self.scene, self.viewer)

    def create_str_input(self):
        return create_node("str_input", self, self.scene, self.viewer)

    def create_checkbox(self):
        return create_node("checkbox", self, self.scene, self.viewer)

    def create_grade(self):
        return create_node("grade", self, self.scene, self.viewer)

    def delete_selected(self):
        for i in self.scene.selectedItems():
            if isinstance(i, Node):
                i.delete_node()


class Viewer(QtWidgets.QGraphicsView):
    def __init__(self, scene, parent=None):
        super(Viewer, self).__init__()
        self.parent = parent
        self.setScene(scene)
        self.scene = scene
        self.drag = False
        self.prevPos = None
        self.ctrl = False
        self.buffer = None
        self.brush = QtGui.QBrush()
        self.brush.setStyle(QtCore.Qt.SolidPattern)
        self.brush.setColor(QtGui.QColor(128, 128, 128, 255))
        self.setBackgroundBrush(self.brush)

    def keyPressEvent(self, event):
        if self.ctrl and event.key() == Qt.Key_X:
            nodes = {}
            for node in self.scene.selectedItems():
                nodes[str(node.id)] = get_node_info(node, relative=True, viewer=self)
            self.buffer = nodes
            for i in self.scene.selectedItems():
                if isinstance(i, Node):
                    i.delete_node()
            return
        if event.key() == Qt.Key_Delete:
            for i in self.scene.selectedItems():
                if isinstance(i, Node):
                    i.delete_node()
        if event.key() == Qt.Key_Control:
            self.ctrl = True
        if self.ctrl and event.key() == Qt.Key_C:
            nodes = {}
            for node in self.scene.selectedItems():
                nodes[str(node.id)] = get_node_info(node, relative=True, viewer=self)
            self.buffer = nodes
        if self.ctrl and event.key() == Qt.Key_V:
            if not self.buffer:
                return
            node_dict = {}
            for node_id in self.buffer:
                # Create proper node type
                node = create_node(self.buffer[node_id]["type"], self, self.scene, self)
                if not node:
                    print("Node type not yet implemented in open scene ({})".format(self.buffer[node_id]["type"]))
                    continue

                # Add node attributes
                node.set_root(self.buffer[node_id]["root"])
                center = self.mapToScene(QtCore.QPoint(int(self.width() / 2), int(self.height() / 2)))

                node.setPos(QPoint(self.buffer[node_id]["pos"][0] + center.x(), self.buffer[node_id]["pos"][1] + center.y()))
                node.options = self.buffer[node_id]["options"]
                node.set_question(self.buffer[node_id]["question"])
                node_dict[str(node.id)] = node
                # Add answers
                if len(node.answers) < len(self.buffer[node_id]["answers"]):
                    # Add answer
                    while len(node.answers) < len(self.buffer[node_id]["answers"]):
                        node.add_answer("")
                elif len(node.answers) > len(self.buffer[node_id]["answers"]):
                    # remove answer
                    while len(node.answers) > len(self.buffer[node_id]["answers"]):
                        node.remove_answer(node.answers[0])
                for i, answer in enumerate(self.buffer[node_id]["answers"]):
                    node.set_answer_on_item(i, answer)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.ctrl = False

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            item = self.itemAt(event.pos())
            if item and (isinstance(item, Node) or isinstance(item.parent, Node)):
                if item not in self.scene.selectedItems() and item.parent not in self.scene.selectedItems() and \
                        not self.ctrl:
                    self.scene.clearSelection()
            self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
        elif event.button() == QtCore.Qt.MiddleButton:
            self.setDragMode(QtWidgets.QGraphicsView.NoDrag)
            self.drag = True
            self.prevPos = event.pos()
            self.setCursor(QtCore.Qt.SizeAllCursor)

        super(Viewer, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.drag:
            delta = (self.mapToScene(event.pos()) - self.mapToScene(self.prevPos)) * -1.0
            center = QtCore.QPoint(int(self.viewport().width() / 2 + delta.x()),
                                   int(self.viewport().height() / 2 + delta.y()))
            new_center = self.mapToScene(center)
            self.centerOn(new_center)
            self.prevPos = event.pos()
            return
        super(Viewer, self).mouseMoveEvent(event)

    def wheelEvent(self, event):
        # print(event.angleDelta())
        in_factor = 1.25
        out_factor = 1 / in_factor
        old_pos = self.mapToScene(event.pos())
        if event.angleDelta().y() > 0:
            zoom_factor = in_factor
        else:
            zoom_factor = out_factor
        self.scale(zoom_factor, zoom_factor)
        new_pos = self.mapToScene(event.pos())
        delta = new_pos - old_pos
        self.translate(delta.x(), delta.y())
        super(Viewer, self).wheelEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            pass
        elif event.button() == QtCore.Qt.MiddleButton:
            self.setDragMode(QtWidgets.QGraphicsView.RubberBandDrag)
            self.drag = False
            self.setCursor(QtCore.Qt.ArrowCursor)
        super(Viewer, self).mouseReleaseEvent(event)


class Scene(QtWidgets.QGraphicsScene):
    def __init__(self, parent=None):
        super(Scene, self).__init__()
        self.parent = parent
        self.viewer = None
        self.top_bar = self.parent.parent.top_bar
        self.grab = False
        self.node_id = 0
        self.selectionChanged.connect(self.selection_changed)
        self.setSceneRect(0, 0, 32000, 32000)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.grab = False
        super(Scene, self).mouseReleaseEvent(event)

    def selection_changed(self):
        self.top_bar.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.itemAt(event.scenePos(), self.viewer.transform()):
                self.grab = True
                for i in self.selectedItems():
                    i.set_offset(event)
        super(Scene, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            if self.grab:
                for i in self.selectedItems():
                    i.mouse_move(event)
        super(Scene, self).mouseMoveEvent(event)

    def get_node_id(self):
        self.node_id += 1
        return self.node_id


class OpenSpace(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(OpenSpace, self).__init__()
        self.parent = parent
        self.setTitle("Node graph")
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.scene = Scene(parent=self)
        self.viewer = Viewer(self.scene, parent=self)
        self.scene.viewer = self.viewer

        # Add to layout
        self.layout.addWidget(self.viewer)


class MainLayout(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super(MainLayout, self).__init__()
        self.showMaximized()
        self.parent = parent
        self.setTitle("The Form Creator")
        # Layout
        self.layout = QtWidgets.QGridLayout()
        self.setLayout(self.layout)
        self.file_name = ""

        # add widget
        # Main menu
        self.main_menu = QtWidgets.QMenuBar(parent=self)
        self.file_menu = QtWidgets.QMenu("File")
        self.new_btn = self.file_menu.addAction("&New", self, SLOT("new()"), QKeySequence("Ctrl+N"))
        self.open_btn = self.file_menu.addAction("&Open...", self, SLOT("open()"), QKeySequence("Ctrl+O"))
        self.save_btn = self.file_menu.addAction("&Save", self, SLOT("save()"), QKeySequence("Ctrl+S"))
        self.save_as_btn = self.file_menu.addAction("Save As...")
        self.file_menu.addSeparator()
        self.quit_btn = self.file_menu.addAction("&Quit", self, SLOT("quit()"), QKeySequence("Ctrl+Q"))
        self.new_btn.triggered.connect(self.new)
        self.open_btn.triggered.connect(self.open)
        self.save_btn.triggered.connect(self.save)
        self.save_as_btn.triggered.connect(self.save_as)
        self.quit_btn.triggered.connect(self.quit)
        self.main_menu.addMenu(self.file_menu)

        self.top_bar = TopBar(parent=self)
        self.open_space = OpenSpace(parent=self)
        self.side_bar = SideBar(parent=self)
        self.top_bar.scene = self.open_space.scene
        self.top_bar.viewer = self.open_space.viewer

        # add to layout
        self.layout.addWidget(self.main_menu, 0, 0, 1, 2)
        self.layout.addWidget(self.top_bar, 1, 0, 1, 2)
        self.layout.addWidget(self.open_space, 2, 0)
        self.layout.addWidget(self.side_bar, 2, 1)

        # stretch
        self.layout.setColumnStretch(0, 1)

    def new(self):
        self.open_space.scene.clear()
        self.open_space.scene.node_id = 0

    def open(self):
        self.file_name = QtWidgets.QFileDialog.getOpenFileName(self, "Open", self.file_name, "File Name (*.node)")[0]
        if self.file_name and path.isfile(self.file_name):
            print("open : ", self.file_name)
            if path.isfile(self.file_name):
                with open(self.file_name, "r") as f:
                    json_data = json.loads(f.read())
                    if json_data:
                        nodes = json_data.get("nodes")
                        scene = json_data.get("scene")
                        self.open_space.scene.clear()
                        self.open_space.scene.node_id = int(scene.get("node_id")) if scene.get("node_id") else 0
                        node_dict = {}
                        for node_id in nodes:
                            # Create proper node type
                            node = create_node(nodes[node_id]["type"], self.open_space.viewer, self.open_space.scene,
                                               self.open_space.viewer)
                            if not node:
                                print("Node type not yet implemented in open scene ({})".format(
                                    nodes[node_id]["type"]))
                                continue
                            # Add node attributes
                            node.set_root(nodes[node_id]["root"])
                            node.id = node_id
                            node_dict[node_id] = node
                            node.setPos(QPoint(nodes[node_id]["pos"][0], nodes[node_id]["pos"][1]))
                            node.options = nodes[node_id]["options"]
                            node.set_question(nodes[node_id]["question"])
                            # Add answers
                            if len(node.answers) < len(nodes[node_id]["answers"]):
                                # Add answer
                                while len(node.answers) < len(nodes[node_id]["answers"]):
                                    node.add_answer("")
                            elif len(node.answers) > len(nodes[node_id]["answers"]):
                                # remove answer
                                while len(node.answers) > len(nodes[node_id]["answers"]):
                                    node.remove_answer(node.answers[0])
                            for i, answer in enumerate(nodes[node_id]["answers"]):
                                node.set_answer_on_item(i, answer)
                        for node_id in nodes:
                            # Connect nodes
                            for nid, aid in nodes[node_id]["outputs"].items():
                                line = Connection(QLineF(QPointF(0, 0), QPointF(0, 0)), node)
                                node = node_dict[node_id]
                                node.add_connection(1, line, node_dict[nid], aid, 0)

        else:
            print("Invalid file name to open")

    def save(self):
        if self.file_name:
            print("save")
            self.save_scene()
        else:
            self.save_as()

    def save_as(self):
        self.file_name = QtWidgets.QFileDialog.getSaveFileName(self, "Save As", self.file_name, "File Name (*.node)")[0]
        if self.file_name:
            print("Save as : ", self.file_name)
            self.save_scene()
        else:
            print("Invalid file name to save as")

    def save_scene(self):
        items = self.open_space.scene.items()
        nodes = {}
        scene = {"node_id": self.open_space.scene.node_id}
        root_list = []
        for item in items:
            if isinstance(item, Node) and item.isVisible():
                outputs = {}
                if item.root:
                    root_list.append(item.id)
                for node, con in item.outputs.items():
                    outputs[str(node.id)] = con.inputIndex

                nodes[str(item.id)] = get_node_info(item)
                for i, answer in enumerate(item.answers):
                    question_list = []
                    for node, con in item.outputs.items():
                        if con.inputIndex == i:
                            question_list.append(con.outputNode.id)

        with open(self.file_name, "w") as f:
            f.write(
                json.dumps({"VERSION": VERSION, "nodes": nodes,
                            "roots": root_list, "scene": scene}, indent=4))

    def quit(self):
        print("quit")
        self.parent.exit()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    main = MainLayout(parent=app)

    main.show()
    sys.exit(app.exec_())
