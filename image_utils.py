import cv2
import fitz
import numpy as np


def load_image_bytes_to_bgr(file_bytes: bytes) -> np.ndarray:
    array = np.frombuffer(file_bytes, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Unable to decode image file")
    return image


def load_images_from_pdf_bytes(file_bytes: bytes) -> list[np.ndarray]:
    document = fitz.open(stream=file_bytes, filetype="pdf")
    images = []
    for page in document:
        pix = page.get_pixmap(alpha=False)
        image = np.frombuffer(pix.samples, dtype=np.uint8)
        image = image.reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
        else:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        images.append(image)
    if not images:
        raise ValueError("PDF did not contain any renderable pages")
    return images


def load_images_from_upload(file_bytes: bytes, filename: str) -> list[np.ndarray]:
    if filename.lower().endswith(".pdf"):
        return load_images_from_pdf_bytes(file_bytes)
    return [load_image_bytes_to_bgr(file_bytes)]


def to_grayscale(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def estimate_blur(gray: np.ndarray) -> float:
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return float(variance)


def estimate_skew(gray: np.ndarray) -> float:
    inverted = cv2.bitwise_not(gray)
    thresh = cv2.threshold(inverted, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if coords.shape[0] < 50:
        return 0.0
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    return abs(float(angle))


def estimate_contrast(gray: np.ndarray) -> float:
    return float(gray.max() - gray.min())


def measure_resolution(image: np.ndarray) -> int:
    return int(image.shape[0] * image.shape[1])


def detect_crop_cutoff(gray: np.ndarray) -> bool:
    h, w = gray.shape
    border = int(min(h, w) * 0.04)
    if border < 4:
        return False
    edges = [gray[:border, :], gray[-border:, :], gray[:, :border], gray[:, -border:]]
    dark_ratios = [float(np.mean(region < 240)) for region in edges]
    return any(ratio > 0.02 for ratio in dark_ratios)


def is_blank_page(gray: np.ndarray, extracted_text: str) -> bool:
    if len(extracted_text.strip()) > 10:
        return False
    white_ratio = float(np.mean(gray > 245))
    return white_ratio > 0.90
