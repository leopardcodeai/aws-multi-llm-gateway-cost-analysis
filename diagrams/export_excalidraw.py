import json
import svgwrite

with open("diagrams/architecture.excalidraw") as f:
    data = json.load(f)

dwg = svgwrite.Drawing("diagrams/architecture.svg", size=("1200px", "800px"), viewBox="0 0 1200 800")

# Styles
colors = {
    "client": {"stroke": "#1976d2", "fill": "#e3f2fd"},
    "gateway": {"stroke": "#f57c00", "fill": "#fff3e0"},
    "cache": {"stroke": "#388e3c", "fill": "#e8f5e9"},
    "classifier": {"stroke": "#c2185b", "fill": "#fce4ec"},
    "models": {"stroke": "#7b1fa2", "fill": "#f3e5f5"},
    "fallback": {"stroke": "#fbc02d", "fill": "#fff8e1"},
    "obs": {"stroke": "#00796b", "fill": "#e0f2f1"},
    "storage": {"stroke": "#546e7a", "fill": "#eceff1"},
    "legend": {"stroke": "#999", "fill": "#fafafa"},
}

def add_rect(dwg, el, colors):
    style = colors.get(el["id"], {"stroke": "#333", "fill": "#fff"})
    dwg.add(dwg.rect(
        insert=(el["x"], el["y"]),
        size=(el["width"], el["height"]),
        rx=8, ry=8,
        stroke=style["stroke"],
        fill=style["fill"],
        stroke_width=2
    ))

def add_text(dwg, el):
    lines = el["text"].split("\n")
    y = el["y"]
    for line in lines:
        dwg.add(dwg.text(
            line,
            insert=(el["x"] + 10, y + 20),
            font_size=el.get("fontSize", 14),
            font_family="Arial, sans-serif",
            fill=el.get("strokeColor", "#333")
        ))
        y += el.get("fontSize", 14) * 1.3

def add_arrow(dwg, el):
    x1, y1 = el["x"], el["y"]
    x2, y2 = x1 + el["width"], y1 + el["height"]
    dwg.add(dwg.line(
        start=(x1, y1), end=(x2, y2),
        stroke="#666", stroke_width=2,
        marker_end="url(#arrowhead)"
    ))

# Arrowhead marker
defs = dwg.defs
marker = defs.add(dwg.marker(id="arrowhead", viewBox="0 0 10 10", refX=8, refY=5, markerWidth=6, markerHeight=6, orient="auto"))
marker.add(dwg.path(d="M 0 0 L 10 5 L 0 10 z", fill="#666"))

# Render elements in order
for el in data["elements"]:
    if el["type"] == "rectangle":
        add_rect(dwg, el, colors)
    elif el["type"] == "text":
        add_text(dwg, el)
    elif el["type"] == "arrow":
        add_arrow(dwg, el)

dwg.save()
print("SVG exported to diagrams/architecture.svg")
