"""
PLotting utilities for epndb.
"""

import numpy as np
import plotly.graph_objects as go

from typing import List, Optional
from numpy import ndarray as Array


def lines(
    data: Array,
    labels: List[str],
    baseline: bool = True,
    normalise: bool = False,
    title: Optional[str] = None,
) -> go.Figure:

    """
    PLot multiple lines with tooltips via Plotly.
    """

    if data.ndim == 1:
        data = np.asarray([data])
    if len(data) != len(labels):
        raise ValueError("Number of columns and labels are different.")

    fig = go.Figure()
    for label, y in zip(labels, data):
        N = y.size
        x = np.arange(N)
        x -= y.argmax()
        y /= y.max() if normalise else 1.0
        y -= np.median(y) if baseline else 0.0
        line = go.Scatter(x=x, y=y, name=label)
        fig.add_trace(line)
    fig.update_traces(hovertemplate=None)

    fig.update_layout(
        # Titles.
        title=title,
        xaxis_title="Peak Offset",
        yaxis_title=("Normalised " if normalise else "") + "Flux Density",
        # Theme.
        template="plotly_dark",
        # Font properties.
        font_size=20,
        font_color="white",
        font_family="Spectral",
        title_font_color="goldenrod",
        title_font_family="Spectral SC",
        # Hover label properties.
        hovermode="x",
        hoverlabel=dict(
            font_size=16,
            bgcolor="black",
            font_color="white",
            font_family="Spectral",
        ),
    )
    return fig
