"use client";

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

const HEADER_H = 48;
const ZOOM_FACTOR = 1.08;
const MAX_SCALE = 4;
const MIN_SCALE_FACTOR = 0.75;
const DENSE_BOOST = 1.15;
const TALL_ASPECT_RATIO = 2.2;
const TALL_BOOST = 1.1;
const LARGE_IMAGE_RATIO = 1.2;

export type LightboxImage = { src: string; label?: string };

type Props = {
  open: boolean;
  onClose: () => void;
  src?: string;
  images?: LightboxImage[];
  initialIndex?: number;
  alt?: string;
};

function getBaseScale(
  viewportW: number,
  viewportH: number,
  imgW: number,
  imgH: number
): { baseScale: number; fitScale: number } {
  if (!imgW || !imgH || viewportW <= 0 || viewportH <= 0) {
    return { baseScale: 1, fitScale: 1 };
  }
  const fitScale = Math.min(
    1,
    viewportW / imgW,
    viewportH / imgH
  );
  const aspect = imgH / imgW;
  let baseScale: number;
  if (aspect > TALL_ASPECT_RATIO) {
    const widthFit = Math.min(1, viewportW / imgW);
    baseScale = Math.min(widthFit * TALL_BOOST, 1);
  } else {
    const isLarge =
      imgW >= LARGE_IMAGE_RATIO * viewportW ||
      imgH >= LARGE_IMAGE_RATIO * viewportH;
    baseScale = isLarge
      ? Math.min(fitScale * DENSE_BOOST, 1)
      : fitScale;
  }
  return { baseScale: Math.max(0.15, baseScale), fitScale };
}

function clampTranslate(
  translateX: number,
  translateY: number,
  scale: number,
  imgW: number,
  imgH: number,
  viewportW: number,
  viewportH: number
): { x: number; y: number } {
  const scaledW = imgW * scale;
  const scaledH = imgH * scale;
  let x = translateX;
  let y = translateY;
  if (scaledW <= viewportW) {
    x = (viewportW - scaledW) / 2;
  } else {
    const minX = viewportW - scaledW;
    const maxX = 0;
    x = Math.max(minX, Math.min(maxX, x));
  }
  if (scaledH <= viewportH) {
    y = (viewportH - scaledH) / 2;
  } else {
    const minY = viewportH - scaledH;
    const maxY = 0;
    y = Math.max(minY, Math.min(maxY, y));
  }
  return { x, y };
}

