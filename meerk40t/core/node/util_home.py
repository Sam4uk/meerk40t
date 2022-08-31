from meerk40t.core.cutcode import HomeCut
from meerk40t.core.element_types import *
from meerk40t.core.node.node import Node


class HomeOperation(Node):
    """
    HomeOperation tells the controller to perform homing.

    Node type "util home"
    """

    def __init__(self, x=0.0, y=0.0, **kwargs):
        super().__init__(type="util home", **kwargs)
        self.settings = {"x": x, "y": y, "output": True}
        self._formatter = "{enabled}{element_type} {x} {y}"

    def __repr__(self):
        return f"HomeOperation('{self.x}, {self.y}')"

    def __copy__(self):
        return HomeOperation(self.x, self.y)

    def __len__(self):
        return 1

    def validate(self):
        parameters = [
            ("output", lambda v: str(v).lower() == "true"),
            ("x", float),
            ("y", float),
        ]
        settings = self.settings
        for param, cast in parameters:
            try:
                if param in settings and settings[param] is not None:
                    settings[param] = (
                        cast(settings[param]) if settings[param] != "None" else None
                    )
            except (KeyError, ValueError):
                pass

    @property
    def x(self):
        return self.settings.get("x")

    @x.setter
    def x(self, v):
        self.settings["x"] = v

    @property
    def y(self):
        return self.settings.get("y")

    @y.setter
    def y(self, v):
        self.settings["y"] = v

    @property
    def output(self):
        return self.settings.get("output", True)

    @output.setter
    def output(self, v):
        self.settings["output"] = v

    @property
    def implicit_passes(self):
        return 1

    def default_map(self, default_map=None):
        default_map = super(HomeOperation, self).default_map(default_map=default_map)
        default_map["element_type"] = "Home"
        default_map["enabled"] = "(Disabled) " if not self.output else ""
        default_map["adjust"] = f" ({self.x}, {self.y})" if self.x != 0 and self.y != 0 else ""
        default_map["x"] = self.x
        default_map["y"] = self.y
        default_map.update(self.settings)
        return default_map

    def drop(self, drag_node, modify=True):
        drop_node = self
        if drag_node.type in op_nodes:
            if modify:
                drop_node.insert_sibling(drag_node)
            return True
        elif drop_node.type == "branch ops":
            # Dragging operation to op branch to effectively move to bottom.
            if modify:
                drop_node.append_child(drag_node)
            return True
        return False

    def load(self, settings, section):
        update_dict = settings.read_persistent_string_dict(section, suffix=True)
        self.settings.update(update_dict)
        self.validate()

    def save(self, settings, section):
        settings.write_persistent_dict(section, self.settings)

    def as_cutobjects(self, closed_distance=15, passes=1):
        """
        Generator of cutobjects for a raster operation. This takes any image node children
        and converts them into rastercut objects. These objects should have already been converted
        from vector shapes.

        The preference for raster shapes is to use the settings set on this operation rather than on the image-node.
        """
        wait = HomeCut((self.x, self.y))
        wait.original_op = self.type
        yield wait

    def generate(self):
        yield "home", self.x, self.y
