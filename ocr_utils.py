# ocr_utils.py — OCR robusto com autopilot (PSM auto) e pré-processamento leve
"""
OCR helpers para text-seeker.

Principais funções:
- resolve_tesseract_cmd(explicit: Optional[str] = None, set_global: bool = True) -> Optional[str]
- extract_text_from_image(image_input, *, lang="eng+por", tesseract_cmd=None,
                          grayscale=True, enhance_contrast=2.0, threshold=None,
                          tess_config=None, autopilot=True, oem=3,
                          psms=(6,4,3), preserve_spaces=True,
                          return_conf=False, preprocess_mode="text") -> str | (str, float)

Notas:
- Mantém compatibilidade com a sua assinatura anterior; novos argumentos são opcionais.
- Autopilot testa vários PSMs e escolhe o melhor pela confiança média do Tesseract.
"""

from __future__ import annotations
from typing import Optional, Union, BinaryIO, Sequence, Tuple
import os, platform, shutil, io, re, unicodedata

from process_utils import configure_hidden_subprocess_windows, limit_external_processes

configure_hidden_subprocess_windows()

__all__ = ["extract_text_from_image", "resolve_tesseract_cmd"]

# --------------------- resolução do executável (com cache) ---------------------
_CACHED_CMD: Optional[str] = None

def resolve_tesseract_cmd(explicit: Optional[str] = None, set_global: bool = True) -> Optional[str]:
    """
    Ordem de resolução:
      1) argumento `explicit`
      2) env TESSERACT_PATH
      3) caminhos Windows comuns
      4) `tesseract` no PATH (shutil.which)
    Se set_global=True, define pytesseract.pytesseract.tesseract_cmd.
    """
    global _CACHED_CMD
    if _CACHED_CMD and os.path.isfile(_CACHED_CMD):
        return _CACHED_CMD

    cand: Optional[str] = None
    if explicit and os.path.isfile(explicit):
        cand = explicit
    elif os.environ.get("TESSERACT_PATH") and os.path.isfile(os.environ["TESSERACT_PATH"]):
        cand = os.environ["TESSERACT_PATH"]
    elif platform.system() == "Windows":
        for p in (r"D:\Tesseract\tesseract.exe",
                  r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                  r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
            if os.path.isfile(p):
                cand = p; break
    if not cand:
        cand = shutil.which("tesseract")

    if cand:
        _CACHED_CMD = cand
        if set_global:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = cand
            except Exception:
                pass
    return cand

# --------------------- helpers de imagem --------------------------------------
def _to_pil_image(image_input: Union[str, "Image.Image", bytes, BinaryIO, "np.ndarray"]):
    """Converte path/bytes/file-like/PIL/ndarray em PIL.Image.Image."""
    try:
        from PIL import Image
    except Exception as e:
        raise ImportError("Pillow é necessário para OCR.") from e

    if isinstance(image_input, str):
        return Image.open(image_input)

    if isinstance(image_input, (bytes, bytearray)):
        return Image.open(io.BytesIO(image_input))

    if hasattr(image_input, "read"):
        return Image.open(image_input)

    if hasattr(image_input, "mode") and hasattr(image_input, "size"):
        return image_input  # presumivelmente PIL.Image.Image

    try:
        import numpy as np
        if isinstance(image_input, np.ndarray):
            if image_input.ndim == 2:
                return Image.fromarray(image_input)
            if image_input.ndim == 3:
                if image_input.shape[2] == 3:   # BGR -> RGB (cv2)
                    return Image.fromarray(image_input[:, :, ::-1])
                if image_input.shape[2] == 4:   # BGRA -> RGBA
                    return Image.fromarray(image_input[:, :, [2,1,0,3]])
    except Exception:
        pass

    raise TypeError("Tipo de input não suportado para imagem.")

def _preprocess_pil(img: "Image.Image", grayscale: bool, enhance_contrast: Optional[float],
                    threshold: Optional[int], mode: str = "text") -> "Image.Image":
    """Pré-processamento leve, sem dependência de OpenCV."""
    from PIL import ImageOps, ImageEnhance, ImageFilter
    im = img
    if grayscale and im.mode != "L":
        im = im.convert("L")
    if enhance_contrast and float(enhance_contrast) > 1.0:
        im = ImageEnhance.Contrast(im).enhance(float(enhance_contrast))
    # ruído leve
    im = im.filter(ImageFilter.MedianFilter(size=3))
    # binarização simples
    if isinstance(threshold, int):
        th = max(0, min(255, threshold))
        im = im.point(lambda p: 255 if p >= th else 0)
    # (opcional) limpeza de artefactos pós-OCR pode ser feita no texto
    return im

# --------------------- OCR/autopilot ------------------------------------------
def _ocr_text(im: "Image.Image", *, lang: str, config: str) -> Tuple[str, float]:
    """
    Executa OCR e devolve (texto, confiança_media). Usa image_to_data para medir confiança.
    """
    import pytesseract
    try:
        data = pytesseract.image_to_data(im, lang=lang, config=config, output_type=pytesseract.Output.DICT)
        confs = [c for c in data.get("conf", []) if isinstance(c, int) and c >= 0]
        mean_conf = (sum(confs)/len(confs)) if confs else 0.0
        # junta tokens não vazios; preserva espaços entre palavras
        tokens = [t for t in data.get("text", []) if isinstance(t, str) and t.strip()]
        text = " ".join(tokens)
        return text, float(mean_conf)
    except Exception:
        # fallback simples
        txt = pytesseract.image_to_string(im, lang=lang, config=config) or ""
        return txt, 0.0

def _clean_ocr_text(s: str) -> str:
    """Limpeza leve de artefactos comuns (sublinhados, barras soltas, múltiplos espaços)."""
    if not s:
        return ""
    t = unicodedata.normalize("NFKC", s)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"(?<=\w)[\\/_](?=\s|$)", "", t)  # remove "\" "/" "_" soltos no fim de palavra
    return t.strip()

