import requests
from PIL import Image, ImageEnhance
from io import BytesIO
import os
import logging
import hashlib
import tempfile
import subprocess

logger = logging.getLogger(__name__)
protected_colors = {
    (0, 0, 0),          # Black
    (255, 255, 255),    # White
    (255, 255, 0),      # Yellow
    (255, 0, 0),        # Red
    (0, 0, 255),        # Blue
    (0, 255, 0)         # Green
}
def get_image(image_url):
    response = requests.get(image_url)
    img = None
    if 200 <= response.status_code < 300 or response.status_code == 304:
        img = Image.open(BytesIO(response.content))
    else:
        logger.error(f"Received non-200 response from {image_url}: status_code: {response.status_code}")
    return img

def change_orientation(image, orientation, inverted=False):
    if orientation == 'horizontal':
        angle = 0
    elif orientation == 'vertical':
        angle = 90

    if inverted:
        angle = (angle + 180) % 360

    return image.rotate(angle, expand=1)

def resize_image(image, desired_size, image_settings=[]):
    img_width, img_height = image.size
    desired_width, desired_height = desired_size
    desired_width, desired_height = int(desired_width), int(desired_height)

    img_ratio = img_width / img_height
    desired_ratio = desired_width / desired_height

    keep_width = "keep-width" in image_settings

    x_offset, y_offset = 0,0
    new_width, new_height = img_width,img_height
    # Step 1: Determine crop dimensions
    desired_ratio = desired_width / desired_height
    if img_ratio > desired_ratio:
        # Image is wider than desired aspect ratio
        new_width = int(img_height * desired_ratio)
        if not keep_width:
            x_offset = (img_width - new_width) // 2
    else:
        # Image is taller than desired aspect ratio
        new_height = int(img_width / desired_ratio)
        if not keep_width:
            y_offset = (img_height - new_height) // 2

    # Step 2: Crop the image
    cropped_image = image.crop((x_offset, y_offset, x_offset + new_width, y_offset + new_height))

    # Step 3: Resize to the exact desired dimensions (if necessary)
    return cropped_image.resize((desired_width, desired_height), Image.LANCZOS)

def apply_image_enhancement(img, image_settings={}):
    # Ensure image is in RGB
    img = img.convert("RGB")
    original_pixels = img.copy().load()

    # Apply global enhancements
    img = ImageEnhance.Brightness(img).enhance(image_settings.get("brightness", 1.0))
    img = ImageEnhance.Contrast(img).enhance(image_settings.get("contrast", 1.0))
    img = ImageEnhance.Color(img).enhance(image_settings.get("saturation", 1.0))
    img = ImageEnhance.Sharpness(img).enhance(image_settings.get("sharpness", 1.0))

    # After all enhancements, restore protected pixels
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            if original_pixels[x, y] in protected_colors:
                pixels[x, y] = original_pixels[x, y]

    return img

def compute_image_hash(image):
    """Compute SHA-256 hash of an image."""
    image = image.convert("RGB")
    img_bytes = image.tobytes()
    return hashlib.sha256(img_bytes).hexdigest()

def take_screenshot_html(html_str, dimensions, timeout_ms=None):
    image = None
    try:
        # Create a temporary HTML file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as html_file:
            html_file.write(html_str.encode("utf-8"))
            html_file_path = html_file.name

        image = take_screenshot(html_file_path, dimensions, timeout_ms)

        # Remove html file
        os.remove(html_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image

def take_screenshot(target, dimensions, timeout_ms=None):
    image = None
    try:
        # Create a temporary output file for the screenshot
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as img_file:
            img_file_path = img_file.name

        command = [
            "chromium-headless-shell", target, "--headless",
            f"--screenshot={img_file_path}", f'--window-size={dimensions[0]},{dimensions[1]}',
            "--no-sandbox", "--disable-gpu", "--disable-software-rasterizer",
            "--disable-dev-shm-usage", "--hide-scrollbars"
        ]
        if timeout_ms:
            command.append(f"--timeout={timeout_ms}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # Check if the process failed or the output file is missing
        if result.returncode != 0 or not os.path.exists(img_file_path):
            logger.error("Failed to take screenshot:")
            logger.error(result.stderr.decode('utf-8'))
            return None

        # Load the image using PIL
        image = Image.open(img_file_path)

        # Remove image files
        os.remove(img_file_path)

    except Exception as e:
        logger.error(f"Failed to take screenshot: {str(e)}")

    return image
