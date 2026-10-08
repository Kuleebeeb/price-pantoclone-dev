"""Golden drawing units and Bangkok report dates from the CEO handoff."""
from datetime import date, datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.db import sample_number_day
from core.drawing import DrawingSpec, build_dim_rows, build_notes, dim_label, render_html, render_svg


class DocumentUnits(unittest.TestCase):
    def test_bangkok_numbering_rolls_at_local_midnight(self):
        self.assertEqual(sample_number_day(datetime(2026, 10, 8, 16, 59, 59, tzinfo=timezone.utc)), date(2026, 10, 8))
        self.assertEqual(sample_number_day(datetime(2026, 10, 8, 17, 0, 0, tzinfo=timezone.utc)), date(2026, 10, 9))
        self.assertEqual(sample_number_day(datetime(2026, 12, 31, 17, 0, 0, tzinfo=timezone.utc)), date(2027, 1, 1))

    def test_mixed_original_units_have_correct_inspection_limits(self):
        spec = DrawingSpec(doc_no="DFA-QA", customer="Synthetic QA", title="Bag", shape="flat_bag",
                           width_mm=101.6, length_mm=304.8, thickness_mm=0.08,
                           tol_dim_lo=-10, tol_dim_hi=10, display_unit="inch / cm",
                           dimension_units={"width": "inch", "length": "cm"})
        rows = {row.item: row for row in build_dim_rows(spec)}
        width, length, thick = rows["WIDTH"], rows[spec.length_label()], rows["THICKNESS"]
        self.assertEqual((width.unit, width.decimals), ("mm", 2))
        self.assertAlmostEqual(width.nominal, 101.6)
        self.assertAlmostEqual(width.lo, 91.6)
        self.assertAlmostEqual(width.hi, 111.6)
        self.assertEqual((length.unit, length.decimals), ("cm", 2))
        self.assertAlmostEqual(length.nominal, 30.48)
        self.assertAlmostEqual(length.lo, 29.48)
        self.assertAlmostEqual(length.hi, 31.48)
        self.assertEqual((thick.unit, thick.decimals), ("mm/side", 3))
        self.assertAlmostEqual(thick.nominal, 0.08)
        self.assertEqual(dim_label(spec, "width"), "WIDTH 4.00 inch (101.60 mm)")
        self.assertIn("30.48 cm", dim_label(spec, "length"))
        notes = " ".join(build_notes(spec))
        self.assertIn("+10.00 / -10.00 mm", notes)
        self.assertIn("+1.00 / -1.00 cm", notes)
        self.assertIn("1 inch = 25.40 mm", notes)

    def test_legacy_inch_drawing_without_original_units_still_renders(self):
        rows = build_dim_rows(DrawingSpec(doc_no="DFA-QA", customer="Synthetic QA", title="Bag", shape="flat_bag",
                                         width_mm=101.6, length_mm=304.8, display_unit="inch"))
        self.assertEqual(rows[0].unit, "inch")
        self.assertAlmostEqual(rows[0].nominal, 4)

    def test_cover_marks_open_bottom_without_inventing_an_author(self):
        spec = DrawingSpec(shape="product_cover", width_mm=450, length_mm=600, height_mm=1500,
                           title="Cover", customer="Synthetic QA", doc_no="DFA-QA")
        svg = render_svg(spec)
        self.assertIn("OPEN BOTTOM", svg)
        self.assertNotIn("อาญาดา", svg)
        html = render_html(spec)
        self.assertIn("Printed:", html)
        self.assertIn("Page 1 of 1", html)
        self.assertIn("DFA-QA", html)


if __name__ == "__main__":
    unittest.main()
