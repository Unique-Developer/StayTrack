import io
import datetime
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Flowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from app.db.models import Property, GuestIdentity, GuestRecord, UploadedReport
from app.core.time_utils import format_ny_now_str


def get_continuous_stays(
    db: Session,
    property_id: Optional[int] = None,
    min_nights: int = 7,
    search: Optional[str] = None,
    room: Optional[str] = None
) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
    """
    Extracts and evaluates uninterrupted continuous occupancy chains for all guests.
    Sorts descending from 30+ nights down to lesser continuous stay customers.
    Ignores guests who did not stay continuously in a row (e.g. breaks/gaps between stays).
    """
    if not isinstance(min_nights, int):
        try:
            min_nights = int(min_nights)
        except Exception:
            min_nights = 7
    if not isinstance(search, str):
        search = None

    prop = None
    if property_id:
        prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        prop = db.query(Property).first()

    prop_name = prop.name if prop else "Studio 6"
    target_property_id = prop.id if prop else 1

    # Determine latest known report date for the property to bound active stays
    latest_report = (
        db.query(UploadedReport.report_date)
        .filter(UploadedReport.property_id == target_property_id, UploadedReport.status == "completed", UploadedReport.is_active == True)
        .order_by(UploadedReport.report_date.desc())
        .first()
    )
    fallback_as_of = latest_report[0] if latest_report else datetime.date(2026, 10, 8)

    identities = db.query(GuestIdentity).filter(GuestIdentity.property_id == target_property_id).all()
    results: List[Dict[str, Any]] = []

    for identity in identities:
        records = (
            db.query(GuestRecord)
            .join(UploadedReport, GuestRecord.report_id == UploadedReport.id)
            .filter(
                GuestRecord.guest_identity_id == identity.id,
                UploadedReport.status == "completed",
                UploadedReport.is_active == True
            )
            .order_by(GuestRecord.check_in_date.asc(), UploadedReport.report_date.asc())
            .all()
        )

        # Deduplicate records representing the exact same reservation
        seen_res = set()
        unique_spans = []
        for r in records:
            c_in = r.check_in_date
            nights = r.number_of_nights or 0
            conf = r.confirmation_number or ""
            key = (conf, c_in, nights, r.room_number)
            if key in seen_res:
                continue
            seen_res.add(key)
            if c_in and nights > 0:
                c_out = r.calculated_departure_date or (c_in + datetime.timedelta(days=nights))
                unique_spans.append({
                    "start": c_in,
                    "end": c_out,
                    "nights": nights,
                    "room": r.room_number,
                    "conf": conf
                })

        chains = []
        if unique_spans:
            unique_spans.sort(key=lambda s: (s["start"], s["end"]))

            # Chain consecutive stays ("stayed in a row")
            curr_chain = {
                "start": unique_spans[0]["start"],
                "end": unique_spans[0]["end"],
                "nights": unique_spans[0]["nights"],
                "rooms": {unique_spans[0]["room"]} if unique_spans[0]["room"] else set(),
                "confs": [unique_spans[0]["conf"]] if unique_spans[0]["conf"] else [],
                "extensions": 0
            }

            for next_span in unique_spans[1:]:
                # If next reservation starts on or before current chain departure (or within 1 day of checkout)
                if next_span["start"] <= curr_chain["end"] + datetime.timedelta(days=1):
                    if next_span["end"] > curr_chain["end"]:
                        curr_chain["end"] = next_span["end"]
                    curr_chain["nights"] = (curr_chain["end"] - curr_chain["start"]).days
                    if next_span["room"]:
                        curr_chain["rooms"].add(next_span["room"])
                    if next_span["conf"] and next_span["conf"] not in curr_chain["confs"]:
                        curr_chain["confs"].append(next_span["conf"])
                    curr_chain["extensions"] += 1
                else:
                    chains.append(curr_chain)
                    curr_chain = {
                        "start": next_span["start"],
                        "end": next_span["end"],
                        "nights": next_span["nights"],
                        "rooms": {next_span["room"]} if next_span["room"] else set(),
                        "confs": [next_span["conf"]] if next_span["conf"] else [],
                        "extensions": 0
                    }
            chains.append(curr_chain)

            # If an original check-in date is configured and earlier than earliest chain, anchor it
            if identity.original_check_in_date:
                # Expand the primary continuous chain back to the original check-in date
                primary_chain = chains[-1] if chains else curr_chain
                if identity.original_check_in_date < primary_chain["start"]:
                    primary_chain["start"] = identity.original_check_in_date
                    primary_chain["nights"] = (primary_chain["end"] - primary_chain["start"]).days

        if not chains:
            continue

        # Check all continuous chains for this guest
        for c in chains:
            nights = c["nights"]
            if nights >= min_nights:
                start_d = c["start"]
                county_exempt_d = start_d + datetime.timedelta(days=30)
                state_exempt_d = start_d + datetime.timedelta(days=90)

                if nights >= 90:
                    cat = "90+ Nights"
                    cat_key = "90+"
                    tax_status = "Fully Tax Exempt (State + County)"
                elif nights >= 30:
                    cat = "30–89 Nights"
                    cat_key = "30+"
                    tax_status = "County Tax Exempt Only (30+ Days)"
                elif nights >= 21:
                    cat = "21–29 Nights"
                    cat_key = "21+"
                    tax_status = f"Approaching County Exemption ({30 - nights}d left)"
                elif nights >= 7:
                    cat = "7–20 Nights"
                    cat_key = "7+"
                    tax_status = f"Standard Taxable ({30 - nights}d to County Exempt)"
                else:
                    cat = "< 7 Nights"
                    cat_key = "<7"
                    tax_status = f"Standard Taxable ({30 - nights}d to County Exempt)"

                results.append({
                    "guest_name": identity.normalized_name,
                    "guest_identity_id": identity.id,
                    "check_in": c["start"],
                    "check_out": c["end"],
                    "total_nights": c["nights"],
                    "rooms_count": len(c["rooms"]) if c["rooms"] else 1,
                    "rooms_list": sorted(list(c["rooms"])),
                    "category": cat,
                    "category_key": cat_key,
                    "tax_status": tax_status,
                    "county_exempt_date": county_exempt_d,
                    "state_exempt_date": state_exempt_d,
                    "fixed_rate": identity.fixed_rate,
                    "extended": "Yes" if c["extensions"] > 0 else "No",
                    "ext_count": c["extensions"],
                    "confirmations": c["confs"]
                })

    # Optional search filtering (by guest name, room number, or confirmation number)
    if search and isinstance(search, str):
        s = search.strip().upper()
        results = [
            r for r in results
            if s in r["guest_name"].upper()
            or any(s in rm.upper() for rm in r["rooms_list"])
            or any(s in cf.upper() for cf in r["confirmations"])
        ]

    # Optional room filtering
    if room and isinstance(room, str):
        rm_filter = room.strip().upper()
        results = [
            r for r in results
            if any(rm_filter in rm.upper() for rm in r["rooms_list"])
        ]

    # Order from 90+ days descending to lesser continuous stay customers
    results.sort(key=lambda x: (-x["total_nights"], x["check_in"], x["guest_name"]))

    # Aggregate counts for header summary badges
    counts = {"90+": 0, "30+": 0, "21+": 0, "7+": 0}
    for r in results:
        k = r["category_key"]
        if k in counts:
            counts[k] += 1

    return prop_name, results, counts


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute total pages and draw decorative border and footer."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        width, height = self._pagesize
        # Top sleek accent line
        self.setFillColor(colors.HexColor("#f59e0b"))
        self.rect(0, height - 3, width * 0.4, 3, fill=1, stroke=0)
        self.setFillColor(colors.HexColor("#f43f5e"))
        self.rect(width * 0.4, height - 3, width * 0.6, 3, fill=1, stroke=0)

        # Bottom footer bar
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawString(36, 18, "STAYTRACK PMS")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(108, 18, "•   Continuous Long-Stay Residency Audit Report   •   Confidential & Proprietary")

        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.setFont("Helvetica-Bold", 7.5)
        self.setFillColor(colors.HexColor("#94a3b8"))
        self.drawRightString(width - 36, 18, page_str)
        self.restoreState()


