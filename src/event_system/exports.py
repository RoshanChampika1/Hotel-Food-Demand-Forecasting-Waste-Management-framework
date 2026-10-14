"""Printable outputs: the Party Menu (kitchen notice board), the StockBalance (for the chef / stores)
and the kitchen recipe sheet, as one Excel workbook and as separate PDFs."""
import io

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from order_calc import SECTION_TITLE, STOCK_GROUPS

HOTEL = "RESHEEN Hotel & Banquets"
ADDRESS = "Kurunegala Rd, Kotadeniyawa."
BRAND = "#7a1f2b"
GOLD = "#c9a24a"


def header_rows(ev):
    return [
        ("Date of Event", ev["date"].strftime("%d %B %Y (%A)")),
        ("Type of Event", f'{ev["event_type"]} - {ev["session"].title()}'),
        ("Event No", ev["event_no"]),
        ("Hall", ev["hall"]),
        ("Location", ev["location"]),
        ("Food Serving Time", ev["serving_time"]),
        ("No of Pax (booked)", ev["booked"]),
        ("Cook for (safe guests)", f'{ev["guests"]}  (P{int(ev["level"] * 100)})'),
    ]


# ---------------------------------------------------------------- Excel
def to_excel(ev, menu, bite_kg, counts, sb, lines):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        wb = xw.book
        f = dict(
            hotel=wb.add_format(dict(bold=True, font_size=18, font_color=BRAND, align="center")),
            addr=wb.add_format(dict(italic=True, align="center", font_color="#555555")),
            title=wb.add_format(dict(bold=True, font_size=14, align="center", bottom=2, bottom_color=GOLD)),
            lab=wb.add_format(dict(bold=True, font_color="#333333")),
            val=wb.add_format(dict(font_color="#000000")),
            sec=wb.add_format(dict(bold=True, font_color="white", bg_color=BRAND, align="left")),
            dish=wb.add_format(dict(left=1, right=1, bottom=4, left_color="#cccccc", right_color="#cccccc",
                                    bottom_color="#dddddd")),
            num=wb.add_format(dict(num_format="0.00", align="right")),
            th=wb.add_format(dict(bold=True, bg_color="#f2e6d0", border=1)),
            td=wb.add_format(dict(border=1)),
            tdn=wb.add_format(dict(border=1, num_format="0.00")),
            grp=wb.add_format(dict(bold=True, font_color="white", bg_color=BRAND, border=1)),
            small=wb.add_format(dict(italic=True, font_color="#777777", font_size=9)),
        )

        # ---- Party Menu
        ws = wb.add_worksheet("Party Menu")
        ws.set_paper(9); ws.set_portrait(); ws.fit_to_pages(1, 0); ws.set_margins(0.4, 0.4, 0.5, 0.5)
        ws.set_column("A:A", 2); ws.set_column("B:B", 46); ws.set_column("C:C", 10); ws.set_column("D:D", 46)
        ws.set_column("E:E", 10)
        ws.merge_range("B1:E1", HOTEL, f["hotel"]); ws.merge_range("B2:E2", ADDRESS, f["addr"])
        ws.merge_range("B4:E4", "MENU CHART", f["title"])
        r = 5
        hr = header_rows(ev)
        for i, (k, v) in enumerate(hr):
            ws.write(r + i // 2, 1 if i % 2 == 0 else 3, f"{k}:  {v}", f["lab"])
        r += (len(hr) + 1) // 2 + 1
        # two columns of sections, filled in order, balancing length
        secs = [(s, menu[s]) for s in SECTION_TITLE if menu.get(s)]
        left, right, lh, rh = [], [], 0, 0
        for s, ds in secs:
            if lh <= rh:
                left.append((s, ds)); lh += len(ds) + 2
            else:
                right.append((s, ds)); rh += len(ds) + 2
        for col, block in ((1, left), (3, right)):
            rr = r
            for s, ds in block:
                ws.merge_range(rr, col, rr, col + 1, SECTION_TITLE[s], f["sec"]); rr += 1
                for d in ds:
                    ws.write(rr, col, d, f["dish"])
                    if s == "bites" and bite_kg.get(d):
                        ws.write(rr, col + 1, f"{bite_kg[d]:.2f} Kg", f["dish"])
                    elif counts.get(d):
                        ws.write(rr, col + 1, counts[d], f["dish"])
                    else:
                        ws.write(rr, col + 1, "", f["dish"])
                    rr += 1
                rr += 1

        # ---- StockBalance
        ws = wb.add_worksheet("StockBalance")
        ws.set_paper(9); ws.set_portrait(); ws.fit_to_pages(1, 0); ws.repeat_rows(9)
        widths = [10, 34, 7, 10, 10, 9, 9, 9, 9]
        for i, w in enumerate(widths):
            ws.set_column(i, i, w)
        ws.merge_range("A1:I1", HOTEL, f["hotel"]); ws.merge_range("A2:I2", ADDRESS, f["addr"])
        ws.merge_range("A3:I3", "STOCK BALANCE (Raw material demand)", f["title"])
        for i, (k, v) in enumerate(header_rows(ev)):
            ws.write(4 + i // 2, 0 if i % 2 == 0 else 4, f"{k}:  {v}", f["lab"])
        cols = ["Item Code", "Description", "Unit", "Demand", "Issue", "Jayalath", "Market", "Stores", "Return"]
        r = 9
        ws.write_row(r, 0, cols, f["th"]); r += 1
        for g in STOCK_GROUPS:
            part = sb[sb.group == g]
            if part.empty:
                continue
            ws.merge_range(r, 0, r, 8, f"{g.upper()} ITEMS  ({len(part)})", f["grp"]); r += 1
            for x in part.itertuples():
                ws.write(r, 0, x.item_code, f["td"]); ws.write(r, 1, x.description, f["td"])
                ws.write(r, 2, x.unit, f["td"]); ws.write_number(r, 3, round(x.demand, 3), f["tdn"])
                ws.write_number(r, 4, x.issue, f["tdn"])
                for c in range(5, 9):
                    ws.write_blank(r, c, None, f["td"])
                r += 1
        r += 1
        bites = [(d, k) for d, k in bite_kg.items() if k]
        if bites:
            ws.write(r, 1, "NOTE: bites prepared (Kg)", f["lab"]); r += 1
            for d, k in bites:
                ws.write(r, 1, d); ws.write_number(r, 3, round(k, 2), f["num"]); r += 1
        ws.write(r + 1, 1, "Demand = recipe quantity x guests to cook for (hotel recipe book). "
                           "Issue = rounded up to whole packets/bottles or 50 g.", f["small"])

        # ---- Kitchen recipes
        ws = wb.add_worksheet("Kitchen Recipes")
        ws.set_paper(9); ws.set_portrait(); ws.fit_to_pages(1, 0)
        for i, w in enumerate([10, 36, 8, 10, 26]):
            ws.set_column(i, i, w)
        ws.merge_range("A1:E1", HOTEL, f["hotel"])
        ws.merge_range("A2:E2", f'KITCHEN RECIPES  -  {ev["date"]:%d %b %Y}  -  cook for {ev["guests"]} guests',
                       f["title"])
        r = 3
        if not lines.empty:
            for (sec, dsh), part in lines.groupby(["menu_section", "dish"], sort=False):
                ws.merge_range(r, 0, r, 4, f'{SECTION_TITLE.get(sec, sec)}  -  {dsh}   ({part.how.iloc[0]})', f["sec"])
                r += 1
                ws.write_row(r, 0, ["Code", "Ingredient", "Unit", "Qty", "Recipe qty (base)"], f["th"]); r += 1
                for x in part.itertuples():
                    ws.write(r, 0, x.item_code, f["td"]); ws.write(r, 1, x.item_name, f["td"])
                    ws.write(r, 2, x.unit, f["td"]); ws.write_number(r, 3, round(x.demand, 3), f["tdn"])
                    ws.write(r, 4, f"{x.qty:g} {x.recipe_unit}", f["td"]); r += 1
                r += 1
    return buf.getvalue()


# ---------------------------------------------------------------- PDF
def _styles():
    ss = getSampleStyleSheet()
    return dict(
        hotel=ParagraphStyle("hotel", parent=ss["Title"], textColor=colors.HexColor(BRAND), fontSize=20,
                             leading=24, spaceAfter=2),
        addr=ParagraphStyle("addr", parent=ss["Normal"], alignment=1, textColor=colors.grey, fontSize=9),
        title=ParagraphStyle("title", parent=ss["Heading2"], alignment=1, spaceBefore=6, spaceAfter=6),
        sec=ParagraphStyle("sec", parent=ss["Heading4"], textColor=colors.white, fontSize=10, leading=12),
        cell=ParagraphStyle("cell", parent=ss["Normal"], fontSize=9, leading=11),
        small=ParagraphStyle("small", parent=ss["Normal"], fontSize=7.5, textColor=colors.grey),
    )


def _head(ev, st, title):
    rows = header_rows(ev)
    data = [[Paragraph(f"<b>{rows[i][0]}:</b> {rows[i][1]}", st["cell"]),
             Paragraph(f"<b>{rows[i + 1][0]}:</b> {rows[i + 1][1]}", st["cell"]) if i + 1 < len(rows) else ""]
            for i in range(0, len(rows), 2)]
    t = Table(data, colWidths=[95 * mm, 85 * mm])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(GOLD)),
                           ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf6ec")),
                           ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
    return [Paragraph(HOTEL, st["hotel"]), Paragraph(ADDRESS, st["addr"]), Paragraph(title, st["title"]), t,
            Spacer(1, 5 * mm)]


def _section_table(title, rows, st, width):
    data = [[Paragraph(title, st["sec"]), ""]] + [[Paragraph(a, st["cell"]), Paragraph(b, st["cell"])]
                                                   for a, b in rows]
    t = Table(data, colWidths=[width - 22 * mm, 22 * mm])
    t.setStyle(TableStyle([
        ("SPAN", (0, 0), (1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor(BRAND)),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
    return t


def party_menu_pdf(ev, menu, bite_kg, counts):
    st, buf = _styles(), io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm, title="Party Menu")
    story = _head(ev, st, "MENU CHART")
    secs = [(s, menu[s]) for s in SECTION_TITLE if menu.get(s)]
    colw = 89 * mm
    left, right, lh, rh = [], [], 0, 0
    for s, ds in secs:
        rows = [(d, f"{bite_kg[d]:.2f} Kg" if s == "bites" and bite_kg.get(d) else str(counts.get(d) or ""))
                for d in ds]
        t = _section_table(SECTION_TITLE[s], rows, st, colw)
        if lh <= rh:
            left += [t, Spacer(1, 3 * mm)]; lh += len(ds) + 2
        else:
            right += [t, Spacer(1, 3 * mm)]; rh += len(ds) + 2
    outer = Table([[left, right]], colWidths=[colw + 3 * mm, colw + 3 * mm])
    outer.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(outer)
    doc.build(story)
    return buf.getvalue()


def stock_balance_pdf(ev, sb, bite_kg):
    st, buf = _styles(), io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=10 * mm, rightMargin=10 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm, title="Stock Balance")
    story = _head(ev, st, "STOCK BALANCE  (Raw material demand)")
    head = ["Code", "Description", "Unit", "Demand", "Issue", "Jayalath", "Market", "Stores", "Return"]
    widths = [16, 58, 12, 17, 15, 17, 17, 17, 17]
    for g in STOCK_GROUPS:
        part = sb[sb.group == g]
        if part.empty:
            continue
        data = [[f"{g.upper()} ITEMS ({len(part)})"] + [""] * 8, head]
        for x in part.itertuples():
            data.append([x.item_code, Paragraph(x.description, st["cell"]), x.unit, f"{x.demand:.3f}",
                         f"{x.issue:g}", "", "", "", ""])
        t = Table(data, colWidths=[w * mm for w in widths], repeatRows=2)
        t.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f2e6d0")),
            ("GRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#999999")), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("ALIGN", (3, 2), (4, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        story += [t, Spacer(1, 4 * mm)]
    bites = [(d, k) for d, k in bite_kg.items() if k]
    if bites:
        story.append(Paragraph("<b>Bites prepared:</b> " + ", ".join(f"{d} {k:.2f} Kg" for d, k in bites),
                               st["cell"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Demand = hotel recipe quantity x guests to cook for. Issue = rounded up to whole "
                           "packets/bottles or 50 g. Fill Jayalath / Market / Stores / Return when issuing.",
                           st["small"]))
    doc.build(story)
    return buf.getvalue()


def recipes_pdf(ev, lines):
    st, buf = _styles(), io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm,
                            bottomMargin=10 * mm, title="Kitchen Recipes")
    story = _head(ev, st, "KITCHEN RECIPES")
    for (sec, dsh), part in lines.groupby(["menu_section", "dish"], sort=False):
        data = [[f"{SECTION_TITLE.get(sec, sec)}  -  {dsh}", "", "", ""], ["Code", "Ingredient", "Unit", "Qty"]]
        data += [[x.item_code, Paragraph(x.item_name, st["cell"]), x.unit, f"{x.demand:.3f}"]
                 for x in part.itertuples()]
        t = Table(data, colWidths=[20 * mm, 110 * mm, 20 * mm, 25 * mm])
        t.setStyle(TableStyle([
            ("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BRAND)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f2e6d0")), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 1), (-1, -1), 0.3, colors.HexColor("#999999")), ("ALIGN", (3, 2), (3, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]))
        story += [KeepTogether(t), Spacer(1, 3 * mm)]
    doc.build(story)
    return buf.getvalue()
