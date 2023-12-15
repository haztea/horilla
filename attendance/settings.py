from horilla.settings import TEMPLATES

TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "attendance.context_processors.biometric_is_installed",
)