# --------------------- API pública --------------------------------------------
def extract_text_from_image(
    image_input,
    lang: str = "por+eng",
    tess_config: str = "--oem 3 --psm 6",
    try_psm: bool = True,
) -> str:
    """
    Extrai texto de caminho ou PIL.Image usando Tesseract.
    - Pré-processa (grayscale, autocontrast, median).
    - Se try_psm=True, testa vários PSM e escolhe o de melhor confiança média.
    Devolve apenas o texto (str).
    """
    try:
        import pytesseract
        from PIL import Image, ImageOps, ImageFilter, ImageFile
    except Exception:
        print("❌ OCR missing dependencies (pytesseract, Pillow).")
        return ""

    # Evita erros com imagens truncadas
    try:
        ImageFile.LOAD_TRUNCATED_IMAGES = True
    except Exception:
        pass

    # Resolver tesseract.exe se possível
    try:
        cmd = resolve_tesseract_cmd()
        if cmd:
            pytesseract.pytesseract.tesseract_cmd = cmd
    except Exception:
        pass

    # Carregar imagem
    try:
        if isinstance(image_input, str):
            img = Image.open(image_input)
        else:
            # Assume objeto PIL.Image; se for NumPy, tente converter
            try:
                from PIL import Image as _PIL_Image
                import numpy as _np  # opcional
                if hasattr(image_input, "shape"):  # provável NumPy
                    img = _PIL_Image.fromarray(image_input)
                else:
                    img = image_input  # PIL.Image
            except Exception:
                img = image_input
    except Exception as e:
        print(f"OCR load error: {e}")
        return ""

    # Pré-processamento leve (funciona bem na maioria dos casos)
    try:
        img = ImageOps.grayscale(img)
        img = ImageOps.autocontrast(img)
        img = img.filter(ImageFilter.MedianFilter(size=3))
        # Binarização opcional (comente/descomente consoante o caso):
        # img = img.point(lambda p: 255 if p > 180 else 0, mode='1')
    except Exception:
        pass

    def _ocr_with_conf(_img, _cfg):
        try:
            data = pytesseract.image_to_data(
                _img, lang=lang, config=_cfg, output_type=pytesseract.Output.DICT
            )
            confs = [
                float(c) for c in data.get("conf", [])
                if isinstance(c, (int, float, str)) and str(c).strip() not in {"", "-1"}
            ]
            mean_conf = (sum(confs) / len(confs)) if confs else 0.0
            text = " ".join(data.get("text", [])).strip()
            return text, float(mean_conf)
        except Exception:
            return "", 0.0

    with limit_external_processes():
        if not try_psm:
            txt, _ = _ocr_with_conf(img, tess_config)
            return txt

        # Ronda multi-PSM (tenta alguns perfis correntes)
        psm_list = [6, 4, 3, 11]
        best_txt, best_conf = "", -1.0
        base = "--oem 3"
        for psm in psm_list:
            # junta tess_config sem duplicar --psm
            extra = " ".join(x for x in (tess_config or "").split() if not x.startswith("--psm"))
            cfg = f"{base} --psm {psm}" + (f" {extra}" if extra else "")
            txt, conf = _ocr_with_conf(img, cfg)
            if conf > best_conf:
                best_conf, best_txt = conf, txt

        return best_txt

