"""A rubric with the four sections a published version must have."""


def rubric(tag: str = "v1") -> str:
    """A valid rubric whose every section names `tag`, to tell versions apart."""
    return (
        f"# Wymogi {tag}\n\n"
        f"## Elementy pracy\nWstęp z celem ({tag}).\n\n"
        f"## Wymogi formalne\nObjętość sugerowana ({tag}).\n\n"
        f"## Co praca ma wykazać\nLogiczny tok wywodu ({tag}).\n\n"
        f"## Waga uchybień\nCRITICAL: brak wstępu ({tag}).\n"
    )
