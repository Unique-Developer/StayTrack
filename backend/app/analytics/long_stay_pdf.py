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
    search: Optional[str] = None
) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
    """
    Extracts and evaluates uninterrupted continuous occupancy chains for all guests.
    Sorts descending from 30+ nights down to lesser continuous stay customers.
    Ignores guests who did not stay continuously in a row (e.g. breaks/gaps between stays).
    """
    prop = None
    if property_id:
        prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        prop = db.query(Property).first()

    prop_name = prop.name if prop else "Motel 6"
    target_property_id = prop.id if prop else 1

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

        if not records:
            continue

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

        if not unique_spans:
            continue

        unique_spans.sort(key=lambda s: (s["start"], s["end"]))

        # Chain consecutive stays ("stayed in a row")
        chains = []
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
            # This represents an uninterrupted continuous stay
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
                # Gap in stay -> Chain broken! Not stayed in a row.
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

        # Check all continuous chains for this guest
        for c in chains:
            if c["nights"] >= min_nights:
                if c["nights"] >= 30:
                    cat = "30+ Nights"
                    cat_key = "30+"
                elif c["nights"] >= 21:
                    cat = "21+ Nights"
                    cat_key = "21+"
                elif c["nights"] >= 14:
                    cat = "14+ Nights"
                    cat_key = "14+"
                elif c["nights"] >= 7:
                    cat = "7+ Nights"
                    cat_key = "7+"
                else:
                    cat = "< 7 Nights"
                    cat_key = "<7"

                results.append({
                    "guest_name": identity.normalized_name,
                    "check_in": c["start"],
                    "check_out": c["end"],
                    "total_nights": c["nights"],
                    "rooms_count": len(c["rooms"]) if c["rooms"] else 1,
                    "rooms_list": sorted(list(c["rooms"])),
                    "category": cat,
                    "category_key": cat_key,
                    "extended": "Yes" if c["extensions"] > 0 else "No",
                    "ext_count": c["extensions"],
                    "confirmations": c["confs"]
                })

    # Optional search filtering (by guest name, room number, or confirmation number)
    if search:
        s = search.strip().upper()
        results = [
            r for r in results
            if s in r["guest_name"].upper()
            or any(s in rm.upper() for rm in r["rooms_list"])
            or any(s in cf.upper() for cf in r["confirmations"])
        ]

    # Order from 30+ days descending to lesser continuous stay customers
    results.sort(key=lambda x: (-x["total_nights"], x["check_in"], x["guest_name"]))

    # Aggregate counts for header summary badges
    counts = {"30+": 0, "21+": 0, "14+": 0, "7+": 0}
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
                "tier": "30+ NIGHTS",
                "count": self.counts.get("30+", 0),
                "badge": "TAX EXEMPT TIER",
                "sub": "Monthly residency alert",
                "accent": "#f43f5e",
                "bg": "#1e1524",
                "border": "#4c1d30"
            },
            {
                "tier": "21–29 NIGHTS",
                "count": self.counts.get("21+", 0),
                "badge": "APPROACHING 30",
                "sub": "3+ weeks continuous",
                "accent": "#f59e0b",
                "bg": "#211a14",
                "border": "#4d3516"
            },
            {
                "tier": "14–20 NIGHTS",
                "count": self.counts.get("14+", 0),
                "badge": "MID-STAY",
                "sub": "Bi-weekly occupancy",
                "accent": "#38bdf8",
                "bg": "#121d2e",
                "border": "#1e3759"
            },
            {
                "tier": "7–13 NIGHTS",
                "count": self.counts.get("7+", 0),
                "badge": "WEEKLY",
                "sub": "1–2 weeks continuous",
                "accent": "#10b981",
                "bg": "#112220",
                "border": "#194a3e"
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
    """Confirmation numbers arranged in a sleek 2-column tag layout."""
    def __init__(self, conf_list: List[str], max_width: float = 140):
        super().__init__()
        self.conf_list = conf_list or []
        self.max_width = max_width
        self.tag_w = 82
        self.tag_h = 15
        self.gap_x = 5
        self.gap_y = 3.5

        cols = 2 if len(self.conf_list) > 1 else 1
        n = len(self.conf_list)
        rows = max(1, (n + cols - 1) // cols) if n > 0 else 1
        self.rows = rows
        self.cols = cols
        self.total_h = rows * self.tag_h + (rows - 1) * self.gap_y if n > 0 else self.tag_h

    def wrap(self, availWidth, availHeight):
        return self.max_width, self.total_h

    def draw(self):
        if not self.conf_list:
            return
        self.canv.saveState()
        for idx, conf in enumerate(self.conf_list):
            r = idx // self.cols
            c = idx % self.cols
            x = c * (self.tag_w + self.gap_x)
            y = self.total_h - ((r + 1) * self.tag_h + r * self.gap_y)

            self.canv.setFillColor(colors.HexColor("#151c2f"))
            self.canv.setStrokeColor(colors.HexColor("#243152"))
            self.canv.setLineWidth(0.8)
            self.canv.roundRect(x, y, self.tag_w, self.tag_h, 3, fill=1, stroke=1)

            self.canv.setFillColor(colors.HexColor("#94a3b8"))
            self.canv.setFont("Courier-Bold", 7.2)
            self.canv.drawCentredString(x + self.tag_w / 2.0, y + 4.2, str(conf))
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
        Paragraph("DURATION", th_center),
        Paragraph("TIER / CATEGORY", th_center),
        Paragraph("BOOKING TYPE & EXTENSIONS", th_center),
        Paragraph("CONFIRMATION NUMBERS", th_style),
    ]]

    # 6 columns summing to 720 pt
    col_widths = [160, 130, 80, 90, 120, 140]

    tier_labels = {
        "30+ Nights": ("30+ DAYS CONTINUOUS  •  MONTHLY RESIDENCY (TAX ALERT)", "#f43f5e", "#2a121e"),
        "21+ Nights": ("21–29 DAYS CONTINUOUS  •  APPROACHING MONTHLY TIER", "#f59e0b", "#2a1f12"),
        "14+ Nights": ("14–20 DAYS CONTINUOUS  •  BI-WEEKLY EXTENDED STAY", "#38bdf8", "#122338"),
        "7+ Nights": ("7–13 DAYS CONTINUOUS  •  WEEKLY EXTENDED OCCUPANCY", "#10b981", "#122b24"),
    }

    tier_pills = {
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
            "", "", "", "", ""
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
                    "", "", "", "", ""
                ]
                table_data.append(divider_row)

            # 1. Guest & Room column
            room_text = f"Room {', '.join(s['rooms_list'])}" if s['rooms_list'] else f"{s['rooms_count']} Room"
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

            # 3. Duration column
            duration_pill = PillTag(
                f"{s['total_nights']} Nights",
                bg_hex="#1e293b",
                text_hex="#ffffff",
                width=68,
                height=17,
                radius=4,
                font_size=8
            )

            # 4. Tier Badge column
            t_text, t_bg, t_fg = tier_pills.get(s["category"], (s["category"], "#1e293b", "#94a3b8"))
            tier_pill = PillTag(t_text, bg_hex=t_bg, text_hex=t_fg, width=74, height=17, radius=4, font_size=7.5)

            # 5. Booking Type & Extensions column
            if s["ext_count"] > 0:
                ext_pill = PillTag(
                    f"Extended ({s['ext_count']} Renewals)",
                    bg_hex="#3b2b13",
                    text_hex="#fbbf24",
                    width=108,
                    height=17,
                    radius=4,
                    font_size=7
                )
            else:
                ext_pill = PillTag(
                    "Single Booking (0 Ext)",
                    bg_hex="#161e31",
                    text_hex="#94a3b8",
                    width=108,
                    height=17,
                    radius=4,
                    font_size=7
                )

            # 6. Confirmation tags
            conf_flowable = ConfGridFlowable(s["confirmations"], max_width=140)

            row = [
                guest_cell,
                period_cell,
                duration_pill,
                tier_pill,
                ext_pill,
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
