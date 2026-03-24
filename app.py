#!/usr/bin/env python3
"""Biotech Catalyst Tracker — Interactive Dashboard.

Run:  python app.py
Open: http://localhost:8050
"""

import os

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

import config

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_movers() -> pd.DataFrame:
    path = os.path.join(config.OUTPUT_DIR, "movers.csv")
    if not os.path.exists(path):
        return pd.DataFrame(columns=[
            "id", "date", "ticker", "company_name", "open", "close",
            "volume", "pct_change", "catalyst_type", "catalyst_confidence",
            "news_headline", "news_summary", "news_url",
        ])
    df = pd.read_csv(path, dtype={"ticker": str, "date": str})
    df["pct_change"] = pd.to_numeric(df["pct_change"], errors="coerce")
    df["catalyst_confidence"] = pd.to_numeric(df["catalyst_confidence"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    return df


def load_trends() -> pd.DataFrame:
    path = os.path.join(config.OUTPUT_DIR, "trends.csv")
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Biotech Catalyst Tracker",
    suppress_callback_exceptions=True,
)

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def make_kpi_card(card_id: str, label: str):
    return dbc.Card(
        dbc.CardBody([
            html.H3(id=card_id, className="card-title text-center mb-0",
                     style={"fontSize": "1.8rem"}),
            html.P(label, className="card-text text-center text-muted mt-1",
                   style={"fontSize": "0.85rem"}),
        ]),
        className="shadow-sm",
        style={"backgroundColor": "#2b2b2b"},
    )


app.layout = dbc.Container([

    # Header
    dbc.Row([
        dbc.Col([
            html.H1("Biotech Catalyst Tracker",
                     className="mb-0", style={"fontWeight": "700"}),
            html.P("Correlating biotech price movements with their catalysts",
                   className="text-muted mb-0", style={"fontSize": "0.9rem"}),
        ], width=8),
        dbc.Col([
            dbc.Button("Export CSV", id="export-btn", color="secondary",
                       size="sm", className="me-2"),
            dcc.Download(id="download-csv"),
        ], width=4, className="d-flex align-items-center justify-content-end"),
    ], className="my-3"),

    html.Hr(style={"borderColor": "#444"}),

    # KPI Cards
    dbc.Row([
        dbc.Col(make_kpi_card("kpi-total", "Total Mover Events"), width=3),
        dbc.Col(make_kpi_card("kpi-top-catalyst", "Most Common Catalyst"), width=3),
        dbc.Col(make_kpi_card("kpi-biggest", "Biggest Single Move"), width=3),
        dbc.Col(make_kpi_card("kpi-avg", "Avg Move Size"), width=3),
    ], className="mb-4"),

    # Filters
    dbc.Row([
        dbc.Col([
            html.Label("Catalyst Type", className="text-muted small"),
            dcc.Dropdown(
                id="filter-catalyst",
                options=[{"label": c, "value": c} for c in config.CATALYST_TYPES],
                multi=True,
                placeholder="All catalyst types",
                style={"backgroundColor": "#333", "color": "#fff"},
            ),
        ], width=4),
        dbc.Col([
            html.Label("Direction", className="text-muted small"),
            dcc.Dropdown(
                id="filter-direction",
                options=[
                    {"label": "All Moves", "value": "all"},
                    {"label": "Positive Only (+)", "value": "positive"},
                    {"label": "Negative Only (-)", "value": "negative"},
                ],
                value="all",
                clearable=False,
                style={"backgroundColor": "#333", "color": "#fff"},
            ),
        ], width=3),
        dbc.Col([
            html.Label("Search Ticker", className="text-muted small"),
            dbc.Input(
                id="filter-ticker",
                placeholder="e.g. MRNA",
                type="text",
                style={"backgroundColor": "#333", "color": "#fff", "border": "1px solid #555"},
            ),
        ], width=2),
        dbc.Col([
            html.Label("Min % Move", className="text-muted small"),
            dbc.Input(
                id="filter-min-pct",
                placeholder="10",
                type="number",
                value=10,
                style={"backgroundColor": "#333", "color": "#fff", "border": "1px solid #555"},
            ),
        ], width=2),
    ], className="mb-4"),

    # Data Table
    dbc.Row([
        dbc.Col([
            dash_table.DataTable(
                id="movers-table",
                columns=[
                    {"name": "Date", "id": "date"},
                    {"name": "Ticker", "id": "ticker"},
                    {"name": "Company", "id": "company_name"},
                    {"name": "% Change", "id": "pct_change", "type": "numeric"},
                    {"name": "Volume", "id": "volume", "type": "numeric"},
                    {"name": "Catalyst", "id": "catalyst_type"},
                    {"name": "Confidence", "id": "catalyst_confidence", "type": "numeric"},
                    {"name": "News", "id": "news_headline"},
                ],
                style_table={"overflowX": "auto"},
                style_header={
                    "backgroundColor": "#1e1e1e",
                    "color": "#fff",
                    "fontWeight": "bold",
                    "border": "1px solid #444",
                },
                style_cell={
                    "backgroundColor": "#2b2b2b",
                    "color": "#ddd",
                    "border": "1px solid #444",
                    "padding": "8px",
                    "fontSize": "13px",
                    "textAlign": "left",
                    "maxWidth": "300px",
                    "overflow": "hidden",
                    "textOverflow": "ellipsis",
                },
                style_data_conditional=[
                    {
                        "if": {"filter_query": "{pct_change} > 0"},
                        "backgroundColor": "#1a2e1a",
                    },
                    {
                        "if": {"filter_query": "{pct_change} < 0"},
                        "backgroundColor": "#2e1a1a",
                    },
                    {
                        "if": {"state": "active"},
                        "backgroundColor": "#3a3a5a",
                        "border": "1px solid #7777cc",
                    },
                ],
                sort_action="native",
                sort_by=[{"column_id": "pct_change", "direction": "desc"}],
                page_size=20,
                row_selectable="single",
            ),
        ]),
    ], className="mb-4"),

    # Charts Row 1: Catalyst frequency + Avg move by catalyst
    dbc.Row([
        dbc.Col(dcc.Graph(id="chart-catalyst-freq"), width=6),
        dbc.Col(dcc.Graph(id="chart-avg-move"), width=6),
    ], className="mb-4"),

    # Chart Row 2: 30-day timeline scatter
    dbc.Row([
        dbc.Col(dcc.Graph(id="chart-timeline")),
    ], className="mb-4"),

    # Stock Detail Panel (shown on row click)
    dbc.Row([
        dbc.Col(html.Div(id="stock-detail-panel")),
    ], className="mb-4"),

], fluid=True, style={"maxWidth": "1400px"})


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

@callback(
    [
        Output("movers-table", "data"),
        Output("kpi-total", "children"),
        Output("kpi-top-catalyst", "children"),
        Output("kpi-biggest", "children"),
        Output("kpi-avg", "children"),
        Output("chart-catalyst-freq", "figure"),
        Output("chart-avg-move", "figure"),
        Output("chart-timeline", "figure"),
    ],
    [
        Input("filter-catalyst", "value"),
        Input("filter-direction", "value"),
        Input("filter-ticker", "value"),
        Input("filter-min-pct", "value"),
    ],
)
def update_dashboard(catalyst_filter, direction, ticker_search, min_pct):
    df = load_movers()

    # Apply filters
    if catalyst_filter:
        df = df[df["catalyst_type"].isin(catalyst_filter)]
    if direction == "positive":
        df = df[df["pct_change"] > 0]
    elif direction == "negative":
        df = df[df["pct_change"] < 0]
    if ticker_search:
        df = df[df["ticker"].str.contains(ticker_search.upper(), na=False)]
    if min_pct is not None:
        df = df[df["pct_change"].abs() >= float(min_pct)]

    # KPIs
    total = len(df)
    if total > 0:
        top_catalyst = df["catalyst_type"].value_counts().index[0]
        biggest = df.loc[df["pct_change"].abs().idxmax()]
        biggest_str = f"{biggest['ticker']} {biggest['pct_change']:+.1f}%"
        avg_move = f"{df['pct_change'].abs().mean():.1f}%"
    else:
        top_catalyst = "N/A"
        biggest_str = "N/A"
        avg_move = "N/A"

    # Chart 1: Catalyst frequency
    if total > 0:
        freq = df["catalyst_type"].value_counts().reset_index()
        freq.columns = ["catalyst_type", "count"]
        fig_freq = px.bar(
            freq, x="catalyst_type", y="count",
            title="Catalyst Frequency",
            color="count",
            color_continuous_scale=["#2196F3", "#FF9800"],
        )
    else:
        fig_freq = go.Figure()
        fig_freq.add_annotation(text="No data", showarrow=False, font=dict(size=20, color="#888"))

    fig_freq.update_layout(**_chart_layout(), xaxis_title="", yaxis_title="Count")

    # Chart 2: Avg % move by catalyst
    if total > 0:
        avg_by_cat = (
            df.groupby("catalyst_type")["pct_change"]
            .agg(["mean", "std", "count"])
            .reset_index()
        )
        avg_by_cat.columns = ["catalyst_type", "avg_pct", "std_pct", "count"]
        avg_by_cat["avg_abs"] = avg_by_cat["avg_pct"].abs()
        avg_by_cat = avg_by_cat.sort_values("avg_abs", ascending=False)
        avg_by_cat["color"] = avg_by_cat["avg_pct"].apply(lambda x: "#4CAF50" if x > 0 else "#F44336")

        fig_avg = go.Figure()
        fig_avg.add_trace(go.Bar(
            x=avg_by_cat["catalyst_type"],
            y=avg_by_cat["avg_pct"],
            marker_color=avg_by_cat["color"],
            text=avg_by_cat["avg_pct"].apply(lambda x: f"{x:+.1f}%"),
            textposition="outside",
            hovertemplate="%{x}<br>Avg: %{y:+.1f}%<br>Count: %{customdata}<extra></extra>",
            customdata=avg_by_cat["count"],
        ))
    else:
        fig_avg = go.Figure()
        fig_avg.add_annotation(text="No data", showarrow=False, font=dict(size=20, color="#888"))

    fig_avg.update_layout(**_chart_layout(), title="Avg % Move by Catalyst", yaxis_title="Avg % Change")

    # Chart 3: Timeline scatter
    if total > 0:
        fig_timeline = px.scatter(
            df.sort_values("date"),
            x="date",
            y="pct_change",
            color="catalyst_type",
            size=df["pct_change"].abs(),
            hover_data=["ticker", "company_name", "news_headline", "catalyst_confidence"],
            title="30-Day Price Movement Timeline",
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        fig_timeline.add_hline(y=0, line_dash="dash", line_color="#666")
    else:
        fig_timeline = go.Figure()
        fig_timeline.add_annotation(text="No data", showarrow=False, font=dict(size=20, color="#888"))

    fig_timeline.update_layout(**_chart_layout(), xaxis_title="Date", yaxis_title="% Change", height=500)

    # Table data
    table_data = df.to_dict("records") if total > 0 else []

    return table_data, str(total), top_catalyst, biggest_str, avg_move, fig_freq, fig_avg, fig_timeline


@callback(
    Output("stock-detail-panel", "children"),
    Input("movers-table", "selected_rows"),
    State("movers-table", "data"),
)
def show_stock_detail(selected_rows, table_data):
    if not selected_rows or not table_data:
        return html.Div()

    row = table_data[selected_rows[0]]
    ticker = row["ticker"]
    company = row.get("company_name", ticker)

    # Build detail card
    detail_items = [
        html.H4(f"{ticker} — {company}", className="mb-3"),
        dbc.Row([
            dbc.Col([
                html.Strong("Date: "), html.Span(row.get("date", "")),
            ], width=3),
            dbc.Col([
                html.Strong("Move: "),
                html.Span(
                    f"{row.get('pct_change', 0):+.1f}%",
                    style={"color": "#4CAF50" if row.get("pct_change", 0) > 0 else "#F44336",
                           "fontWeight": "bold"},
                ),
            ], width=2),
            dbc.Col([
                html.Strong("Catalyst: "),
                dbc.Badge(row.get("catalyst_type", "UNKNOWN"), color="info"),
            ], width=3),
            dbc.Col([
                html.Strong("Confidence: "),
                html.Span(f"{row.get('catalyst_confidence', 0):.0%}"),
            ], width=2),
        ], className="mb-3"),
    ]

    headline = row.get("news_headline", "")
    summary = row.get("news_summary", "")
    url = row.get("news_url", "")

    if headline:
        detail_items.append(html.Div([
            html.Strong("News: "),
            html.A(headline, href=url, target="_blank", style={"color": "#64B5F6"}) if url
            else html.Span(headline),
        ], className="mb-2"))

    if summary:
        detail_items.append(html.Div([
            html.Strong("Summary: "),
            html.Span(summary, className="text-muted"),
        ], className="mb-2"))

    # Show all events for this ticker
    all_movers = load_movers()
    ticker_events = all_movers[all_movers["ticker"] == ticker].sort_values("date")

    if len(ticker_events) > 1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ticker_events["date"],
            y=ticker_events["pct_change"],
            mode="markers+lines",
            marker=dict(
                size=12,
                color=ticker_events["pct_change"].apply(lambda x: "#4CAF50" if x > 0 else "#F44336"),
            ),
            line=dict(color="#666", width=1),
            text=ticker_events["catalyst_type"],
            hovertemplate="%{x}<br>%{y:+.1f}%<br>%{text}<extra></extra>",
        ))
        fig.update_layout(
            **_chart_layout(),
            title=f"{ticker} — All Mover Events",
            xaxis_title="Date",
            yaxis_title="% Change",
            height=300,
        )
        fig.add_hline(y=0, line_dash="dash", line_color="#555")
        detail_items.append(dcc.Graph(figure=fig))

    return dbc.Card(
        dbc.CardBody(detail_items),
        style={"backgroundColor": "#2b2b2b", "border": "1px solid #555"},
        className="mt-2",
    )


@callback(
    Output("download-csv", "data"),
    Input("export-btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_csv(n_clicks):
    df = load_movers()
    return dcc.send_data_frame(df.to_csv, "biotech_movers_export.csv", index=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chart_layout() -> dict:
    return dict(
        template="plotly_dark",
        paper_bgcolor="#1e1e1e",
        plot_bgcolor="#1e1e1e",
        font=dict(color="#ddd"),
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(font=dict(size=10)),
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\nBiotech Catalyst Tracker Dashboard")
    print("Open: http://localhost:8050\n")
    app.run(debug=True, port=8050)
