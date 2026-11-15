import io
import os
import html
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

st.set_page_config(
    page_title="PlantCare AI | Leaf Health",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)


MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "200"))

try:
    API_URL = str(
        st.secrets.get(
            "API_URL",
            os.getenv("API_URL", "http://127.0.0.1:8000")
        )
    ).strip().rstrip("/")
except Exception:
    API_URL = os.getenv(
        "API_URL",
        "http://127.0.0.1:8000"
    ).strip().rstrip("/")

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")


# =========================================================
# RESULT NORMALIZATION
# =========================================================

def _as_text_list(value):
    if value is None or value == "":
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

    if isinstance(value, tuple):
        return [
            str(item).strip()
            for item in value
            if item is not None and str(item).strip()
        ]

    if isinstance(value, dict):
        return [f"{key}: {val}" for key, val in value.items()]

    return [
        line.strip(" •-\t")
        for line in str(value).splitlines()
        if line.strip(" •-\t")
    ]


def normalize_result(payload):
    """Normalize Hindi and English keys returned by backend."""

    if not isinstance(payload, dict):
        return {}

    data = dict(payload)

    nested_hi = (
        data.get("hindi")
        if isinstance(data.get("hindi"), dict)
        else {}
    )

    aliases = {
        "disease_name_hi": ("disease_name_hindi",),
        "disease_type_hi": ("disease_type_hindi",),
        "severity_hi": ("severity_hindi",),

        "symptoms_hi": (
            "hindi_symptoms",
            "symptoms_hindi"
        ),

        "possible_causes_hi": (
            "hindi_causes",
            "causes_hi",
            "causes_hindi",
            "possible_causes_hindi"
        ),

        "treatment_hi": (
            "hindi_treatment",
            "treatment_hindi"
        ),

        "hindi_explanation": (
            "explanation_hi",
            "explanation_hindi",
            "disease_explanation_hi"
        ),
    }

    nested_aliases = {
        "disease_name_hi": ("disease_name", "name"),
        "disease_type_hi": ("disease_type", "type"),
        "severity_hi": ("severity",),
        "symptoms_hi": ("symptoms",),
        "possible_causes_hi": ("possible_causes", "causes"),
        "treatment_hi": ("treatment",),
        "hindi_explanation": ("explanation", "description"),
    }

    for target, source_keys in aliases.items():

        if data.get(target) in (None, "", []):

            for key in source_keys:

                if data.get(key) not in (None, "", []):

                    data[target] = data[key]
                    break

        if data.get(target) in (None, "", []) and nested_hi:

            for key in nested_aliases.get(target, ()):

                if nested_hi.get(key) not in (None, "", []):

                    data[target] = nested_hi[key]
                    break

    # Original backend fields and frontend aliases

    mappings = [
        ("symptoms_hi", "hindi_symptoms"),
        ("possible_causes_hi", "hindi_causes"),
        ("treatment_hi", "hindi_treatment"),
    ]

    for canonical, alias in mappings:

        if data.get(canonical) in (None, "", []):

            if data.get(alias) not in (None, "", []):

                data[canonical] = data[alias]

        data[canonical] = _as_text_list(data.get(canonical))
        data[alias] = data[canonical]

    # Normalize English fields

    for key in (
        "symptoms",
        "possible_causes",
        "treatment"
    ):
        data[key] = _as_text_list(data.get(key))

    # Generate a short Hindi summary from actual Hindi fields

    if not data.get("hindi_explanation"):

        disease_hi = data.get("disease_name_hi")
        severity_hi = data.get("severity_hi")

        if disease_hi:

            summary = f"पहचाना गया रोग: {disease_hi}।"

            if severity_hi:
                summary += f" गंभीरता: {severity_hi}।"

            data["hindi_explanation"] = summary

    return data


# =========================================================
# RESPONSIVE UI STYLING
# =========================================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');

