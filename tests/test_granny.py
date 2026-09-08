import contextlib
import io
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import main as bot


class GrannyPurchaseTests(unittest.TestCase):
    def frame(self, filename):
        frame = Image.new("RGB", (200, 140), (20, 20, 20))
        if filename:
            with Image.open(Path(bot.__file__).parent / "img" / filename) as icon:
                frame.paste(icon.convert("RGB"), (30, 25))
        return frame

    def run_frames(self, filenames, stop_on_move=False):
        frames = [self.frame(filename) for filename in filenames]
        event = threading.Event()
        completed = 0

        def finish_frame(_timeout):
            nonlocal completed
            completed += 1
            if completed == len(frames):
                event.set()

        def move_mouse(*_args):
            self.assertTrue(bot.mouse_lock.locked())
            if stop_on_move:
                event.set()

        output = io.StringIO()
        with (
            patch.object(bot, "stop_event", event),
            patch.object(bot, "stopRequested", side_effect=event.is_set),
            patch.object(event, "wait", side_effect=finish_frame),
            patch.object(bot.pgui, "screenshot", side_effect=frames),
            patch.object(bot.pgui, "moveTo", side_effect=move_mouse) as move,
            patch.object(bot.pgui, "click", side_effect=lambda: self.assertTrue(bot.mouse_lock.locked())) as click,
            contextlib.redirect_stdout(output),
        ):
            bot.clickOnGranny((100, 50, 200, 140))
        return click, move, output.getvalue()

    def test_bright_reference_is_clicked_at_screen_coordinates(self):
        click, move, output = self.run_frames(["granny.png"])
        click.assert_called_once_with()
        move.assert_called_once_with(163, 106)
        self.assertIn("brightness 100%", output)

    def test_dim_reference_is_located_but_never_clicked(self):
        click, move, output = self.run_frames(["bGrann.png"])
        click.assert_not_called()
        move.assert_not_called()
        self.assertIn("Granny is dim", output)

    def test_purchase_rechecks_brightness_before_clicking_again(self):
        click, _, output = self.run_frames(["granny.png", "bGrann.png"])
        click.assert_called_once_with()
        self.assertIn("Granny is dim", output)

    def test_waits_until_granny_becomes_bright(self):
        click, _, _ = self.run_frames(["bGrann.png", "granny.png"])
        click.assert_called_once_with()

    def test_no_match_never_clicks(self):
        click, move, output = self.run_frames([None])
        click.assert_not_called()
        move.assert_not_called()
        self.assertIn("not visible", output)

    def test_q_during_movement_prevents_click(self):
        click, move, _ = self.run_frames(["granny.png"], stop_on_move=True)
        move.assert_called_once()
        click.assert_not_called()

    def test_q_stop_remains_set_for_other_worker_after_release(self):
        event = threading.Event()
        get_key_state = Mock(side_effect=[-32768, 0])
        windll = SimpleNamespace(user32=SimpleNamespace(GetAsyncKeyState=get_key_state))
        with patch.object(bot, "stop_event", event), patch.object(bot.ctypes, "windll", windll):
            self.assertTrue(bot.stopRequested())
            self.assertTrue(bot.stopRequested())


if __name__ == "__main__":
    unittest.main()
