from copy import copy

from meerk40t.core.cutcode import CubicCut, CutGroup, LineCut, QuadCut
from meerk40t.core.element_types import *
from meerk40t.core.node.node import Node
from meerk40t.core.parameters import Parameters
from meerk40t.core.units import UNITS_PER_MM
from meerk40t.svgelements import (
    Close,
    Color,
    CubicBezier,
    Line,
    Move,
    Path,
    Polygon,
    QuadraticBezier,
)


class EngraveOpNode(Node, Parameters):
    """
    Default object defining any operation done on the laser.

    This is a Node of type "op engrave".
    """

    def __init__(self, *args, **kwargs):
        if "setting" in kwargs:
            kwargs = kwargs["settings"]
            if "type" in kwargs:
                del kwargs["type"]
        Node.__init__(self, type="op engrave", **kwargs)
        Parameters.__init__(self, None, **kwargs)
        self._formatter = "{enabled}{pass}{element_type} {speed}mm/s @{power} {color}"
        self.settings.update(kwargs)

        if len(args) == 1:
            obj = args[0]
            if hasattr(obj, "settings"):
                self.settings = dict(obj.settings)
            elif isinstance(obj, dict):
                self.settings.update(obj)
        # We may want to add more advanced logic at a later time
        # to convert text to paths within dnd...
        self._allowed_elements_dnd = (
            "elem ellipse",
            "elem path",
            "elem polyline",
            "elem rect",
            "elem line",
            "elem dot",
        )
        # Which elements do we consider for automatic classification?
        self._allowed_elements = (
            "elem ellipse",
            "elem path",
            "elem polyline",
            "elem rect",
            "elem line",
        )
        # To which attributes does the classification color check respond
        # Can be extended / reduced by add_color_attribute / remove_color_attribute
        self.allowed_attributes = [
            "stroke",
        ]  # comma is relevant
        # Is this op out of useful bounds?
        self.dangerous = False

    def __repr__(self):
        return "EngraveOpNode()"

    def __copy__(self):
        return EngraveOpNode(self)

    @property
    def bounds(self):
        if self._bounds_dirty:
            self._bounds = Node.union_bounds(self.flat(types=elem_ref_nodes))
        return self._bounds

    # def is_dangerous(self, minpower, maxspeed):
    #     result = False
    #     if maxspeed is not None and self.speed > maxspeed:
    #         result = True
    #     if minpower is not None and self.power < minpower:
    #         result = True
    #     self.dangerous = result

    def default_map(self, default_map=None):
        default_map = super(EngraveOpNode, self).default_map(default_map=default_map)
        default_map["element_type"] = "Engrave"
        default_map["enabled"] = "(Disabled) " if not self.output else ""
        default_map["danger"] = "❌" if self.dangerous else ""
        default_map["defop"] = "✓" if self.default else ""
        default_map["pass"] = (
            f"{self.passes}X " if self.passes_custom and self.passes != 1 else ""
        )
        default_map["penpass"] = f"(p:{self.penbox_pass}) " if self.penbox_pass else ""
        default_map["penvalue"] = (
            f"(v:{self.penbox_value}) " if self.penbox_value else ""
        )
        default_map["speed"] = "default"
        default_map["power"] = "default"
        default_map["frequency"] = "default"
        ct = 0
        t = ""
        s = ""
        for cc in self.allowed_attributes:
            if len(cc) > 0:
                t += cc[0].upper()
                ct += 1
        if ct > 0:
            s = self.color.hex + "-" + t
        default_map["colcode"] = s
        default_map["opstop"] = "❌" if self.stopop else ""
        default_map.update(self.settings)
        default_map["color"] = self.color.hexrgb if self.color is not None else ""
        return default_map

    def drop(self, drag_node, modify=True):
        # Default routine for drag + drop for an op node - irrelevant for others...
        if drag_node.type.startswith("elem"):
            if not drag_node.type in self._allowed_elements_dnd:
                return False
            # Dragging element onto operation adds that element to the op.
            if modify:
                self.add_reference(drag_node, pos=0)
            return True
        elif drag_node.type == "reference":
            # Disallow drop of image refelems onto a Dot op.
            if not drag_node.node.type in self._allowed_elements_dnd:
                return False
            # Move a refelem to end of op.
            if modify:
                self.append_child(drag_node)
            return True
        elif drag_node.type in op_nodes:
            # Move operation to a different position.
            if modify:
                self.insert_sibling(drag_node)
            return True
        elif drag_node.type in ("file", "group"):
            some_nodes = False
            for e in drag_node.flat(elem_nodes):
                # Add element to operation
                if e.type in self._allowed_elements_dnd:
                    if modify:
                        self.add_reference(e)
                    some_nodes = True
            return some_nodes
        return False

    def has_color_attribute(self, attribute):
        return attribute in self.allowed_attributes

    def add_color_attribute(self, attribute):
        if not attribute in self.allowed_attributes:
            self.allowed_attributes.append(attribute)

    def remove_color_attribute(self, attribute):
        if attribute in self.allowed_attributes:
            self.allowed_attributes.remove(attribute)

    def valid_node(self, node):
        return True

    def classify(self, node, fuzzy=False, fuzzydistance=100, usedefault=False):
        def matching_color(col1, col2):
            result = False
            if col1 is None and col2 is None:
                result = True
            elif (
                col1 is not None
                and col1.argb is not None
                and col2 is not None
                and col2.argb is not None
            ):
                if fuzzy:
                    distance = Color.distance(col1, col2)
                    result = distance < fuzzydistance
                else:
                    result = col1 == col2
            return result

        if node.type in self._allowed_elements:
            if not self.default:
                if len(self.allowed_attributes) > 0:
                    for attribute in self.allowed_attributes:
                        if (
                            hasattr(node, attribute)
                            and getattr(node, attribute) is not None
                        ):
                            plain_color_op = abs(self.color)
                            plain_color_node = abs(getattr(node, attribute))
                            if matching_color(plain_color_op, plain_color_node):
                                if self.valid_node(node):
                                    self.add_reference(node)
                                # Have classified but more classification might be needed
                                return True, self.stopop
                else:  # empty ? Anything goes
                    if self.valid_node(node):
                        self.add_reference(node)
                    # Have classified but more classification might be needed
                    return True, self.stopop
            elif self.default and usedefault:
                # Have classified but more classification might be needed
                if self.valid_node(node):
                    return True, self.stopop
        return False, False

    def load(self, settings, section):
        settings.read_persistent_attributes(section, self)
        update_dict = settings.read_persistent_string_dict(section, suffix=True)
        self.settings.update(update_dict)
        self.validate()
        hexa = self.settings.get("hex_color")
        if hexa is not None:
            self.color = Color(hexa)

    def save(self, settings, section):
        settings.write_persistent_attributes(section, self)
        settings.write_persistent(section, "hex_color", self.color.hexa)
        settings.write_persistent_dict(section, self.settings)

    def copy_children(self, obj):
        for element in obj.children:
            self.add_reference(element)

    def copy_children_as_real(self, copy_node):
        for node in copy_node.children:
            self.add_node(copy(node.node))

    def time_estimate(self):
        estimate = 0
        for node in self.children:
            if node.type == "reference":
                node = node.node
            try:
                path = node.as_path()
            except AttributeError:
                continue
            length = path.length(error=1e-2, min_depth=2)
            try:
                estimate += length / (UNITS_PER_MM * self.speed)
            except ZeroDivisionError:
                estimate = float("inf")
        if self.passes_custom and self.passes != 1:
            estimate *= max(self.passes, 1)

        hours, remainder = divmod(estimate, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{int(hours)}:{str(int(minutes)).zfill(2)}:{str(int(seconds)).zfill(2)}"

    def preprocess(self, context, matrix, commands):
        """
        Preprocess hatch values

        @param context:
        @param matrix:
        @param commands:
        @return:
        """
        native_mm = abs(complex(*matrix.transform_vector([0, UNITS_PER_MM])))
        self.settings["native_mm"] = native_mm
        self.settings["native_speed"] = self.speed * native_mm
        self.settings["native_rapid_speed"] = self.rapid_speed * native_mm

    def as_cutobjects(self, closed_distance=15, passes=1):
        """Generator of cutobjects for a particular operation."""
        settings = self.derive()
        for node in self.children:
            if node.type == "reference":
                node = node.node
            if node.type == "elem image":
                object_path = node.image
                box = object_path.bbox()
                path = Path(
                    Polygon(
                        (box[0], box[1]),
                        (box[0], box[3]),
                        (box[2], box[3]),
                        (box[2], box[1]),
                    )
                )
            elif node.type == "elem path":
                path = abs(node.path)
                path.approximate_arcs_with_cubics()
            else:
                path = abs(Path(node.shape))
                path.approximate_arcs_with_cubics()
            settings["line_color"] = path.stroke
            for subpath in path.as_subpaths():
                sp = Path(subpath)
                if len(sp) == 0:
                    continue
                closed = (
                    isinstance(sp[-1], Close)
                    or abs(sp.z_point - sp.current_point) <= closed_distance
                )
                group = CutGroup(
                    None,
                    closed=closed,
                    settings=settings,
                    passes=passes,
                )
                group.path = Path(subpath)
                group.original_op = self.type
                for seg in subpath:
                    if isinstance(seg, Move):
                        pass  # Move operations are ignored.
                    elif isinstance(seg, Close):
                        if seg.start != seg.end:
                            group.append(
                                LineCut(
                                    seg.start,
                                    seg.end,
                                    settings=settings,
                                    passes=passes,
                                    parent=group,
                                )
                            )
                    elif isinstance(seg, Line):
                        if seg.start != seg.end:
                            group.append(
                                LineCut(
                                    seg.start,
                                    seg.end,
                                    settings=settings,
                                    passes=passes,
                                    parent=group,
                                )
                            )
                    elif isinstance(seg, QuadraticBezier):
                        group.append(
                            QuadCut(
                                seg.start,
                                seg.control,
                                seg.end,
                                settings=settings,
                                passes=passes,
                                parent=group,
                            )
                        )
                    elif isinstance(seg, CubicBezier):
                        group.append(
                            CubicCut(
                                seg.start,
                                seg.control1,
                                seg.control2,
                                seg.end,
                                settings=settings,
                                passes=passes,
                                parent=group,
                            )
                        )
                if len(group) > 0:
                    group[0].first = True
                for i, cut_obj in enumerate(group):
                    cut_obj.closed = closed
                    try:
                        cut_obj.next = group[i + 1]
                    except IndexError:
                        cut_obj.last = True
                        cut_obj.next = group[0]
                    cut_obj.previous = group[i - 1]
                yield group