:root {
  --pc-bg: #07130f;
  --pc-panel: #0e211a;
  --pc-panel-2: #122a20;
  --pc-line: rgba(177, 231, 193, .13);
  --pc-text: #eff8f0;
  --pc-muted: #a8c4b1;
  --pc-green: #9ce6ad;
  --pc-lime: #c5f18b;
}

.stApp {
  background:
    radial-gradient(ellipse at 8% 0%, rgba(67, 145, 91, .18), transparent 34%),
    radial-gradient(ellipse at 95% 12%, rgba(123, 180, 100, .10), transparent 30%),
    linear-gradient(145deg, #06100c 0%, #091b14 55%, #0b2118 100%);
  color: var(--pc-text);
  font-family: 'DM Sans', sans-serif;
}

.block-container {
  max-width: 1220px;
  padding-top: 1.35rem;
  padding-bottom: 3rem;
}

h1, h2, h3, h4, p, label, span {
  color: var(--pc-text);
}

h1, h2, h3 {
  font-family: 'Manrope', sans-serif;
  letter-spacing: -.025em;
}

.hero {
  border: 1px solid var(--pc-line);
  background: linear-gradient(120deg, rgba(19, 53, 37, .94), rgba(12, 34, 25, .88));
  border-radius: 26px;
  padding: clamp(22px, 4vw, 42px);
  position: relative;
  overflow: hidden;
  margin-bottom: 1.2rem;
}

.hero:after {
  content: "🌿";
  position: absolute;
  right: 4%;
  top: 4%;
  font-size: clamp(75px, 12vw, 150px);
  opacity: .10;
}

.eyebrow {
  color: var(--pc-green);
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: .14em;
  font-size: .73rem;
  margin-bottom: .55rem;
}

.hero-title {
  font-size: clamp(1.9rem, 4vw, 3.1rem);
  line-height: 1.12;
  font-weight: 800;
  margin: 0;
}

.hero-sub {
  color: #c3d9ca !important;
  max-width: 700px;
  font-size: 1rem;
  margin-top: .8rem;
}

.pill {
  display: inline-block;
  border: 1px solid rgba(156,230,173,.25);
  background: rgba(156,230,173,.09);
  color: #bdf2c8;
  border-radius: 999px;
  padding: 6px 11px;
  font-size: .78rem;
  font-weight: 700;
  margin: 5px 5px 0 0;
}

.section-kicker {
  color: #9ce6ad;
  font-weight: 800;
  letter-spacing: .10em;
  font-size: .72rem;
  text-transform: uppercase;
}

.panel {
  border: 1px solid var(--pc-line);
  background: rgba(12, 31, 23, .78);
  border-radius: 20px;
  padding: clamp(15px, 2.2vw, 23px);
}

div[data-testid="stFileUploader"],
div[data-testid="stCameraInput"] {
  border: 1px dashed rgba(156,230,173,.36);
  background: rgba(255,255,255,.025);
  border-radius: 16px;
  padding: 12px;
}

div[data-testid="stImage"] {
  width: 100%;
  border-radius: 16px;
  overflow: hidden;
  background: rgba(0,0,0,.20);
}

div[data-testid="stImage"] img {
  display: block;
  width: 100% !important;
  max-width: 100% !important;
  height: auto !important;
  max-height: 560px;
  object-fit: contain;
  margin: 0 auto;
}

.stButton > button,
.stDownloadButton > button {
  background: linear-gradient(120deg, #c5f18b, #8de2a8);
  color: #092016 !important;
  border: 0;
  border-radius: 13px;
  font-weight: 800;
  min-height: 3rem;
  width: 100%;
  box-shadow: 0 8px 22px rgba(83, 177, 111, .13);
}

.stButton > button:hover,
.stDownloadButton > button:hover {
  background: linear-gradient(120deg, #d6ffa2, #a0f0b8);
  color: #07170f !important;
  border: 0;
}

div[data-testid="stRadio"] label {
  color: #e9f6ec !important;
}

div[data-testid="stMetric"] {
  background: rgba(156,230,173,.075);
  border: 1px solid var(--pc-line);
  border-radius: 15px;
  padding: 13px 15px;
}

.result-head {
  border: 1px solid rgba(156,230,173,.23);
  background: linear-gradient(120deg, rgba(24,67,44,.85), rgba(13,38,27,.88));
  border-radius: 20px;
  padding: 22px;
  margin: 1rem 0;
}

.result-name {
  font-size: clamp(1.35rem, 3vw, 2rem);
  font-weight: 800;
  margin: 0;
}

.result-hi {
  color: #bdecc7 !important;
  font-size: 1.1rem;
  margin-top: .35rem;
}

.info-card {
  height: 100%;
  border: 1px solid var(--pc-line);
  background: rgba(15,39,28,.78);
  border-radius: 16px;
  padding: 17px;
}

.info-card h4 {
  margin: 0 0 .7rem 0;
  color: #b9efc4 !important;
  font-size: 1rem;
}

.muted {
  color: var(--pc-muted) !important;
  font-size: .88rem;
}

hr {
  border-color: rgba(177,231,193,.12) !important;
}

[data-testid="stCaptionContainer"] p {
  color: #a9c4b2 !important;
}

@media (max-width: 640px) {
  .block-container {
    padding-left: .8rem;
    padding-right: .8rem;
  }

  .hero {
    border-radius: 19px;
  }

  div[data-testid="stImage"] img {
    max-height: 390px;
  }
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# HINDI FONT HANDLING
# =========================================================

def _find_hindi_font():
    """Find a Devanagari font or extract Nirmala from Windows TTC."""

    candidates = [
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/NirmalaUI.ttf"),
        Path("C:/Windows/Fonts/NirmalaB.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagariUI-Regular.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.ttf"),
    ]

    for candidate in candidates:

        if candidate.exists():
            return candidate

    ttc_path = Path("C:/Windows/Fonts/Nirmala.ttc")

    if not ttc_path.exists():
        return None

    try:

        from fontTools.ttLib import TTCollection

        generated_dir = (
            Path(__file__).resolve().parent / ".generated_fonts"
        )

        generated_dir.mkdir(parents=True, exist_ok=True)

        extracted_path = generated_dir / "Nirmala-Regular.ttf"

        if (
            extracted_path.exists()
            and extracted_path.stat().st_mtime >= ttc_path.stat().st_mtime
        ):
            return extracted_path

        collection = TTCollection(str(ttc_path), lazy=False)

        selected = None

        for face in collection.fonts:

            family = ""

            if "name" in face:

                for record in face["name"].names:

                    if record.nameID in (1, 4, 6):

                        try:
                            family = record.toUnicode()
                        except Exception:
                            family = ""

                        if "Nirmala" in family:
                            selected = face
                            break

            if selected is not None:
                break

        if selected is None and collection.fonts:
            selected = collection.fonts[0]

        if selected is None:
            return None

        selected.save(str(extracted_path))

        return extracted_path

    except Exception as exc:

        print(f"Could not extract Nirmala.ttc: {exc}")

        return None


# =========================================================
# PDF REPORT GENERATOR
# =========================================================

def make_pdf_report(image_bytes, filename, result):

    result = normalize_result(result)

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Image as RLImage,
        Table,
        TableStyle,
    )

    output = io.BytesIO()

    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=17 * mm,
        leftMargin=17 * mm,
        topMargin=16 * mm,
        bottomMargin=17 * mm,
        title="Plant Leaf Disease Analysis Report",
        author="PlantCare AI",
    )

    styles = getSampleStyleSheet()

    green = colors.HexColor("#245C3B")
    dark = colors.HexColor("#183528")
    muted = colors.HexColor("#53675B")
    pale = colors.HexColor("#EDF6EF")

    hindi_font_path = _find_hindi_font()

    hindi_available = False

    if hindi_font_path:

        try:

            try:
                pdfmetrics.registerFont(
                    TTFont(
                        "HindiDevanagari",
                        str(hindi_font_path),
                        shapable=True
                    )
                )

            except TypeError:

                pdfmetrics.registerFont(
                    TTFont(
                        "HindiDevanagari",
                        str(hindi_font_path)
                    )
                )

            hindi_available = True

        except Exception as exc:

            print(f"Hindi font registration failed: {exc}")

            hindi_available = False

    styles.add(ParagraphStyle(
        name="ReportTitlePC",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=21,
        leading=26,
        textColor=green,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name="SubPC",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=muted,
        spaceAfter=10
    ))

    styles.add(ParagraphStyle(
        name="SectionPC",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=green,
        spaceBefore=11,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name="BodyPC",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=dark,
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        name="HindiPC",
        parent=styles["BodyText"],
        fontName="HindiDevanagari" if hindi_available else "Helvetica",
        fontSize=9,
        leading=14,
        textColor=dark,
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        name="SmallPC",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=muted
    ))

    def para(value, style="BodyPC"):

        value = "" if value is None else str(value)

        return Paragraph(
            escape(value).replace("\n", "<br/>"),
            styles[style]
        )

    story = [
        Paragraph(
            "Plant Leaf Disease Detection",
            styles["ReportTitlePC"]
        ),

        Paragraph(
            "AI-assisted plant health report / पौधों के स्वास्थ्य की जाँच रिपोर्ट",
            styles["SubPC"]
        ),
    ]

    timestamp = (
        result.get("analysis_timestamp")
        or datetime.now().astimezone().isoformat()
    )

    meta = [
        [
            para("Report generated", "SmallPC"),
            para(datetime.now().strftime("%d %b %Y, %I:%M %p"))
        ],
        [
            para("Image file", "SmallPC"),
            para(filename)
        ],
        [
            para("AI analysis time", "SmallPC"),
            para(timestamp)
        ],
    ]

    meta_table = Table(
        meta,
        colWidths=[38 * mm, 130 * mm]
    )

    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pale),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5E6D9")),
        ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#D5E6D9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story += [
        meta_table,
        Spacer(1, 10)
    ]

    # Uploaded image

    try:

        with Image.open(io.BytesIO(image_bytes)) as im:

            im = ImageOps.exif_transpose(im).convert("RGB")

            im.thumbnail((1500, 1100), Image.Resampling.LANCZOS)

            image_buffer = io.BytesIO()

            im.save(
                image_buffer,
                format="JPEG",
                quality=88,
                optimize=True
            )

            image_buffer.seek(0)

        report_image = RLImage(image_buffer)

        max_w = 165 * mm
        max_h = 100 * mm

        scale = min(
            max_w / report_image.imageWidth,
            max_h / report_image.imageHeight,
            1
        )

        report_image.drawWidth = report_image.imageWidth * scale
        report_image.drawHeight = report_image.imageHeight * scale

        story += [
            Paragraph(
                "Uploaded leaf image / अपलोड की गई पत्ते की तस्वीर",
                styles["SectionPC"]
            ),
            report_image,
            Spacer(1, 7)
        ]

    except Exception:

        story.append(
            para("The uploaded image could not be embedded in this report.", "SmallPC")
        )

    disease_en = result.get("disease_name") or "Not specified"
    disease_hi = result.get("disease_name_hi") or "उपलब्ध नहीं"

    story += [
        Paragraph(
            "Detection summary / पहचान का सारांश",
            styles["SectionPC"]
        ),

        para(f"Disease: {disease_en}"),

        para(f"रोग: {disease_hi}", "HindiPC"),
    ]

    summary_rows = [
        [
            para("Disease type / रोग का प्रकार", "SmallPC"),
            para(result.get("disease_type", "N/A")),
            para(result.get("disease_type_hi", "उपलब्ध नहीं"), "HindiPC")
        ],
        [
            para("Severity / गंभीरता", "SmallPC"),
            para(result.get("severity", "N/A")),
            para(result.get("severity_hi", "उपलब्ध नहीं"), "HindiPC")
        ],
        [
            para("Confidence / भरोसे का स्तर", "SmallPC"),
            para(f"{result.get('confidence', 'N/A')}%"),
            para("AI का अनुमान", "HindiPC")
        ],
    ]

    summary_table = Table(
        summary_rows,
        colWidths=[52 * mm, 58 * mm, 58 * mm]
    )

    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), pale),
        ("BOX", (0, 0), (-1, -1), .5, colors.HexColor("#D5E6D9")),
        ("INNERGRID", (0, 0), (-1, -1), .3, colors.HexColor("#D5E6D9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(summary_table)

    # English and Hindi details

    sections = [
        ("Symptoms / लक्षण", "symptoms", "symptoms_hi"),
        ("Possible causes / संभावित कारण", "possible_causes", "possible_causes_hi"),
        ("Treatment & care / उपचार और देखभाल", "treatment", "treatment_hi"),
    ]

    for title, en_key, hi_key in sections:

        story.append(
            Paragraph(title, styles["SectionPC"])
        )

        en_items = result.get(en_key) or []
        hi_items = result.get(hi_key) or []

        rows = []

        max_items = max(
            len(en_items),
            len(hi_items)
        )

        if not max_items:

            rows.append([
                para("Not provided"),
                para("जानकारी उपलब्ध नहीं है।", "HindiPC")
            ])

        else:

            for i in range(max_items):

                en = (
                    f"• {en_items[i]}"
                    if i < len(en_items)
                    else "—"
                )

                hi = (
                    f"• {hi_items[i]}"
                    if i < len(hi_items)
                    else "—"
                )

                rows.append([
                    para(en),
                    para(hi, "HindiPC")
                ])

        section_table = Table(
            rows,
            colWidths=[84 * mm, 84 * mm]
        )

        section_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FBF8")),
            ("BOX", (0, 0), (-1, -1), .4, colors.HexColor("#DCE9DF")),
            ("INNERGRID", (0, 0), (-1, -1), .25, colors.HexColor("#E2ECE5")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))

        story.append(section_table)

    story += [
        Spacer(1, 12),

        para(
            "Disclaimer: This is AI-assisted visual guidance, not a laboratory diagnosis. Confirm serious, spreading, or uncertain symptoms with a qualified local agriculture expert.",
            "SmallPC"
        ),

        para(
            "अस्वीकरण: यह AI द्वारा तस्वीर के आधार पर दी गई सामान्य जानकारी है, प्रयोगशाला जाँच नहीं। गंभीर या फैलते लक्षणों के लिए कृषि विशेषज्ञ से सलाह लें।",
            "HindiPC"
        ),
    ]

    def footer(canvas, document):

        canvas.saveState()

        canvas.setStrokeColor(
            colors.HexColor("#D5E6D9")
        )

        canvas.line(
            17 * mm,
            13 * mm,
            A4[0] - 17 * mm,
            13 * mm
        )

        canvas.setFont("Helvetica", 8)

        canvas.setFillColor(muted)

        canvas.drawString(
            17 * mm,
            8 * mm,
            "PlantCare AI · Plant Leaf Disease Detection"
        )

        canvas.drawRightString(
            A4[0] - 17 * mm,
            8 * mm,
            f"Page {document.page}"
        )

        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer
    )

    return output.getvalue(), hindi_available


