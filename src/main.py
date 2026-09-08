import ctypes
import threading
from pathlib import Path

import pyautogui as pgui
import pygetwindow as gw
from PIL import Image, ImageOps, ImageStat

COOKIE_CONFIDENCE = 0.8
GRANNY_CONFIDENCE = 0.9
GRANNY_MIN_BRIGHTNESS_RATIO = 0.9
GRANNY_CHECK_INTERVAL = 0.5
CLICK_INTERVAL = 0.0
mouse_lock = threading.Lock()
stop_event = threading.Event()


# Bot Functions

def stopRequested() -> bool:
    get_key_state = ctypes.windll.user32.GetAsyncKeyState
    get_key_state.argtypes = [ctypes.c_int]
    get_key_state.restype = ctypes.c_short
    if get_key_state(ord("Q")) & 0x8000:
        stop_event.set()
    return stop_event.is_set()


def clickOnCookie(windowRegion) -> None:
    cookie_image = Path(__file__).resolve().parent / "img" / "cookiedUnedited.png"
    try:
        cookieImageLocation = pgui.locateOnScreen(
            str(cookie_image), region=windowRegion, confidence=COOKIE_CONFIDENCE)
    except pgui.ImageNotFoundException as error:
        print(f"Cookie image was not found above confidence {COOKIE_CONFIDENCE:.2f}.")
        details = error.__cause__ or error.__context__ or error
        if str(details):
            print(details)
        return
    except NotImplementedError as error:
        print(error)
        print("Install confidence matching support: python -m pip install opencv-python")
        return
    print(f"Cookie found: {cookieImageLocation} (confidence threshold: {COOKIE_CONFIDENCE:.2f})")

    cookie_x, cookie_y = pgui.center(cookieImageLocation)
    print("Clicking the cookie. Press Q to stop.")
    while not stopRequested():
        with mouse_lock:
            if stopRequested():
                break
            pgui.moveTo(cookie_x, cookie_y)
            if stopRequested():
                break
            pgui.click()
        stop_event.wait(CLICK_INTERVAL)

    print("Cookie clicking stopped.")


def clickOnGranny(windowRegion) -> None:
    granny_image = Path(__file__).resolve().parent / "img" / "granny.png"
    with Image.open(granny_image) as image:
        # Exclude the outer border: the two reference screenshots are cropped differently.
        margin_x, margin_y = image.width // 10, image.height // 10
        template = image.convert("RGB").crop(
            (margin_x, margin_y, image.width - margin_x, image.height - margin_y)
        )
    gray_template = ImageOps.grayscale(template)
    # Sample highlights on the face/hair, rather than the dark background.
    highlight_mask = gray_template.point(lambda value: 255 if value >= 160 else 0)
    reference_brightness = ImageStat.Stat(gray_template, highlight_mask).mean[0]
    previous_state = None

    while not stopRequested():
        # Keep observation and clicking together so the cookie thread cannot move the mouse.
        with mouse_lock:
            if stopRequested():
                break
            screenshot = pgui.screenshot(region=windowRegion)
            if screenshot.width < template.width or screenshot.height < template.height:
                print("Game window is too small to search for granny. Restore it and restart.")
                return
            try:
                location = pgui.locate(template, screenshot, confidence=GRANNY_CONFIDENCE, grayscale=False)
            except pgui.ImageNotFoundException:
                location = None
            except NotImplementedError as error:
                print(error)
                print("Install confidence matching support: python -m pip install opencv-python")
                return

            if location is None:
                state = "missing"
                message = "Granny is not visible; waiting."
            else:
                left, top, width, height = location
                patch = screenshot.crop((left, top, left + width, top + height))
                brightness = ImageStat.Stat(ImageOps.grayscale(patch), highlight_mask).mean[0]
                ratio = brightness / reference_brightness
                if ratio >= GRANNY_MIN_BRIGHTNESS_RATIO:
                    if stopRequested():
                        break
                    pgui.moveTo(
                        windowRegion[0] + left + width // 2,
                        windowRegion[1] + top + height // 2,
                    )
                    if stopRequested():
                        break
                    pgui.click()
                    state = "bright"
                    message = f"Clicked bright granny (brightness {ratio:.0%} of reference)."
                else:
                    state = "dim"
                    message = f"Granny is dim ({ratio:.0%} of reference); waiting to buy."

            if state != previous_state or state == "bright":
                print(message)
            previous_state = state
        # Take a fresh screenshot before every purchase: buying can dim the icon again.
        stop_event.wait(GRANNY_CHECK_INTERVAL)

    print("Granny clicking stopped.")


def main() -> None:
    windows = gw.getWindowsWithTitle("Cookie Clicker")
    if not windows:
        print("Cookie Clicker Window is not open!")
        return

    window = windows[0]
    cookieClickerGame_region = (window.left, window.top, window.width, window.height)
    print(f"Window size is Width {window.width} Height is {window.height}")
    print(f"Position {window.left}, {window.top}")

    stop_event.clear()
    cookieThread = threading.Thread(target=clickOnCookie, args=(cookieClickerGame_region,))
    grannyThread = threading.Thread(target=clickOnGranny, args=(cookieClickerGame_region,))
    cookieThread.start()
    grannyThread.start()
    cookieThread.join()
    grannyThread.join()
    print("All Threads Tasks Done")


if __name__ == "__main__":
    main()
