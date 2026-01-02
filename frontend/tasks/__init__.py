"""
Task Management Module
======================

Componentes para el control y visualización de tareas de vectorización.
"""

from .mock_data import generate_mock_assets
from .matrix_view import render_task_matrix, render_dispatch_button
from .sidecar_viewer import render_sidecar_sidebar

__all__ = ['generate_mock_assets', 'render_task_matrix', 'render_dispatch_button', 'render_sidecar_sidebar']
