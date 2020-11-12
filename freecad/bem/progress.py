try:
    import pyCaller
except ImportError:
    pass


class Progress:
    def __init__(self):
        try:
            pyCaller
            self.is_active = True
        except NameError:
            self.is_active = False

    def set(self, pourcentage: int, step_id: str, message: str):
        """Set progression during IFC import
        Pourcentage: is x as in x/100.
        step_id: step name which can be interpretable as an id for translation
        message: is a free string message"""
        if self.is_active:
            pyCaller.SetProgress(pourcentage, step_id, message)


progress = Progress()