# =========================================================
# HEADER
# =========================================================

st.markdown("""
<div class="hero">
  <div class="eyebrow">Plant health intelligence · पौधों की सेहत</div>
  <div class="hero-title">PlantCare AI</div>

  <p class="hero-sub">
    Detect leaf diseases, understand symptoms, and get practical care guidance — in English and Hindi.
  </p>

  <span class="pill">AI leaf analysis</span>
  <span class="pill">Camera + image upload</span>
  <span class="pill">हिंदी + English</span>
  <span class="pill">PDF report</span>
</div>
""", unsafe_allow_html=True)


# =========================================================
# PHOTO INPUT
# =========================================================

st.markdown(
    '<div class="section-kicker">01 · Add a leaf photo / पत्ते की फोटो जोड़ें</div>',
    unsafe_allow_html=True
)

st.write(
    "Upload a clear image or capture one using your device camera. / साफ फोटो अपलोड करें या डिवाइस के कैमरे से खींचें।"
)

upload_tab, camera_tab = st.tabs([
    "📁 Upload photo / फोटो अपलोड",
    "📷 Camera / कैमरा"
])

image_file = None

with upload_tab:

    image_file = st.file_uploader(
        "Choose JPG, PNG, WEBP, BMP or TIFF",
        type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff"],
        help=f"Application limit: {MAX_UPLOAD_MB} MB. Streamlit's server upload limit must be set at least this high.",
        key="leaf_file_upload",
    )

