"""
Welding form generation pipeline.

Generates filled-out Excel and PDF forms from database records,
using registered templates for each form type.
"""

from qms.welding.generation.generator import generate, register_template, get_form_data
from qms.welding.generation.excel_renderer import render_excel
from qms.welding.generation.pdf_renderer import render_pdf

__all__ = [
    "generate",
    "register_template",
    "get_form_data",
    "render_excel",
    "render_pdf",
]
