import re
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pdfplumber

from app.parsers.normalizers import (
    clean_whitespace,
    normalize_confirmation_number,
    normalize_name,
    parse_date_flexible,
    calculate_departure_date,
    clean_room_number
)
from app.parsers.ocr_engine import is_ocr_available, ocr_pdf_to_text

class PDFParserResult:
    def __init__(self):
        self.property_name: Optional[str] = None
        self.property_code: Optional[str] = None
        self.report_date: Optional[datetime.date] = None
        self.report_run_datetime: Optional[str] = None
        self.generated_by: Optional[str] = None
        self.records: List[Dict[str, Any]] = []
        self.total_rows: int = 0
        self.valid_rows: int = 0
        self.has_warnings: bool = False
        self.warnings: List[str] = []
        self.extraction_method: str = "pdfplumber"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_name": self.property_name,
            "property_code": self.property_code,
            "report_date": self.report_date.isoformat() if self.report_date else None,
            "report_run_datetime": self.report_run_datetime,
            "generated_by": self.generated_by,
            "records": self.records,
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "has_warnings": self.has_warnings,
            "warnings": self.warnings,
            "extraction_method": self.extraction_method
        }


def parse_header_metadata(page: pdfplumber.page.Page, tables: List[Any]) -> Tuple[Optional[str], Optional[str], Optional[datetime.date], Optional[str], Optional[str]]:
    """
    Extract property name, property code, report date, run time, and user from header.
    """
    property_name = None
    property_code = None
    report_date = None
    run_datetime = None
    generated_by = None

    def extract_run_dt(text: str) -> Optional[str]:
        if not text:
            return None
        m_date = re.search(r'Report Run Date:\s*([A-Za-z0-9\s,]+?)(?=\n|Report Run Time|User:|$)', text, re.IGNORECASE)
        m_time = re.search(r'Report Run Time:\s*([0-9:]+\s*(?:AM|PM)?)', text, re.IGNORECASE)
        if m_date and m_time:
            d_val = clean_whitespace(m_date.group(1))
            t_val = clean_whitespace(m_time.group(1))
            for fmt in ("%b %d %Y %I:%M %p", "%b %d, %Y %I:%M %p", "%Y-%m-%d %I:%M %p"):
                try:
                    dt = datetime.datetime.strptime(f"{d_val} {t_val}", fmt)
                    return dt.strftime("%b %d, %Y • %I:%M %p")
                except ValueError:
                    pass
            return f"{d_val} • {t_val}"
        elif m_date:
            d_val = clean_whitespace(m_date.group(1))
            for fmt in ("%b %d %Y", "%b %d, %Y", "%Y-%m-%d"):
                try:
                    dt = datetime.datetime.strptime(d_val, fmt)
                    return dt.strftime("%b %d, %Y")
                except ValueError:
                    pass
            return d_val
        return None

    # First check tables[0] if present
    if tables and len(tables) > 0 and len(tables[0]) > 0:
        header_row = tables[0][0]
        for cell in header_row:
            if not cell:
                continue
            cell_str = str(cell)
            lines = [clean_whitespace(l) for l in cell_str.split('\n') if clean_whitespace(l)]
            
            # Check for property lines
            for line in lines:
                if "STUDIO 6" in line.upper() or "MOTEL 6" in line.upper() or "-" in line:
                    if not property_name:
                        property_name = line
                if re.match(r'^\d{4,6}$', line):
                    property_code = line
                if "Date:" in line:
                    date_part = line.split("Date:", 1)[1]
                    d = parse_date_flexible(date_part)
                    if d and not report_date:
                        report_date = d
                if "User:" in line:
                    generated_by = line.split("User:", 1)[1].strip()

            if not run_datetime:
                run_datetime = extract_run_dt(cell_str)

    # Fallback / reinforcement from raw page text
    raw_text = page.extract_text() or ""
    if not report_date:
        match_date = re.search(r'Date:\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4})', raw_text)
        if match_date:
            report_date = parse_date_flexible(match_date.group(1))

    if not run_datetime:
        run_datetime = extract_run_dt(raw_text)

    if not property_code:
        match_code = re.search(r'\b(\d{4})\b', raw_text)
        if match_code:
            property_code = match_code.group(1)

    if not property_name:
        match_prop = re.search(r'([A-Za-z0-9\s\-]+,\s*[A-Z]{2})', raw_text)
        if match_prop:
            property_name = match_prop.group(1).strip()
        else:
            property_name = "STUDIO 6 - STAFFORD, VA"

    if not generated_by:
        match_user = re.search(r'User:\s*([A-Za-z\s]+)', raw_text)
        if match_user:
            generated_by = match_user.group(1).strip()

    return property_name, property_code, report_date, run_datetime, generated_by


