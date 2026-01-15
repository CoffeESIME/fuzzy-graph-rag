"""
Task Management Module
======================

Componentes para el control y visualización de tareas de vectorización.
"""


from .matrix_view import render_task_matrix, render_dispatch_button, render_task_status_summary
from .sidecar_viewer import render_sidecar_sidebar
from .task_metadata_editor import (
    render_task_metadata_editor,
    get_selected_tasks_with_metadata,
    clear_metadata_state
)
from .review_queue import render_review_queue
from .graph_generator import render_graph_generator, send_to_graph_generator

__all__ = [
    'render_task_matrix',
    'render_dispatch_button',
    'render_task_status_summary',
    'render_sidecar_sidebar',
    'render_task_metadata_editor',
    'get_selected_tasks_with_metadata',
    'clear_metadata_state',
    'render_review_queue',
    'render_graph_generator',
    'send_to_graph_generator'
]