export function ImageLightbox({
  open,
  onClose,
  src,
  images,
  initialIndex = 0,
  alt = "Image",
}: Props) {
  const list = images?.length
    ? images
    : src
      ? [{ src, label: undefined }]
      : [];
  const [activeIndex, setActiveIndex] = useState(
    Math.min(initialIndex, Math.max(0, list.length - 1))
  );
  const current = list[activeIndex];
  const currentSrc = current?.src;

  const [naturalWidth, setNaturalWidth] = useState(0);
  const [naturalHeight, setNaturalHeight] = useState(0);
  const [scale, setScale] = useState(1);
  const [translateX, setTranslateX] = useState(0);
  const [translateY, setTranslateY] = useState(0);
  const [baseScale, setBaseScale] = useState(1);
  const [minScale, setMinScale] = useState(0.5);
  const [maxScale, setMaxScale] = useState(MAX_SCALE);
  const [viewportSize, setViewportSize] = useState({ w: 0, h: 0 });
  const [imageLoaded, setImageLoaded] = useState(false);

  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const pinchStartRef = useRef<{ distance: number; scale: number; midX: number; midY: number } | null>(null);
  const pointersRef = useRef<Map<number, { x: number; y: number }>>(new Map());
  const lastScaleRef = useRef(scale);
  const lastTxRef = useRef(translateX);
  const lastTyRef = useRef(translateY);

  const viewportW = viewportSize.w;
  const viewportH = viewportSize.h;

  const updateTransform = useCallback(
    (s: number, tx: number, ty: number) => {
      if (!naturalWidth || !naturalHeight) return;
      const minS = Math.min(baseScale * MIN_SCALE_FACTOR, baseScale);
      const clampedScale = Math.max(minS, Math.min(MAX_SCALE, s));
      const { x, y } = clampTranslate(
        tx,
        ty,
        clampedScale,
        naturalWidth,
        naturalHeight,
        viewportW,
        viewportH
      );
      lastScaleRef.current = clampedScale;
      lastTxRef.current = x;
      lastTyRef.current = y;
      setScale(clampedScale);
      setTranslateX(x);
      setTranslateY(y);
    },
    [baseScale, naturalWidth, naturalHeight, viewportW, viewportH]
  );

  const resetToFit = useCallback(() => {
    setScale(baseScale);
    const tx = (viewportW - naturalWidth * baseScale) / 2;
    const ty = (viewportH - naturalHeight * baseScale) / 2;
    setTranslateX(tx);
    setTranslateY(ty);
    lastScaleRef.current = baseScale;
    lastTxRef.current = tx;
    lastTyRef.current = ty;
  }, [baseScale, viewportW, viewportH, naturalWidth, naturalHeight]);

  const resetTo100 = useCallback(() => {
    setScale(1);
    const tx = (viewportW - naturalWidth) / 2;
    const ty = (viewportH - naturalHeight) / 2;
    setTranslateX(tx);
    setTranslateY(ty);
    lastScaleRef.current = 1;
    lastTxRef.current = tx;
    lastTyRef.current = ty;
  }, [viewportW, viewportH, naturalWidth, naturalHeight]);

  // Use window size for viewport so image is always centered on the user's screen
  useEffect(() => {
    if (!open) return;
    const updateViewport = () => {
      setViewportSize({
        w: window.innerWidth,
        h: Math.max(0, window.innerHeight - HEADER_H),
      });
    };
    updateViewport();
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, [open]);

  // Compute initial scale and center image when image loads or viewport changes
  useLayoutEffect(() => {
    if (!open || !naturalWidth || !naturalHeight) return;
    const vw = viewportW > 0 ? viewportW : window.innerWidth;
    const vh = viewportH > 0 ? viewportH : Math.max(0, window.innerHeight - HEADER_H);
    if (vw <= 0 || vh <= 0) return;
    const { baseScale: bs } = getBaseScale(vw, vh, naturalWidth, naturalHeight);
    setBaseScale(bs);
    const minS = Math.min(bs * MIN_SCALE_FACTOR, bs);
    setMinScale(minS);
    setMaxScale(MAX_SCALE);
    const tx = (vw - naturalWidth * bs) / 2;
    const ty = (vh - naturalHeight * bs) / 2;
    setScale(bs);
    setTranslateX(tx);
    setTranslateY(ty);
    lastScaleRef.current = bs;
    lastTxRef.current = tx;
    lastTyRef.current = ty;
  }, [open, naturalWidth, naturalHeight, viewportW, viewportH]);

  // Sync index when initialIndex or list changes
  useEffect(() => {
    if (!open) return;
    const idx = Math.min(initialIndex, Math.max(0, list.length - 1));
    setActiveIndex(idx);
  }, [open, initialIndex, list.length]);

  // Reset image state when switching image in gallery
  useEffect(() => {
    if (!open || !currentSrc) return;
    setImageLoaded(false);
    setNaturalWidth(0);
    setNaturalHeight(0);
  }, [open, currentSrc]);

  // Lock body scroll when open
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  // Focus close button when opened
  useEffect(() => {
    if (open) {
      const t = requestAnimationFrame(() => closeRef.current?.focus());
      return () => cancelAnimationFrame(t);
    }
  }, [open]);

  // Keyboard
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === "0") {
        e.preventDefault();
        resetToFit();
        return;
      }
      if (e.key === "1") {
        e.preventDefault();
        resetTo100();
        return;
      }
      if (e.key === "=" || e.key === "+") {
        e.preventDefault();
        const s = Math.min(MAX_SCALE, lastScaleRef.current * ZOOM_FACTOR);
        updateTransform(s, lastTxRef.current, lastTyRef.current);
        return;
      }
      if (e.key === "-") {
        e.preventDefault();
        const s = Math.max(minScale, lastScaleRef.current / ZOOM_FACTOR);
        updateTransform(s, lastTxRef.current, lastTyRef.current);
        return;
      }
      if (list.length > 1) {
        if (e.key === "ArrowLeft") {
          e.preventDefault();
          setActiveIndex((i) => (i <= 0 ? list.length - 1 : i - 1));
          return;
        }
        if (e.key === "ArrowRight") {
          e.preventDefault();
          setActiveIndex((i) => (i >= list.length - 1 ? 0 : i + 1));
          return;
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose, resetToFit, resetTo100, minScale, updateTransform, list.length]);

  const handleImageLoad = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    const img = e.currentTarget;
    setNaturalWidth(img.naturalWidth);
    setNaturalHeight(img.naturalHeight);
    setImageLoaded(true);
  }, []);

  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const cursorX = e.clientX - rect.left;
      const cursorY = e.clientY - rect.top;
      const imgX = (cursorX - lastTxRef.current) / lastScaleRef.current;
      const imgY = (cursorY - lastTyRef.current) / lastScaleRef.current;
      const factor = e.deltaY > 0 ? 1 / ZOOM_FACTOR : ZOOM_FACTOR;
      const newScale = Math.max(minScale, Math.min(MAX_SCALE, lastScaleRef.current * factor));
      const newTx = cursorX - imgX * newScale;
      const newTy = cursorY - imgY * newScale;
      updateTransform(newScale, newTx, newTy);
    },
    [naturalWidth, naturalHeight, minScale, updateTransform]
  );

  const getPoint = (e: React.PointerEvent) => ({ x: e.clientX, y: e.clientY });
  const getMid = (a: { x: number; y: number }, b: { x: number; y: number }) => ({
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
  });
  const dist = (a: { x: number; y: number }, b: { x: number; y: number }) =>
    Math.hypot(b.x - a.x, b.y - a.y);

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      (e.currentTarget as HTMLElement).setPointerCapture?.(e.pointerId);
      const id = e.pointerId;
      const pt = getPoint(e);
      pointersRef.current.set(id, pt);
      if (pointersRef.current.size === 2) {
        const [p1, p2] = Array.from(pointersRef.current.values());
        pinchStartRef.current = {
          distance: dist(p1, p2),
          scale: lastScaleRef.current,
          ...getMid(p1, p2),
        };
      } else if (pointersRef.current.size === 1 && lastScaleRef.current > baseScale + 0.01) {
        setIsDragging(true);
        dragStartRef.current = { x: pt.x, y: pt.y, tx: lastTxRef.current, ty: lastTyRef.current };
      }
    },
    [baseScale]
  );

  const onPointerMove = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const id = e.pointerId;
      const pt = getPoint(e);
      pointersRef.current.set(id, pt);

      if (pinchStartRef.current && pointersRef.current.size === 2) {
        const [p1, p2] = Array.from(pointersRef.current.values());
        const d = dist(p1, p2);
        const start = pinchStartRef.current;
        const ratio = d / start.distance;
        const newScale = Math.max(minScale, Math.min(MAX_SCALE, start.scale * ratio));
        const mid = getMid(p1, p2);
        if (!containerRef.current) return;
        const rect = containerRef.current.getBoundingClientRect();
        const midYInContainer = mid.y - rect.top;
        const startMidYInContainer = start.midY - rect.top;
        const dx = mid.x - start.midX;
        const dy = midYInContainer - startMidYInContainer;
        const newTx = lastTxRef.current + dx;
        const newTy = lastTyRef.current + dy;
        updateTransform(newScale, newTx, newTy);
        pinchStartRef.current = { ...start, distance: d, midX: mid.x, midY: mid.y };
        return;
      }

      if (isDragging && pointersRef.current.size === 1) {
        const start = dragStartRef.current;
        const newTx = start.tx + (pt.x - start.x);
        const newTy = start.ty + (pt.y - start.y);
        updateTransform(lastScaleRef.current, newTx, newTy);
      }
    },
    [minScale, updateTransform, isDragging]
  );

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size !== 2) pinchStartRef.current = null;
    if (pointersRef.current.size === 0) setIsDragging(false);
  }, []);

  const onPointerLeave = useCallback((e: React.PointerEvent) => {
    pointersRef.current.delete(e.pointerId);
    if (pointersRef.current.size !== 2) pinchStartRef.current = null;
    if (pointersRef.current.size === 0) setIsDragging(false);
  }, []);

  const handleDoubleClick = useCallback(() => {
    const s = lastScaleRef.current;
    const nearFit = Math.abs(s - baseScale) < 0.05;
    const near100 = Math.abs(s - 1) < 0.05;
    if (nearFit || s < 1) {
      resetTo100();
    } else {
      resetToFit();
    }
  }, [baseScale, resetToFit, resetTo100]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose]
  );

  const goPrev = useCallback(() => {
    setActiveIndex((i) => (i <= 0 ? list.length - 1 : i - 1));
  }, [list.length]);

  const goNext = useCallback(() => {
    setActiveIndex((i) => (i >= list.length - 1 ? 0 : i + 1));
  }, [list.length]);

  const zoomPercent = Math.round(scale * 100);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-black/85 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label="Image lightbox"
    >
      {/* Header */}
      <div
        className="flex items-center justify-between shrink-0 h-12 px-4 border-b border-zinc-700 bg-zinc-900/80"
        style={{ height: HEADER_H }}
      >
        <div className="flex items-center gap-3 min-w-0">
          {current?.label && (
            <span className="text-sm text-zinc-300 truncate">{current.label}</span>
          )}
          {list.length > 1 && (
            <span className="text-xs text-zinc-500 tabular-nums">
              {activeIndex + 1} / {list.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 w-10 text-right">{zoomPercent}%</span>
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-200 px-2 py-1 text-sm"
            onClick={resetToFit}
            aria-label="Fit to view"
          >
            Fit
          </button>
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-200 px-2 py-1 text-sm"
            onClick={resetTo100}
            aria-label="100% zoom"
          >
            100%
          </button>
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-200 w-8 h-8 flex items-center justify-center text-lg"
            onClick={() =>
              updateTransform(
                Math.max(minScale, lastScaleRef.current / ZOOM_FACTOR),
                lastTxRef.current,
                lastTyRef.current
              )
            }
            aria-label="Zoom out"
          >
            −
          </button>
          <button
            type="button"
            className="text-zinc-400 hover:text-zinc-200 w-8 h-8 flex items-center justify-center text-lg"
            onClick={() =>
              updateTransform(
                Math.min(MAX_SCALE, lastScaleRef.current * ZOOM_FACTOR),
                lastTxRef.current,
                lastTyRef.current
              )
            }
            aria-label="Zoom in"
          >
            +
          </button>
          <button
            ref={closeRef}
            type="button"
            className="ml-2 text-zinc-400 hover:text-zinc-200 px-3 py-1.5 rounded border border-zinc-600 text-sm"
            onClick={onClose}
            aria-label="Close lightbox"
          >
            Close
          </button>
        </div>
      </div>

      {/* Main area: container + image */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 flex items-center justify-center overflow-hidden relative"
        onWheel={handleWheel}
        style={{ touchAction: "none" }}
      >
        {list.length > 1 && activeIndex > 0 && (
          <button
            type="button"
            className="absolute left-2 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-zinc-800/90 border border-zinc-600 text-zinc-200 flex items-center justify-center hover:bg-zinc-700"
            onClick={goPrev}
            aria-label="Previous image"
          >
            ‹
          </button>
        )}
        {list.length > 1 && activeIndex < list.length - 1 && (
          <button
            type="button"
            className="absolute right-2 top-1/2 -translate-y-1/2 z-10 w-10 h-10 rounded-full bg-zinc-800/90 border border-zinc-600 text-zinc-200 flex items-center justify-center hover:bg-zinc-700"
            onClick={goNext}
            aria-label="Next image"
          >
            ›
          </button>
        )}

        <div
          className="absolute inset-0"
          onClick={handleBackdropClick}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerLeave}
          onPointerCancel={onPointerUp}
          style={{
            cursor: scale > baseScale + 0.01 ? (isDragging ? "grabbing" : "grab") : "default",
            userSelect: "none",
          }}
        >
          {!currentSrc ? (
            <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-zinc-500">
              {list.length > 1 ? "Loading…" : "No image"}
            </span>
          ) : (
            <>
              {!imageLoaded && (
                <span className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-zinc-500">
                  Loading…
                </span>
              )}
              <img
                ref={imageRef}
                src={currentSrc}
                alt={current?.label ?? alt}
                draggable={false}
                className="select-none max-w-none absolute left-0 top-0"
                style={{
                  width: naturalWidth || undefined,
                  height: naturalHeight || undefined,
                  transform: `translate3d(${translateX}px, ${translateY}px, 0) scale(${scale})`,
                  transformOrigin: "0 0",
                  opacity: imageLoaded ? 1 : 0,
                  pointerEvents: imageLoaded ? "auto" : "none",
                }}
                onLoad={handleImageLoad}
                onDoubleClick={(e) => {
                  e.stopPropagation();
                  handleDoubleClick();
                }}
                onClick={(e) => e.stopPropagation()}
              />
            </>
          )}
        </div>

      </div>
    </div>
  );
}
