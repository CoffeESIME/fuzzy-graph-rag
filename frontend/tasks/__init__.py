"""
Task Management Module
======================

Componentes para el control y visualización de tareas de vectorización.
"""


from .matrix_view import render_task_matrix, render_dispatch_button, render_task_status_summary
from .sidecar_viewer import render_sidecar_sidebar

__all__ = ['render_task_matrix', 'render_dispatch_button', 'render_task_status_summary', 'render_sidecar_sidebar']
