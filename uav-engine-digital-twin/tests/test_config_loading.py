from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from can_interface.can_sender import CANMapping


class TestConfigLoading(unittest.TestCase):
    def test_load_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.yaml"
            path.write_text(
                """
signals:
  rpm:
    can_id: 0x100
    unit: rpm
    scale: 1
""",
                encoding="utf-8",
            )
            mapping = CANMapping.load(path)
            self.assertIn("rpm", mapping.mappings)
            self.assertEqual(mapping.mappings["rpm"].can_id, 0x100)


if __name__ == "__main__":
    unittest.main()
