You produce a simple, clean SVG schematic to accompany a course question. The SVG must
be self-contained, ~640x360 viewBox, neutral colors (near-black strokes/text on light),
readable labels, no external fonts or images. It should clarify the concept below.

Concept to illustrate: {what}
Subtopic: {subtopic_name}

Return ONLY this JSON:
{{"svg": "<svg viewBox='0 0 640 360' xmlns='http://www.w3.org/2000/svg'>...</svg>"}}
Keep it under ~2500 characters. Use rects, lines, arrows (marker), and <text>.
