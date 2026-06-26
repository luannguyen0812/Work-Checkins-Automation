import openpyxl
from openpyxl.chart import BarChart, LineChart, ScatterChart, Reference, Series
from openpyxl.chart.series import SeriesLabel


def add_attendance_bar_chart(ws: openpyxl.worksheet.worksheet.Worksheet, name_col: int, rate_col: int, data_rows: int) -> None:
    """Bar chart: attendance rate per intern, sorted ascending. Expects headers in row 1."""
    chart = BarChart()
    chart.type = "bar"
    chart.title = "Attendance Rate by Intern"
    chart.y_axis.title = "Rate (%)"
    chart.x_axis.title = "Intern"
    chart.style = 10
    chart.width = 28
    chart.height = 16

    data_ref = Reference(ws, min_col=rate_col, min_row=1, max_row=1 + data_rows)
    chart.add_data(data_ref, titles_from_data=True)

    cats = Reference(ws, min_col=name_col, min_row=2, max_row=1 + data_rows)
    chart.set_categories(cats)

    ws.add_chart(chart, f"A{4 + data_rows}")


def add_trend_line_chart(ws: openpyxl.worksheet.worksheet.Worksheet, header_row: int, data_rows: int, week_cols: list[int], name_col: int) -> None:
    """Line chart: week-over-week attendance per intern."""
    chart = LineChart()
    chart.title = "4-Week Attendance Trend"
    chart.y_axis.title = "Rate (%)"
    chart.x_axis.title = "Week"
    chart.style = 10
    chart.width = 28
    chart.height = 16

    for col in week_cols:
        data_ref = Reference(ws, min_col=col, min_row=header_row, max_row=header_row + data_rows)
        chart.add_data(data_ref, titles_from_data=True)

    cats = Reference(ws, min_col=name_col, min_row=header_row + 1, max_row=header_row + data_rows)
    chart.set_categories(cats)

    ws.add_chart(chart, f"A{header_row + data_rows + 3}")


def add_risk_scatter_chart(ws: openpyxl.worksheet.worksheet.Worksheet, war_col: int, rar_col: int, data_rows: int) -> None:
    """Scatter: WAR (x) vs RAR (y)."""
    chart = ScatterChart()
    chart.title = "WAR vs RAR"
    chart.x_axis.title = "Weekly Attendance Rate"
    chart.y_axis.title = "4-Week Rolling Rate"
    chart.style = 10
    chart.width = 20
    chart.height = 15

    xvalues = Reference(ws, min_col=war_col, min_row=2, max_row=1 + data_rows)
    yvalues = Reference(ws, min_col=rar_col, min_row=2, max_row=1 + data_rows)
    series = Series(yvalues, xvalues, title="Interns")
    chart.series.append(series)

    ws.add_chart(chart, f"J2")