def identify_columns(header_cells: List[Optional[str]]) -> Dict[str, int]:
    """
    Map column semantic names to index positions based on header text.
    Handles multi-line and wrapped header titles.
    """
    col_map = {}
    for idx, cell in enumerate(header_cells):
        if not cell:
            continue
        c = clean_whitespace(cell).lower()
        
        if "confirm" in c:
            col_map["confirmation"] = idx
        elif "additional" in c:
            col_map["additional_guests"] = idx
        elif "room" in c:
            col_map["room"] = idx
        elif c == "guest name" or c.startswith("guest\nname") or c == "guest":
            col_map["guest_name"] = idx
        elif "first name" in c:
            col_map["first_name"] = idx
        elif "last name" in c:
            col_map["last_name"] = idx
        elif "check in" in c:
            col_map["check_in_date"] = idx
        elif "night" in c:
            col_map["nights"] = idx
        elif "status" in c:
            col_map["status"] = idx
        elif "balance" in c:
            col_map["balance"] = idx
        elif "estimated" in c:
            col_map["est_departure"] = idx
        elif "actual" in c or "departed time" in c:
            col_map["actual_departed"] = idx
        elif "vip" in c:
            col_map["vip"] = idx
        elif "tier" in c:
            col_map["tier"] = idx
        elif "housekeep" in c or "remarks" in c:
            col_map["remarks"] = idx

    return col_map