with camera_tab:

    camera_file = st.camera_input(
        "Take a clear, well-lit photo of one leaf / पत्ते की साफ और रोशनी वाली फोटो लें",
        key="leaf_camera_capture",
    )

    if camera_file is not None:
        image_file = camera_file


# =========================================================
# IMAGE PREVIEW AND ANALYSIS
# =========================================================

if image_file is not None:

    raw_image = image_file.getvalue()

    filename = getattr(image_file, "name", None) or "camera_capture.jpg"

    mime_type = getattr(image_file, "type", None) or "image/jpeg"

    st.markdown(
        '<div class="section-kicker">02 · Preview / फोटो देखें</div>',
        unsafe_allow_html=True
    )

    preview_col, detail_col = st.columns(
        [1.25, 0.75],
        gap="large"
    )

    with preview_col:

        with st.container(border=True):

            st.image(
                raw_image,
                caption="Selected leaf photo / चुनी हुई फोटो",
                width="stretch"
            )

    with detail_col:

        st.markdown(
            '<div class="panel">',
            unsafe_allow_html=True
        )

        st.markdown("**Image details / फोटो की जानकारी**")

        st.markdown(
            f"<p class='muted'>File: {escape(filename)}</p>",
            unsafe_allow_html=True
        )

        st.metric(
            "Original size / मूल आकार",
            f"{len(raw_image) / (1024 * 1024):.2f} MB"
        )

        st.markdown(
            f"""
            <p class='muted'>
            Maximum allowed: {MAX_UPLOAD_MB} MB.
            Large images are resized and compressed by the backend
            before being sent to the vision model.
            </p>

            <p class='muted'>
            अधिक आकार वाली फोटो को AI जाँच से पहले backend
            अपने-आप छोटा और compress करेगा।
            </p>
            """,
            unsafe_allow_html=True
        )

        st.markdown("</div>", unsafe_allow_html=True)

    if len(raw_image) > MAX_UPLOAD_MB * 1024 * 1024:

        st.error(
            f"Image is larger than {MAX_UPLOAD_MB} MB. / फोटो {MAX_UPLOAD_MB} MB से बड़ी है।"
        )

    elif st.button(
        "🔍 Analyze leaf / पत्ते की जाँच करें",
        use_container_width=True,
        type="primary"
    ):

        with st.spinner(
            "Analyzing image with AI… / AI फोटो की जाँच कर रहा है…"
        ):

            try:

                response = requests.post(
                    f"{API_URL}/disease-detection-file",

                    files={
                        "file": (
                            filename,
                            raw_image,
                            mime_type
                        )
                    },

                    timeout=(20, 300),
                )

                if response.status_code != 200:

                    try:
                        detail = response.json().get(
                            "detail",
                            response.text
                        )

                    except ValueError:
                        detail = response.text

                    st.error(
                        f"API Error ({response.status_code}): {detail}"
                    )

                else:

                    api_payload = response.json()

                    # Some API versions wrap the analysis in {"result": {...}}.
                    if isinstance(api_payload, dict) and isinstance(api_payload.get("result"), dict):
                        api_payload = api_payload["result"]

                    result = normalize_result(api_payload)

                    if not result:
                        st.error(
                            "The backend returned an empty or unrecognized result. "
                            "Check the FastAPI response schema."
                        )
                    else:
                        st.session_state["leaf_analysis_result"] = result

                        st.session_state["leaf_analysis_image"] = raw_image

                        st.session_state["leaf_analysis_filename"] = filename

                        st.session_state["leaf_analysis_mime"] = mime_type

                        st.rerun()

            except requests.Timeout:

                st.error(
                    "Request timed out. Try a smaller/clearer image or check the backend. / अनुरोध में समय लगा। छोटी या साफ फोटो के साथ दोबारा कोशिश करें।"
                )

            except requests.RequestException as exc:

                st.error(
                    f"Could not connect to backend: {exc}. Check API_URL and start FastAPI. / Backend से कनेक्शन नहीं हो पाया।"
                )


