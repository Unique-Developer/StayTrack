import io
import datetime
from pathlib import Path
from typing import List, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from app.db.models import UploadedReport, GuestRecord


def generate_report_excel(report: UploadedReport, records: List[GuestRecord]) -> io.BytesIO:
    """
    Generates a beautifully formatted Excel (.xlsx) spreadsheet of a report's extracted guest data.
    Eliminates reliance on stored physical PDF files while providing rich structured reporting.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Departures Data"
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    title_font = Font(name="Segoe UI", size=14, bold=True, color="0F172A")
    meta_label_font = Font(name="Segoe UI", size=9, bold=True, color="64748B")
    meta_val_font = Font(name="Segoe UI", size=9, bold=False, color="0F172A")
    header_font = Font(name="Segoe UI", size=9, bold=True, color="FFFFFF")
    data_font = Font(name="Segoe UI", size=9, color="1E293B")
    mono_font = Font(name="Consolas", size=9, color="1E293B")
    total_font = Font(name="Segoe UI", size=9, bold=True, color="0F172A")

    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    summary_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    header_border = Border(
        left=Side(style='thin', color='334155'),
        right=Side(style='thin', color='334155'),
        top=Side(style='thin', color='334155'),
        bottom=Side(style='medium', color='0F172A')
    )

    summary_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='94A3B8'),
        bottom=Side(style='double', color='0F172A')
    )

    # 1. Metadata Block
    ws.cell(row=1, column=1, value="StayTrack — Daily Departures Report Data").font = title_font

    prop_name = report.property.name if report.property else "Motel Property"
    prop_code = report.property.property_code if report.property else ""
    rep_date_str = report.report_date.strftime("%m-%d-%Y") if report.report_date else "N/A"

    metadata_rows = [
        ("Property:", f"{prop_name} (#{prop_code})" if prop_code else prop_name, "Report Date:", rep_date_str),
        ("Original File:", report.original_filename or "N/A", "PMS Run Time:", report.report_run_datetime or "N/A"),
        ("Extracted Records:", f"{len(records)} guests", "Export Generated:", datetime.datetime.now().strftime("%m-%d-%Y %I:%M %p"))
    ]

    for r_idx, meta in enumerate(metadata_rows, start=2):
        ws.cell(row=r_idx, column=1, value=meta[0]).font = meta_label_font
        ws.cell(row=r_idx, column=2, value=meta[1]).font = meta_val_font
        ws.cell(row=r_idx, column=4, value=meta[2]).font = meta_label_font
        ws.cell(row=r_idx, column=5, value=meta[3]).font = meta_val_font

    # 2. Table Headers (Row 6)
    headers = [
        ("Conf #", Alignment(horizontal="center")),
        ("Room", Alignment(horizontal="center")),
        ("Guest Name", Alignment(horizontal="left")),
        ("Additional Guests", Alignment(horizontal="left")),
        ("Check-In Date", Alignment(horizontal="center")),
        ("Nights", Alignment(horizontal="right")),
        ("Departure Date", Alignment(horizontal="center")),
        ("Actual Departed", Alignment(horizontal="center")),
        ("Status", Alignment(horizontal="center")),
        ("Total Balance ($)", Alignment(horizontal="right")),
        ("VIP", Alignment(horizontal="center")),
        ("Tier", Alignment(horizontal="center")),
        ("Housekeeping Remarks", Alignment(horizontal="left")),
        ("Validation Flags", Alignment(horizontal="left")),
    ]

    header_row_idx = 6
    for col_idx, (col_name, align) in enumerate(headers, start=1):
        cell = ws.cell(row=header_row_idx, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align
        cell.border = header_border

    # 3. Data Rows
    current_row = 7
    total_balance = 0.0
    total_nights = 0

    for rec in records:
        use_zebra = (current_row % 2 == 0)
        row_fill = zebra_fill if use_zebra else None

        c_in_str = rec.check_in_date.strftime("%m-%d-%Y") if rec.check_in_date else ""
        c_out_str = rec.calculated_departure_date.strftime("%m-%d-%Y") if rec.calculated_departure_date else ""
        balance = float(rec.total_guest_balance or 0.0)
        nights = rec.number_of_nights or 0
        total_balance += balance
        total_nights += nights

        row_data = [
            (rec.confirmation_number or rec.raw_confirmation_number or "", mono_font, Alignment(horizontal="center"), None),
            (rec.room_number or "", mono_font, Alignment(horizontal="center"), None),
            (rec.normalized_name or rec.raw_guest_name or "", data_font, Alignment(horizontal="left"), None),
            (rec.additional_guests or "", data_font, Alignment(horizontal="left"), None),
            (c_in_str, mono_font, Alignment(horizontal="center"), None),
            (nights, mono_font, Alignment(horizontal="right"), "#,##0"),
            (c_out_str, mono_font, Alignment(horizontal="center"), None),
            (rec.actual_departed_time or "", mono_font, Alignment(horizontal="center"), None),
            (rec.status or "Checked Out", data_font, Alignment(horizontal="center"), None),
            (balance, mono_font, Alignment(horizontal="right"), "$#,##0.00"),
            (rec.vip_guest or "No", data_font, Alignment(horizontal="center"), None),
            (rec.guest_tier or "", data_font, Alignment(horizontal="center"), None),
            (rec.housekeeping_remarks or "", data_font, Alignment(horizontal="left"), None),
            (rec.validation_flags or "", data_font, Alignment(horizontal="left"), None),
        ]

        for col_idx, (val, font, align, num_fmt) in enumerate(row_data, start=1):
            cell = ws.cell(row=current_row, column=col_idx, value=val)
            cell.font = font
            cell.alignment = align
            cell.border = thin_border
            if row_fill:
                cell.fill = row_fill
            if num_fmt:
                cell.number_format = num_fmt

        current_row += 1

    # 4. Summary Row (Totals)
    if records:
        summary_row_idx = current_row
        for col_idx in range(1, len(headers) + 1):
            c = ws.cell(row=summary_row_idx, column=col_idx)
            c.border = summary_border
            c.fill = summary_fill

        ws.cell(row=summary_row_idx, column=3, value=f"Total ({len(records)} records)").font = total_font
        nights_cell = ws.cell(row=summary_row_idx, column=6, value=total_nights)
        nights_cell.font = total_font
        nights_cell.alignment = Alignment(horizontal="right")
        nights_cell.number_format = "#,##0"

        bal_cell = ws.cell(row=summary_row_idx, column=10, value=total_balance)
        bal_cell.font = total_font
        bal_cell.alignment = Alignment(horizontal="right")
        bal_cell.number_format = "$#,##0.00"

    # 5. Column Width Formatting
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            # Measure table content (row 6 and above)
            if cell.row >= 6 and cell.value is not None:
                val_str = str(cell.value)
                if len(val_str) > max_len:
                    max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
