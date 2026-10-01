"""Regression coverage for HWND capability checks and screenshot coordinates.

No UI input or real screenshot capture is performed by these tests.
"""

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("guardian", ROOT / "scripts" / "screen_guardian_capture.py")
guardian = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guardian)

WINDOW = {
    "hwnd": 123,
    "rect": {"left": 47, "top": 64, "right": 932, "bottom": 903, "width": 885, "height": 839},
    "client_rect": {"left": 55, "top": 115, "right": 924, "bottom": 895, "width": 869, "height": 780},
}


class WindowReadinessTests(unittest.TestCase):
    def probe(self, grab, platform="nt"):
        libs = {"ImageGrab": SimpleNamespace(grab=grab), "Image": SimpleNamespace(__version__="test")}
        with mock.patch.object(guardian, "os", SimpleNamespace(name=platform)), \
                mock.patch.object(guardian, "import_capture_libs", return_value=(libs, None)):
            return guardian.window_adapter_status()[0]

    def test_legacy_pillow_is_not_reported_as_hwnd_ready(self):
        def legacy_grab(bbox=None, all_screens=False):
            self.fail("A readiness check must not capture pixels")

        status = self.probe(legacy_grab)
        self.assertTrue(status["dependencies_importable"])
        self.assertFalse(status["available"])
        self.assertFalse(status["probe"]["window_parameter_supported"])
        self.assertIn("11.2.1", status["import_error"])
        self.assertIn("--upgrade", status["install_hint"])

    def test_supported_api_is_ready_without_capturing(self):
        def modern_grab(window=None):
            self.fail("A readiness check must not capture pixels")

        status = self.probe(modern_grab)
        self.assertTrue(status["available"])
        self.assertFalse(status["probe"]["capture_tested"])

    def test_supported_api_still_requires_windows(self):
        def modern_grab(window=None):
            self.fail("No capture expected")

        self.assertFalse(self.probe(modern_grab, platform="posix")["available"])

    def test_missing_dependencies_return_install_hint(self):
        with mock.patch.object(guardian, "os", SimpleNamespace(name="nt")), \
                mock.patch.object(guardian, "import_capture_libs", return_value=(None, "No module named 'mss'")):
            status, _ = guardian.window_adapter_status()
        self.assertFalse(status["available"])
        self.assertFalse(status["dependencies_importable"])
        self.assertEqual(status["import_error"], "No module named 'mss'")


class WindowGeometryTests(unittest.TestCase):
    def setUp(self):
        self.config_patch = mock.patch.object(guardian, "load_config", return_value=copy.deepcopy(guardian.DEFAULT_CONFIG))
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.libs, error = guardian.import_capture_libs()
        self.assertIsNone(error, "Install scripts/requirements.txt before running window tests")
        self.client_image = self.libs["Image"].new("RGB", (869, 780), "white")
        self.client_image.paste("black", (0, 0, 24, 24))

    def capture(self, fallback=False, window=None):
        outer_image = self.libs["Image"].new("RGB", (885, 839), "white")
        calls = []

        def grab(window=None, bbox=None, all_screens=False):
            calls.append({"window": window, "bbox": bbox})
            if window is not None:
                if fallback:
                    raise OSError("direct capture unavailable")
                return self.client_image
            return outer_image

        libs = dict(self.libs, ImageGrab=SimpleNamespace(grab=grab))
        with mock.patch.object(guardian, "virtual_screen_rect", return_value={}), \
                mock.patch.object(guardian, "bbox_identity_probe", return_value={}):
            image, source, _ = guardian.grab_window_once(
                {"background_mode": "visible_fallback" if fallback else "strict"},
                {"id": "pillow-window"}, libs, window or WINDOW,
            )
        return image, source, calls

    def test_direct_hwnd_samples_entire_client_without_second_crop(self):
        image, source, calls = self.capture()
        self.assertEqual(image.size, (869, 780))
        self.assertEqual(source["capture_box"], WINDOW["client_rect"])
        self.assertEqual(source["image_space"], "window_client")
        crop = source["direct_window_content"]["client_crop_box"]
        self.assertEqual((crop["left"], crop["top"], crop["width"], crop["height"]), (0, 0, 869, 780))
        self.assertEqual(len(calls), 1)
        self.assertFalse(source["quiet_capture"]["foreground_activation_performed"])

    def test_visible_fallback_keeps_outer_window_coordinates(self):
        image, source, calls = self.capture(fallback=True)
        self.assertEqual(image.size, (885, 839))
        self.assertEqual(source["capture_box"], WINDOW["rect"])
        self.assertEqual(source["image_space"], "window_outer")
        self.assertEqual(calls[1]["bbox"], (47, 64, 932, 903))
        self.assertTrue(source["quiet_capture"]["visible_screen_fallback"])

    def test_missing_client_origin_never_uses_outer_origin_for_direct_image(self):
        _, source, _ = self.capture(window={"hwnd": 123, "rect": WINDOW["rect"]})
        self.assertIsNone(source["capture_box"])
        self.assertEqual(source["coordinate_space"], "window_client_local")
        self.assertFalse(guardian.window_coordinate_mapping(source, (869, 780))["available"])

    def test_scaled_capture_mapping_is_returned_and_saved_in_sidecar(self):
        image, source, _ = self.capture()
        with tempfile.TemporaryDirectory() as output:
            result = guardian.save_capture_image(image, source, self.libs, {"output_dir": output, "max_width": 434})
            metadata = json.loads(Path(result["metadata_path"]).read_text(encoding="utf-8"))
            self.assertEqual(metadata["coordinate_mapping"], result["coordinate_mapping"])
            mapping = result["coordinate_mapping"]
            self.assertEqual(mapping["origin"], {"x": 55, "y": 115})
            size = result["saved_size"]
            units = mapping["desktop_units_per_saved_pixel"]
            self.assertAlmostEqual(55 + size["width"] * units["x"], 924)
            self.assertAlmostEqual(115 + size["height"] * units["y"], 895)
            self.assertEqual(result["original_size"], {"width": 869, "height": 780})


if __name__ == "__main__":
    unittest.main()