def draw_background(canv: canvas.Canvas, doc: SimpleDocTemplate):
    """Draws rich deep midnight navy background on every page."""
    canv.saveState()
    width, height = doc.pagesize
    canv.setFillColor(colors.HexColor("#0c101d"))
    canv.rect(0, 0, width, height, fill=1, stroke=0)
    canv.restoreState()


class ExecutiveBannerFlowable(Flowable):
    """Modern executive header with property badge, title, subtitle, and live audit KPI."""
    def __init__(self, prop_name: str, total_count: int, width: float = 720, height: float = 46):
        super().__init__()
        self.prop_name = prop_name
        self.total_count = total_count
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        # Left side: Category pill tag above title
        self.canv.setFillColor(colors.HexColor("#1e293b"))
        self.canv.roundRect(0, self.height - 14, 120, 14, 3, fill=1, stroke=0)
        self.canv.setFont("Helvetica-Bold", 6.5)
        self.canv.setFillColor(colors.HexColor("#f59e0b"))
        self.canv.drawString(6, self.height - 10, "STAYTRACK AUDIT SUITE")

        # Property Title
        self.canv.setFont("Helvetica-Bold", 16)
        self.canv.setFillColor(colors.white)
        display_name = self.prop_name.title() if self.prop_name.isupper() else self.prop_name
        self.canv.drawString(0, self.height - 32, display_name)

        # Subtitle
        self.canv.setFont("Helvetica", 8)
        self.canv.setFillColor(colors.HexColor("#94a3b8"))
        now_str = format_ny_now_str("%b %d, %Y • %I:%M %p %Z")
        self.canv.drawString(0, self.height - 44, f"Continuous Stay & Extended Occupancy Verification   |   Generated: {now_str}")

        # Right side: Prominent Total Count Card
        card_w = 145
        card_h = 42
        card_x = self.width - card_w
        card_y = self.height - 44

        self.canv.setFillColor(colors.HexColor("#161f36"))
        self.canv.setStrokeColor(colors.HexColor("#2a385c"))
        self.canv.setLineWidth(1)
        self.canv.roundRect(card_x, card_y, card_w, card_h, 6, fill=1, stroke=1)

        # Pulse accent dot inside card
        self.canv.setFillColor(colors.HexColor("#10b981"))
        self.canv.circle(card_x + 12, card_y + card_h - 12, 3, fill=1, stroke=0)

        self.canv.setFont("Helvetica-Bold", 7)
        self.canv.setFillColor(colors.HexColor("#94a3b8"))
        self.canv.drawString(card_x + 20, card_y + card_h - 14, "LONG-STAY GUESTS")

        self.canv.setFont("Helvetica-Bold", 17)
        self.canv.setFillColor(colors.white)
        self.canv.drawString(card_x + 12, card_y + 8, str(self.total_count))

        self.canv.setFont("Helvetica", 7.5)
        self.canv.setFillColor(colors.HexColor("#38bdf8"))
        self.canv.drawRightString(card_x + card_w - 10, card_y + 10, "≥ 7 Consecutive Days")

        self.canv.restoreState()