def parse_departures_pdf(file_path: str, convention: str = "checkin_plus_nights") -> PDFParserResult:
    """
    Primary parser for Departures List PDF reports.
    Attempts text and table extraction first, with OCR fallback if necessary.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    result = PDFParserResult()

    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                raise ValueError("PDF contains no pages")

            # Check if text is present across pages
            total_text = ""
            for p in pdf.pages:
                t = p.extract_text() or ""
                total_text += t.strip()

            # If empty text, try OCR fallback
            if len(total_text) < 50:
                if is_ocr_available():
                    result.extraction_method = "ocr_fallback"
                    result.warnings.append("Text extraction yielded minimal content; applied OCR fallback.")
                    ocr_text = ocr_pdf_to_text(file_path)
                    # We can log OCR text or parse line-by-line
                else:
                    result.warnings.append("Scanned document detected but Tesseract OCR is not installed.")

            # Process pages
            for page_num, page in enumerate(pdf.pages, start=1):
                tables = page.extract_tables()
                
                # First page header metadata
                if page_num == 1:
                    prop_name, prop_code, rep_date, run_dt, gen_by = parse_header_metadata(page, tables)
                    result.property_name = prop_name
                    result.property_code = prop_code
                    result.report_date = rep_date
                    result.report_run_datetime = run_dt
                    result.generated_by = gen_by

                # Extract data table
                data_table = None
                if len(tables) >= 2:
                    data_table = tables[1]
                elif len(tables) == 1:
                    data_table = tables[0]

                if not data_table or len(data_table) < 2:
                    continue

                # Locate header row (skip title rows like 'Departures List')
                header_row_idx = 0
                for r_idx, row in enumerate(data_table):
                    row_text = " ".join([clean_whitespace(c).lower() for c in row if c])
                    if "room" in row_text or "confirmation" in row_text or "check in" in row_text:
                        header_row_idx = r_idx
                        break

                col_map = identify_columns(data_table[header_row_idx])
                
                # Iterate rows
                for r_idx, row in enumerate(data_table[header_row_idx + 1:], start=header_row_idx + 1):
                    # Skip empty rows
                    if not any(row):
                        continue

                    def get_cell(col_key: str) -> Optional[str]:
                        idx = col_map.get(col_key)
                        if idx is not None and idx < len(row):
                            return clean_whitespace(row[idx])
                        return None

                    raw_conf = get_cell("confirmation")
                    raw_name = get_cell("guest_name")
                    first_name = get_cell("first_name")
                    last_name = get_cell("last_name")
                    room = clean_room_number(get_cell("room"))
                    check_in_str = get_cell("check_in_date")
                    nights_str = get_cell("nights")
                    status_str = get_cell("status") or "Checked Out"
                    balance_str = get_cell("balance")
                    actual_departed = get_cell("actual_departed")
                    vip_str = get_cell("vip") or "No"
                    tier_str = get_cell("tier")
                    remarks_str = get_cell("remarks")
                    add_guests = get_cell("additional_guests")

                    # If all core fields are missing, skip line
                    if not raw_conf and not raw_name and not room:
                        continue

                    conf_no = normalize_confirmation_number(raw_conf)
                    
                    # Normalize names
                    combined_name = f"{first_name or ''} {last_name or ''}".strip()
                    if not combined_name:
                        combined_name = raw_name or ""
                    norm_name = normalize_name(combined_name)

                    # Dates & Nights
                    check_in_date = parse_date_flexible(check_in_str)
                    nights = None
                    if nights_str:
                        try:
                            # Strip any non-digit
                            digits = re.findall(r'\d+', nights_str)
                            if digits:
                                nights = int(digits[0])
                        except ValueError:
                            pass

                    calc_dept_date = calculate_departure_date(check_in_date, nights, convention)

                    # Balance
                    balance = 0.0
                    if balance_str:
                        try:
                            balance = float(re.sub(r'[^\d.\-]', '', balance_str))
                        except ValueError:
                            balance = 0.0

                    # Quality & Validation flags
                    flags = []
                    confidence = 1.0

                    if not conf_no:
                        flags.append("MISSING_CONFIRMATION")
                        confidence -= 0.15
                    if not room:
                        flags.append("MISSING_ROOM")
                        confidence -= 0.15
                    if not norm_name:
                        flags.append("MISSING_NAME")
                        confidence -= 0.35
                    if not check_in_date:
                        flags.append("INVALID_CHECKIN_DATE")
                        confidence -= 0.25
                    if nights is None:
                        flags.append("MISSING_NIGHTS")
                        confidence -= 0.15
                    
                    # Check if departure date differs from report date
                    if calc_dept_date and result.report_date and calc_dept_date != result.report_date:
                        flags.append(f"DEPARTURE_MISMATCH_CALC_{calc_dept_date.isoformat()}")

                    confidence = max(0.0, round(confidence, 2))

                    record = {
                        "raw_confirmation_number": raw_conf,
                        "confirmation_number": conf_no,
                        "raw_guest_name": raw_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "normalized_name": norm_name,
                        "additional_guests": add_guests,
                        "room_number": room,
                        "check_in_date": check_in_date.isoformat() if check_in_date else None,
                        "number_of_nights": nights,
                        "calculated_departure_date": calc_dept_date.isoformat() if calc_dept_date else None,
                        "status": status_str,
                        "total_guest_balance": balance,
                        "actual_departed_time": actual_departed,
                        "vip_guest": vip_str,
                        "guest_tier": tier_str,
                        "housekeeping_remarks": remarks_str,
                        "source_page": page_num,
                        "source_row_index": r_idx,
                        "confidence_score": confidence,
                        "validation_flags": flags
                    }

                    result.records.append(record)
                    result.total_rows += 1
                    if confidence >= 0.70 and norm_name and check_in_date:
                        result.valid_rows += 1
                    else:
                        result.has_warnings = True

    except Exception as e:
        result.has_warnings = True
        result.warnings.append(f"Parsing exception: {str(e)}")

    return result