# =========================================================
# RESULTS
# =========================================================

result = st.session_state.get("leaf_analysis_result")

report_image = st.session_state.get("leaf_analysis_image")

report_filename = st.session_state.get(
    "leaf_analysis_filename",
    "leaf-photo.jpg"
)


if result and report_image:

    result = normalize_result(result)

    st.session_state["leaf_analysis_result"] = result

    st.divider()

    st.markdown(
        '<div class="section-kicker">03 · AI diagnosis / AI जाँच का परिणाम</div>',
        unsafe_allow_html=True
    )

    if result.get("disease_type") == "invalid_image":

        st.warning(
            "This does not appear to be a clear plant-leaf photo. / यह पौधे के पत्ते की साफ फोटो नहीं लग रही है।"
        )

    elif result.get("disease_detected"):

        st.success(
            "Possible disease detected / संभावित बीमारी मिली"
        )

    else:

        st.success(
            "No disease detected / कोई बीमारी नहीं मिली"
        )

    name_en = (
        result.get("disease_name")
        or (
            "Healthy leaf"
            if not result.get("disease_detected")
            else "Disease detected"
        )
    )

    name_hi = (
        result.get("disease_name_hi")
        or (
            "स्वस्थ पत्ता"
            if not result.get("disease_detected")
            else "बीमारी की पहचान"
        )
    )

    st.markdown(
        f"""
        <div class="result-head">

          <div class="eyebrow">
            Primary finding · मुख्य निष्कर्ष
          </div>

          <p class="result-name">
            {escape(str(name_en))}
          </p>

          <p class="result-hi">
            {escape(str(name_hi))}
          </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    # DEBUG: actual fields received from backend

    with st.expander(
        "Debug: Hindi fields received from API",
        expanded=False
    ):

        st.json({
            "disease_name_hi": result.get("disease_name_hi"),
            "disease_type_hi": result.get("disease_type_hi"),
            "severity_hi": result.get("severity_hi"),
            "symptoms_hi": result.get("symptoms_hi"),
            "possible_causes_hi": result.get("possible_causes_hi"),
            "treatment_hi": result.get("treatment_hi"),
            "hindi_explanation": result.get("hindi_explanation"),
        })

    # Metrics

    m1, m2, m3 = st.columns(3)

    m1.metric(
        "Disease type / प्रकार",
        str(result.get("disease_type", "N/A"))
    )

    m2.metric(
        "Severity / गंभीरता",
        str(result.get("severity", "N/A"))
    )

    m3.metric(
        "Confidence / भरोसे का स्तर",
        f"{result.get('confidence', 'N/A')}%"
    )

    st.caption(
        f"हिंदी विवरण · प्रकार: {result.get('disease_type_hi', 'उपलब्ध नहीं')} | गंभीरता: {result.get('severity_hi', 'उपलब्ध नहीं')}"
    )

    # English and Hindi sections

    sections = [
        ("Symptoms", "लक्षण", "symptoms", "symptoms_hi"),
        ("Possible causes", "संभावित कारण", "possible_causes", "possible_causes_hi"),
        ("Treatment & care", "उपचार और देखभाल", "treatment", "treatment_hi"),
    ]

    for en_title, hi_title, en_key, hi_key in sections:

        st.markdown(
            f"### {en_title} / {hi_title}"
        )

        en_items = result.get(en_key) or []

        hi_items = result.get(hi_key) or []

        left, right = st.columns(2, gap="large")

        with left:

            with st.container(border=True):

                st.markdown(f"**🇬🇧 {en_title}**")

                if en_items:

                    for item in en_items:
                        st.markdown(f"- {item}")

                else:

                    st.caption("Not provided")

        with right:

            with st.container(border=True):

                st.markdown(f"**🇮🇳 {hi_title}**")

                if hi_items:

                    for item in hi_items:
                        st.markdown(f"- {item}")

                elif en_items:

                    st.write(
                        "हिंदी विवरण उपलब्ध नहीं है।"
                    )

                else:

                    st.caption(
                        "जानकारी उपलब्ध नहीं है।"
                    )

    # Hindi explanation

    if result.get("hindi_explanation"):

        st.markdown("### 🇮🇳 रोग का संक्षिप्त विवरण")

        with st.container(border=True):

            st.write(
                result["hindi_explanation"]
            )

    st.caption(
        f"Analysis time / जाँच का समय: {result.get('analysis_timestamp', 'N/A')}"
    )

    st.info(
        "AI-based visual guidance only; this is not a laboratory diagnosis. Confirm serious or spreading symptoms with a local agriculture expert. / यह AI द्वारा तस्वीर पर आधारित सामान्य सलाह है, प्रयोगशाला जाँच नहीं। गंभीर या फैलते लक्षणों के लिए कृषि विशेषज्ञ से सलाह लें।"
    )

    # =====================================================
    # PDF DOWNLOAD
    # =====================================================

    st.markdown(
        '<div class="section-kicker">04 · Download report / रिपोर्ट डाउनलोड करें</div>',
        unsafe_allow_html=True
    )

    try:

        pdf_bytes, hindi_font_available = make_pdf_report(
            report_image,
            report_filename,
            result
        )

        if not hindi_font_available:

            st.warning(
                "PDF में हिंदी सही दिखाने के लिए इस कंप्यूटर पर Nirmala UI या Noto Sans Devanagari font उपलब्ध होना चाहिए। Hindi font नहीं मिला, इसलिए PDF में हिंदी अक्षर सही render न भी हों।"
            )

        safe_name = (
            Path(report_filename)
            .stem
            .replace(" ", "_")[:45]
            or "leaf"
        )

        st.download_button(
            "⬇️ Download PDF report with leaf photo / फोटो सहित PDF रिपोर्ट डाउनलोड करें",

            data=pdf_bytes,

            file_name=f"plant_disease_report_{safe_name}.pdf",

            mime="application/pdf",

            use_container_width=True,
        )

    except Exception as exc:

        st.error(
            f"PDF generation error: {exc}"
        )

    # =====================================================
    # NEW ANALYSIS
    # =====================================================

    if st.button(
        "Clear analysis / नई जाँच शुरू करें",
        use_container_width=False
    ):

        for key in (
            "leaf_analysis_result",
            "leaf_analysis_image",
            "leaf_analysis_filename",
            "leaf_analysis_mime"
        ):

            st.session_state.pop(key, None)

        st.rerun()


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    f"PlantCare AI · Backend: {API_URL} · Maximum original upload: {MAX_UPLOAD_MB} MB · Reports include the submitted image."
)
