class Progress:
    progress_func = None

    @classmethod
    def set(cls, pourcentage: int, step_id: str, message: str):
        """Set progression during IFC import
        Pourcentage: is x as in x/100.
        step_id: step name which can be interpretable as an id for translation
        message: is a free string message"""
        if cls.progress_func:
            cls.progress_func(pourcentage, step_id, message)