class MetricCardsFlowable(Flowable):
    """4 Modern Executive KPI Cards across the top for immediate understanding."""
    def __init__(self, counts: dict, width: float = 720, height: float = 48):
        super().__init__()
        self.counts = counts
        self.width = width
        self.height = height

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        card_configs = [
            {
                "tier": "90+ NIGHTS",
                "count": self.counts.get("90+", 0),
                "badge": "STATE & COUNTY EXEMPT",
                "sub": "Full tax exemption",
                "accent": "#10b981",
                "bg": "#112220",
                "border": "#194a3e"
            },
            {
                "tier": "30–89 NIGHTS",
                "count": self.counts.get("30+", 0),
                "badge": "COUNTY EXEMPT ONLY",
                "sub": "Local transient exempt",
                "accent": "#f43f5e",
                "bg": "#1e1524",
                "border": "#4c1d30"
            },
            {
                "tier": "21–29 NIGHTS",
                "count": self.counts.get("21+", 0),
                "badge": "APPROACHING 30",
                "sub": "Approaching residency",
                "accent": "#f59e0b",
                "bg": "#211a14",
                "border": "#4d3516"
            },
            {
                "tier": "7–20 NIGHTS",
                "count": self.counts.get("7+", 0),
                "badge": "WEEKLY EXTENDED",
                "sub": "Continuous occupancy",
                "accent": "#38bdf8",
                "bg": "#121d2e",
                "border": "#1e3759"
            }
        ]

        num_cards = len(card_configs)
        gap = 10
        card_w = (self.width - (num_cards - 1) * gap) / float(num_cards)
        card_h = self.height

        for i, cfg in enumerate(card_configs):
            x = i * (card_w + gap)
            y = 0

            # Card background & border
            self.canv.setFillColor(colors.HexColor(cfg["bg"]))
            self.canv.setStrokeColor(colors.HexColor(cfg["border"]))
            self.canv.setLineWidth(1)
            self.canv.roundRect(x, y, card_w, card_h, 5, fill=1, stroke=1)

            # Left color indicator bar
            self.canv.setFillColor(colors.HexColor(cfg["accent"]))
            self.canv.roundRect(x, y, 3.5, card_h, 2, fill=1, stroke=0)

            # Top header row inside card: Tier Title
            self.canv.setFont("Helvetica-Bold", 7.5)
            self.canv.setFillColor(colors.white)
            self.canv.drawString(x + 10, y + card_h - 13, cfg["tier"])

            # Mini badge pill on top-right of card
            badge_text = cfg["badge"]
            bw = self.canv.stringWidth(badge_text, "Helvetica-Bold", 5.5) + 8
            bx = x + card_w - bw - 8
            by = y + card_h - 14
            self.canv.setFillColor(colors.HexColor(cfg["accent"]))
            self.canv.roundRect(bx, by, bw, 9, 2.5, fill=1, stroke=0)
            self.canv.setFont("Helvetica-Bold", 5.5)
            self.canv.setFillColor(colors.HexColor("#0f172a"))
            self.canv.drawCentredString(bx + bw / 2.0, by + 2.2, badge_text)

            # Large Count Number
            self.canv.setFont("Helvetica-Bold", 19)
            self.canv.setFillColor(colors.HexColor(cfg["accent"]))
            self.canv.drawString(x + 10, y + 10, str(cfg["count"]))

            # Small descriptor text next to number
            self.canv.setFont("Helvetica", 6.8)
            self.canv.setFillColor(colors.HexColor("#94a3b8"))
            self.canv.drawString(x + 40, y + 14, cfg["sub"])

        self.canv.restoreState()


