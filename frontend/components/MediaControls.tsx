"use client";

import { useState, useEffect, useRef, useCallback } from "react";

const PLAYBACK_RATES = [0.5, 0.75, 1, 1.25, 1.5, 1.75, 2];

function formatTime(s: number): string {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}

export type MediaControlsProps = {
  /** The video or audio element. When null, controls are disabled. */
  element: HTMLVideoElement | HTMLAudioElement | null;
  /** Show fullscreen button (video only). */
  isVideo?: boolean;
  /** Optional class for the container. */
  className?: string;
};

export function MediaControls({ element, isVideo = false, className = "" }: MediaControlsProps) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [paused, setPaused] = useState(true);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isDragging, setIsDragging] = useState(false);
  const [showRateMenu, setShowRateMenu] = useState(false);
  const progressRef = useRef<HTMLDivElement>(null);

  const updateState = useCallback(() => {
    if (!element) return;
    setCurrentTime(element.currentTime);
    setDuration(element.duration);
    setPaused(element.paused);
    setVolume(element.volume);
    setMuted(element.muted);
    setPlaybackRate(element.playbackRate);
  }, [element]);

  useEffect(() => {
    if (!element) return;
    updateState();
    const events = ["timeupdate", "durationchange", "play", "pause", "volumechange", "ratechange"];
    events.forEach((ev) => element.addEventListener(ev, updateState));
    return () => events.forEach((ev) => element.removeEventListener(ev, updateState));
  }, [element, updateState]);

  const togglePlay = () => {
    if (!element) return;
    if (element.paused) element.play().catch(() => {});
    else element.pause();
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement> | React.PointerEvent) => {
    if (!element || !Number.isFinite(element.duration)) return;
    const rect = progressRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = "clientX" in e ? e.clientX : (e as React.MouseEvent).clientX;
    const p = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
    element.currentTime = p * element.duration;
    setCurrentTime(element.currentTime);
  };

  const handleProgressPointerDown = (e: React.PointerEvent) => {
    if (!element) return;
    setIsDragging(true);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    handleSeek(e);
  };

  const handleProgressPointerUp = (e: React.PointerEvent) => {
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    setIsDragging(false);
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!element) return;
    const v = parseFloat(e.target.value);
    element.volume = v;
    element.muted = v === 0;
    setVolume(v);
    setMuted(v === 0);
  };

  const toggleMute = () => {
    if (!element) return;
    element.muted = !element.muted;
    setMuted(element.muted);
  };

  const setRate = (rate: number) => {
    if (!element) return;
    element.playbackRate = rate;
    setPlaybackRate(rate);
    setShowRateMenu(false);
  };

  const toggleFullscreen = () => {
    if (!element || !isVideo) return;
    const container = element.parentElement;
    if (!container) return;
    if (!document.fullscreenElement) {
      container.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.();
    }
  };

  useEffect(() => {
    if (!element) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.repeat) return;
      switch (e.key) {
        case " ":
          e.preventDefault();
          if (element.paused) element.play().catch(() => {});
          else element.pause();
          break;
        case "ArrowLeft":
          e.preventDefault();
          element.currentTime = Math.max(0, element.currentTime - 10);
          updateState();
          break;
        case "ArrowRight":
          e.preventDefault();
          element.currentTime = Math.min(element.duration || 0, element.currentTime + 10);
          updateState();
          break;
        case "f":
        case "F":
          if (isVideo) {
            e.preventDefault();
            toggleFullscreen();
          }
          break;
        default:
          break;
      }
    };
    const container = element.closest("[data-media-container]");
    if (container) {
      const handler = (e: Event) => onKeyDown(e as KeyboardEvent);
      container.addEventListener("keydown", handler);
      return () => container.removeEventListener("keydown", handler);
    }
  }, [element, isVideo, updateState]);

  const displayTime = isDragging ? currentTime : (element?.currentTime ?? currentTime);
  const displayDuration = Number.isFinite(duration) ? duration : 0;

  if (!element) return null;

  return (
    <div className={`flex flex-wrap items-center gap-2 py-2 ${className}`} title="Keyboard: Space play/pause, ← → seek 10s, F fullscreen (video)">
      <button
        type="button"
        onClick={togglePlay}
        className="p-2 rounded hover:bg-slate-200 text-slate-700"
        aria-label={paused ? "Play" : "Pause"}
      >
        {paused ? (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M6.3 2.84A1.5 1.5 0 018 4v12a1.5 1.5 0 01-2.7.92L2.7 11.4A1.5 1.5 0 012 10V6a1.5 1.5 0 01.7-1.28l3.6-2.16zm7.4 0A1.5 1.5 0 0116 4v12a1.5 1.5 0 01-2.3 1.26l-3.6-2.16A1.5 1.5 0 019 14V6a1.5 1.5 0 01.7-1.28l3.6-2.16z" />
          </svg>
        ) : (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M6 4a2 2 0 00-2 2v8a2 2 0 002 2h8a2 2 0 002-2V6a2 2 0 00-2-2H6z" />
          </svg>
        )}
      </button>

      <span className="text-sm text-slate-600 tabular-nums">
        {formatTime(displayTime)} / {formatTime(displayDuration)}
      </span>

      <div
        ref={progressRef}
        className="relative flex-1 min-w-[80px] h-2 rounded-full bg-slate-300 cursor-pointer group flex items-center"
        onPointerDown={handleProgressPointerDown}
        onPointerMove={isDragging ? handleSeek : undefined}
        onPointerUp={handleProgressPointerUp}
        onPointerLeave={() => setIsDragging(false)}
        onClick={handleSeek}
      >
        <div
          className="h-full rounded-full bg-slate-600 transition-[width] duration-75 pointer-events-none"
          style={{ width: displayDuration ? `${(displayTime / displayDuration) * 100}%` : "0%" }}
        />
        <div
          className="absolute top-1/2 w-3 h-3 -translate-y-1/2 rounded-full bg-slate-800 opacity-0 group-hover:opacity-100 group-active:opacity-100 transition-opacity pointer-events-none"
          style={{
            left: displayDuration ? `calc(${(displayTime / displayDuration) * 100}% - 6px)` : "0",
          }}
        />
      </div>

      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={toggleMute}
          className="p-1.5 rounded hover:bg-slate-200 text-slate-700"
          aria-label={muted ? "Unmute" : "Mute"}
        >
          {muted || volume === 0 ? (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.076l-2.94-3.6A1 1 0 014 12H2a1 1 0 01-1-1V9a1 1 0 011-1h2a1 1 0 01.617.076l2.94 3.6zM14.657 2.929a1 1 0 011.414 0A9 9 0 0119 10a9 9 0 01-2.929 6.586 1 1 0 01-1.414-1.414A7 7 0 0017 10a7 7 0 00-1.929-4.657 1 1 0 010-1.414zm-2.829 2.828a1 1 0 011.415 0 5 5 0 010 7.07 1 1 0 11-1.415-1.415 3 3 0 000-4.242 1 1 0 010-1.415z" clipRule="evenodd" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.617.076l-2.94-3.6A1 1 0 014 12H2a1 1 0 01-1-1V9a1 1 0 011-1h2a1 1 0 01.617.076l2.94 3.6zM14.657 2.929a1 1 0 011.414 0A9 9 0 0119 10a9 9 0 01-2.929 6.586 1 1 0 01-1.414-1.414A7 7 0 0017 10a7 7 0 00-1.929-4.657 1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          )}
        </button>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={muted ? 0 : volume}
          onChange={handleVolumeChange}
          className="w-16 h-1.5 accent-slate-600"
          aria-label="Volume"
        />
      </div>

      <div className="relative">
        <button
          type="button"
          onClick={() => setShowRateMenu((v) => !v)}
          className="px-2 py-1 rounded hover:bg-slate-200 text-slate-700 text-sm font-medium"
          aria-label="Playback speed"
        >
          {playbackRate}x
        </button>
        {showRateMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowRateMenu(false)} aria-hidden />
            <div className="absolute bottom-full left-0 mb-1 py-1 bg-white border border-slate-200 rounded shadow-lg z-20 min-w-[4rem]">
              {PLAYBACK_RATES.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setRate(r)}
                  className={`block w-full text-left px-3 py-1.5 text-sm ${r === playbackRate ? "bg-slate-100 font-medium" : "hover:bg-slate-50"}`}
                >
                  {r}x
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {isVideo && (
        <button
          type="button"
          onClick={toggleFullscreen}
          className="p-2 rounded hover:bg-slate-200 text-slate-700"
          aria-label="Fullscreen"
        >
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M3 4a1 1 0 011-1h4a1 1 0 010 2H6.414l2.293 2.293a1 1 0 11-1.414 1.414L5 6.414V8a1 1 0 01-2 0V4zm9 1a1 1 0 010-2h4a1 1 0 011 1v4a1 1 0 01-2 0V6.414l-2.293 2.293a1 1 0 11-1.414-1.414L13.586 5H12zm-9 7a1 1 0 012 0v1.586l2.293-2.293a1 1 0 111.414 1.414L6.414 15H8a1 1 0 010 2H4a1 1 0 01-1-1v-4zm13-1a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 010-2h1.586l-2.293-2.293a1 1 0 111.414-1.414L15 13.586V12a1 1 0 011-1z" clipRule="evenodd" />
          </svg>
        </button>
      )}
    </div>
  );
}
