class Progress:
    progress_func = None
    current_pourcentage = 0
    current_step_id = ""
    current_message = ""
    pourcent_range = 1
    len_spaces = 1
    current_space = 0

    @classmethod
    def set(
        cls,
        pourcentage: int = None,
        step_id: str = None,
        message: str = None,
        pourcent_range: int = None,
    ):
        """Set progression during IFC import
        Pourcentage: is x as in x/100.
        step_id: step name which can be interpretable as an id for translation
        message: is a free string message
        pourcent_range: used for substeps"""
        if pourcentage:
            cls.current_pourcentage = pourcentage
        else:
            pourcentage = cls.current_pourcentage + cls.space_pourcentage()
        if step_id:
            cls.current_step_id = step_id
        else:
            step_id = cls.current_step_id
        if message is None:
            message = cls.space_count()
        if pourcent_range:
            cls.pourcent_range = pourcent_range
        if cls.progress_func:
            cls.progress_func(pourcentage, step_id, message)

    @classmethod
    def next_space(cls):
        cls.current_space += 1
        return cls.current_space

    @classmethod
    def space_pourcentage(cls):
        return int(cls.current_space * cls.pourcent_range / cls.len_spaces)

    @classmethod
    def space_count(cls):
        cls.next_space()
        return f"{cls.current_space}/{cls.len_spaces}"

    @classmethod
    def new_space_count(cls):
        cls.current_space = 0
        return f"{cls.current_space}/{cls.len_spaces}"