class PillTag(Flowable):
    """Reusable modern pill tag for durations, categories, and booking extensions."""
    def __init__(self, text: str, bg_hex: str, text_hex: str, width: float = 68, height: float = 16, radius: float = 3.5, font_size: float = 7.5):
        super().__init__()
        self.text = text
        self.bg_color = colors.HexColor(bg_hex)
        self.text_color = colors.HexColor(text_hex)
        self.width = width
        self.height = height
        self.radius = radius
        self.font_size = font_size

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColor(self.bg_color)
        self.canv.roundRect(0, 0, self.width, self.height, self.radius, fill=1, stroke=0)
        self.canv.setFillColor(self.text_color)
        self.canv.setFont("Helvetica-Bold", self.font_size)
        self.canv.drawCentredString(self.width / 2.0, (self.height - self.font_size) / 2.0 + 1.2, self.text)
        self.canv.restoreState()


class ConfGridFlowable(Flowable):
    """Confirmation numbers arranged in a sleek 2-column tag layout, capped to prevent row overflow."""
    def __init__(self, conf_list: List[str], max_width: float = 140, max_tags: int = 4):
        super().__init__()
        self.raw_conf_list = [c for c in (conf_list or []) if c]
        self.max_width = max_width
        self.tag_w = 66
        self.tag_h = 15
        self.gap_x = 5
        self.gap_y = 3.5

        # Format items to display (capped at max_tags)
        items: List[Tuple[str, bool]] = []  # (text, is_badge)
        total_confs = len(self.raw_conf_list)
        if total_confs == 0:
            items.append(("—", False))
        elif total_confs <= max_tags:
            for c in self.raw_conf_list:
                items.append((str(c), False))
        else:
            # Show first 2 confirmations, the latest confirmation, and an overflow badge
            items.append((str(self.raw_conf_list[0]), False))
            if max_tags >= 3:
                items.append((str(self.raw_conf_list[1]), False))
            if max_tags >= 4:
                items.append((str(self.raw_conf_list[-1]), False))
            overflow_count = total_confs - len(items)
            items.append((f"+{overflow_count} more", True))

        self.display_items = items
        cols = 2 if len(items) > 1 else 1
        n = len(items)
        rows = max(1, (n + cols - 1) // cols)
        self.rows = rows
        self.cols = cols
        self.total_h = rows * self.tag_h + (rows - 1) * self.gap_y

    def wrap(self, availWidth, availHeight):
        return self.max_width, self.total_h

    def draw(self):
        if not self.display_items:
            return
        self.canv.saveState()
        for idx, (text, is_badge) in enumerate(self.display_items):
            r = idx // self.cols
            c = idx % self.cols
            x = c * (self.tag_w + self.gap_x)
            y = self.total_h - ((r + 1) * self.tag_h + r * self.gap_y)

            if is_badge:
                # Highlight badge pill for renewals/extensions
                self.canv.setFillColor(colors.HexColor("#2d2415"))
                self.canv.setStrokeColor(colors.HexColor("#784e1b"))
                self.canv.setLineWidth(0.8)
                self.canv.roundRect(x, y, self.tag_w, self.tag_h, 3, fill=1, stroke=1)

                self.canv.setFillColor(colors.HexColor("#f59e0b"))
                self.canv.setFont("Helvetica-Bold", 6.8)
                self.canv.drawCentredString(x + self.tag_w / 2.0, y + 4.2, text)
            else:
                self.canv.setFillColor(colors.HexColor("#151c2f"))
                self.canv.setStrokeColor(colors.HexColor("#243152"))
                self.canv.setLineWidth(0.8)
                self.canv.roundRect(x, y, self.tag_w, self.tag_h, 3, fill=1, stroke=1)

                self.canv.setFillColor(colors.HexColor("#94a3b8"))
                f_size = 6.8 if len(text) <= 10 else 5.8
                self.canv.setFont("Courier-Bold", f_size)
                self.canv.drawCentredString(x + self.tag_w / 2.0, y + 4.2, text)
        self.canv.restoreState()


def generate_long_stay_pdf(
    property_name: str,
    stays: List[Dict[str, Any]],
    counts: Dict[str, int]
) -> bytes:
    """
    Renders an executive, highly intuitive continuous long-stay monitoring report.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=36,
        rightMargin=36,
        topMargin=28,
        bottomMargin=28
    )

    usable_width = landscape(letter)[0] - 72  # 720 pt
    story = []

    # 1. Executive Top Header Banner
    story.append(ExecutiveBannerFlowable(property_name, len(stays), width=usable_width, height=46))
    story.append(Spacer(1, 10))

    # 2. Executive 4-Card Metric Grid
    story.append(MetricCardsFlowable(counts, width=usable_width, height=48))
    story.append(Spacer(1, 12))

    # 3. Typography Styles
    th_style = ParagraphStyle(
        "TH",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=colors.HexColor("#64748b"),
        alignment=0,
        spaceAfter=0
    )
    th_center = ParagraphStyle("TH_C", parent=th_style, alignment=1)

    guest_name_style = ParagraphStyle(
        "GName",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=colors.white,
        leading=10
    )
    guest_sub_style = ParagraphStyle(
        "GSub",
        fontName="Helvetica",
        fontSize=7.2,
        textColor=colors.HexColor("#94a3b8"),
        leading=9
    )

    date_range_style = ParagraphStyle(
        "DateRange",
        fontName="Helvetica-Bold",
        fontSize=7.8,
        textColor=colors.HexColor("#e2e8f0"),
        leading=10
    )
    date_sub_style = ParagraphStyle(
        "DateSub",
        fontName="Helvetica",
        fontSize=7,
        textColor=colors.HexColor("#64748b"),
        leading=9
    )

    table_data = [[
        Paragraph("GUEST & ROOM", th_style),
        Paragraph("STAY PERIOD", th_style),
        Paragraph("DURATION & TIER", th_center),
        Paragraph("TAX EXEMPTION DATES", th_style),
        Paragraph("CONFIRMATIONS", th_style),
    ]]

    # 5 columns summing to 720 pt
    col_widths = [175, 130, 95, 170, 150]

    tier_labels = {
        "90+ Nights": ("90+ DAYS CONTINUOUS  •  STATE & COUNTY TAX EXEMPT (FULL RESIDENCY)", "#10b981", "#122b24"),
        "30–89 Nights": ("30–89 DAYS CONTINUOUS  •  COUNTY TAX EXEMPT ONLY (LOCAL RESIDENCY)", "#f43f5e", "#2a121e"),
        "21–29 Nights": ("21–29 DAYS CONTINUOUS  •  APPROACHING 30-DAY COUNTY EXEMPTION", "#f59e0b", "#2a1f12"),
        "7–20 Nights": ("7–20 DAYS CONTINUOUS  •  WEEKLY EXTENDED OCCUPANCY", "#38bdf8", "#122338"),
        "30+ Nights": ("30+ DAYS CONTINUOUS  •  MONTHLY RESIDENCY (TAX ALERT)", "#f43f5e", "#2a121e"),
        "21+ Nights": ("21–29 DAYS CONTINUOUS  •  APPROACHING MONTHLY TIER", "#f59e0b", "#2a1f12"),
        "14+ Nights": ("14–20 DAYS CONTINUOUS  •  BI-WEEKLY EXTENDED STAY", "#38bdf8", "#122338"),
        "7+ Nights": ("7–13 DAYS CONTINUOUS  •  WEEKLY EXTENDED OCCUPANCY", "#10b981", "#122b24"),
    }

    tier_pills = {
        "90+ Nights": ("90+ Nights", "#194a3e", "#10b981"),
        "30–89 Nights": ("30–89 Nights", "#4c1d30", "#f43f5e"),
        "21–29 Nights": ("21–29 Nights", "#4d3516", "#f59e0b"),
        "7–20 Nights": ("7–20 Nights", "#1e3759", "#38bdf8"),
        "30+ Nights": ("30+ Nights", "#4c1d30", "#f43f5e"),
        "21+ Nights": ("21+ Nights", "#4d3516", "#f59e0b"),
        "14+ Nights": ("14+ Nights", "#1e3759", "#38bdf8"),
        "7+ Nights": ("7+ Nights", "#194a3e", "#10b981"),
        "< 7 Nights": ("< 7 Nights", "#1e293b", "#94a3b8"),
    }

    if not stays:
        empty_style = ParagraphStyle(
            "Empty",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#94a3b8"),
            alignment=1
        )
        empty_row = [
            Paragraph("No continuous stay records found matching the criteria.", empty_style),
            "", "", "", ""
        ]
        table_data.append(empty_row)
    else:
        current_tier = None
        for s in stays:
            tier = s["category"]

            # Add tier divider banner row when moving to a new tier
            if tier != current_tier:
                current_tier = tier
                tier_title, accent_color, bar_bg = tier_labels.get(tier, (tier, "#94a3b8", "#1e293b"))
                divider_style = ParagraphStyle(
                    "TierDivider",
                    fontName="Helvetica-Bold",
                    fontSize=7.2,
                    textColor=colors.HexColor(accent_color),
                    alignment=0
                )
                divider_row = [
                    Paragraph(f"▶  {tier_title}", divider_style),
                    "", "", "", ""
                ]
                table_data.append(divider_row)

            # 1. Guest & Room column
            if s['rooms_list']:
                if len(s['rooms_list']) > 3:
                    room_text = f"Rooms {', '.join(s['rooms_list'][:3])} (+{len(s['rooms_list']) - 3} more)"
                else:
                    room_text = f"Room {', '.join(s['rooms_list'])}"
            else:
                room_text = f"{s['rooms_count']} Room"

            guest_cell = [
                Paragraph(s["guest_name"], guest_name_style),
                Paragraph(f"<font color='#38bdf8'><b>●</b></font> {room_text}", guest_sub_style)
            ]

            # 2. Stay Period column
            c_in_str = s["check_in"].strftime("%b %d, %Y")
            c_out_str = s["check_out"].strftime("%b %d, %Y")
            period_cell = [
                Paragraph(f"{c_in_str}  →  {c_out_str}", date_range_style),
                Paragraph(f"Unbroken continuous stay", date_sub_style)
            ]

            # 3. Duration & Tier column
            duration_pill = PillTag(
                f"{s['total_nights']} Nights",
                bg_hex="#1e293b",
                text_hex="#ffffff",
                width=72,
                height=15,
                radius=3.5,
                font_size=7.5
            )
            t_text, t_bg, t_fg = tier_pills.get(s["category"], (s["category"], "#1e293b", "#94a3b8"))
            tier_pill = PillTag(t_text, bg_hex=t_bg, text_hex=t_fg, width=72, height=15, radius=3.5, font_size=7)

            duration_tier_cell = [
                duration_pill,
                Spacer(1, 2),
                tier_pill
            ]

            # 4. Tax Exemption Dates column
            county_str = s["county_exempt_date"].strftime("%b %d, %Y") if s.get("county_exempt_date") else "N/A"
            state_str = s["state_exempt_date"].strftime("%b %d, %Y") if s.get("state_exempt_date") else "N/A"
            tax_status_str = s.get("tax_status", "")

            status_color = "#10b981" if s["total_nights"] >= 90 else ("#f43f5e" if s["total_nights"] >= 30 else ("#f59e0b" if s["total_nights"] >= 21 else "#94a3b8"))
            tax_cell = [
                Paragraph(f"<font color='#94a3b8'>County (30+):</font> <b>{county_str}</b>", date_sub_style),
                Paragraph(f"<font color='#94a3b8'>State (90+):</font> <b>{state_str}</b>", date_sub_style),
                Paragraph(f"<font color='{status_color}'><b>● {tax_status_str}</b></font>", date_sub_style)
            ]

            # 5. Confirmation tags
            conf_flowable = ConfGridFlowable(s["confirmations"], max_width=140)

            row = [
                guest_cell,
                period_cell,
                duration_tier_cell,
                tax_cell,
                conf_flowable
            ]
            table_data.append(row)

    t = Table(table_data, colWidths=col_widths, repeatRows=1)

    t_style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#0f1526")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 7),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor("#222f4c")),
    ]

    if not stays:
        t_style.append(('SPAN', (0, 1), (-1, 1)))
        t_style.append(('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#12192c")))
        t_style.append(('TOPPADDING', (0, 1), (-1, 1), 20))
        t_style.append(('BOTTOMPADDING', (0, 1), (-1, 1), 20))
    else:
        row_idx = 1
        for item in table_data[1:]:
            if item[1] == "":
                # Tier section header banner row
                t_style.append(('SPAN', (0, row_idx), (-1, row_idx)))
                t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), colors.HexColor("#141b2f")))
                t_style.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 5))
                t_style.append(('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 5))
                t_style.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor("#222f4c")))
            else:
                bg = colors.HexColor("#0f1424") if row_idx % 2 == 1 else colors.HexColor("#12192c")
                t_style.append(('BACKGROUND', (0, row_idx), (-1, row_idx), bg))
                t_style.append(('TOPPADDING', (0, row_idx), (-1, row_idx), 5))
                t_style.append(('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 5))
                t_style.append(('LINEBELOW', (0, row_idx), (-1, row_idx), 0.5, colors.HexColor("#1a233a")))
            row_idx += 1

    t.setStyle(TableStyle(t_style))
    story.append(t)

    doc.build(story, canvasmaker=NumberedCanvas, onFirstPage=draw_background, onLaterPages=draw_background)
    return buffer.getvalue()
