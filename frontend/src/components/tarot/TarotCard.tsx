"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import type { CityData } from "./types";
import { countryFlagEmoji } from "@/lib/country-flag";

// ── Size variant config ───────────────────────────────────────────

export type CardSize = "sm" | "md" | "lg";

const SIZE_CONFIG = {
  sm:  { w: 140, h: 245, pad: 16, flag: 24, cityKr: 14, cityEn: 9,  compassD: 56, compassMiniD: 20, nnaiFs: 8  },
  md:  { w: 200, h: 350, pad: 20, flag: 28, cityKr: 18, cityEn: 11, compassD: 80, compassMiniD: 24, nnaiFs: 10 },
  lg:  { w: 260, h: 455, pad: 20, flag: 28, cityKr: 18, cityEn: 11, compassD: 80, compassMiniD: 24, nnaiFs: 10 },
} as const;

// ── Props ─────────────────────────────────────────────────────────

export interface TarotCardProps {
  state: "back" | "front" | "locked";
  size?: CardSize;
  cityData?: CityData | null;
  isSelected?: boolean;
  isFlipped?: boolean;
  onClick?: () => void;
}

// ── Compass Rose SVG ──────────────────────────────────────────────

function CompassRose({ diameter, active }: { diameter: number; active: boolean }) {
  const r = diameter / 2;
  const ir = r * 0.5;
  const dotR = r * 0.1;
  const color = active ? "var(--primary)" : "var(--border)";

  return (
    <svg width={diameter} height={diameter} viewBox={`0 0 ${diameter} ${diameter}`} fill="none" style={{ transition: "all 0.3s ease" }}>
      <circle cx={r} cy={r} r={r - 1} stroke={color} strokeWidth={1} />
      <line x1={0} y1={r} x2={diameter} y2={r} stroke={color} strokeWidth={0.8} />
      <line x1={r} y1={0} x2={r} y2={diameter} stroke={color} strokeWidth={0.8} />
      <line x1={r - r * 0.707} y1={r - r * 0.707} x2={r + r * 0.707} y2={r + r * 0.707} stroke={color} strokeWidth={0.5} />
      <line x1={r + r * 0.707} y1={r - r * 0.707} x2={r - r * 0.707} y2={r + r * 0.707} stroke={color} strokeWidth={0.5} />
      <circle cx={r} cy={r} r={ir} stroke={color} strokeWidth={0.8} />
      <circle cx={r} cy={r} r={dotR} fill={color} />
    </svg>
  );
}

function CityTitle({ title }: { title: string }) {
  const parenIndex = title.indexOf("(");
  if (parenIndex <= 0) {
    return <>{title}</>;
  }

  const main = title.slice(0, parenIndex).trimEnd();
  const detail = title.slice(parenIndex).trimStart();
  if (!main || !detail) {
    return <>{title}</>;
  }

  return (
    <>
      {main}
      <br aria-hidden="true" />
      {detail}
    </>
  );
}

function formatTravelCost(value: number | null | undefined): string | null {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return null;
  return `약 ${Math.round(value / 10000)}만원`;
}

function formatBestMonths(months: CityData["best_months"]): string | null {
  if (!Array.isArray(months) || months.length === 0) return null;
  return months.slice(0, 3).map((month) => `${month}월`).join("·");
}

// ── Back Face ─────────────────────────────────────────────────────

function BackFace({ isSelected, size }: { isSelected: boolean; size: CardSize }) {
  const cfg = SIZE_CONFIG[size];

  return (
    <div
      className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden pointer-events-none"
      style={{
        borderRadius: 12,
        background: "var(--card)",
        border: isSelected
          ? "2px solid var(--primary)"
          : "1px solid var(--border)",
        boxShadow: isSelected
          ? "0 0 24px 6px var(--ring), 0 0 48px 12px color-mix(in srgb, var(--primary) 15%, transparent)"
          : "0 0 0px 0px transparent",
        transition: "border 0.35s ease, box-shadow 0.45s ease",
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
      }}
    >
      {/* Inset border */}
      <div
        className="absolute pointer-events-none"
        style={{
          inset: 4,
          borderRadius: 8,
          border: isSelected
            ? "1px solid color-mix(in srgb, var(--primary) 30%, transparent)"
            : "1px solid color-mix(in srgb, var(--border) 40%, transparent)",
          transition: "border 0.35s ease",
        }}
      />

      {/* Compass rose */}
      <CompassRose diameter={cfg.compassD} active={isSelected} />

      {/* NNAI */}
      <span
        className="absolute font-mono text-[10px]"
        style={{
          bottom: 16,
          letterSpacing: "0.2em",
          color: isSelected ? "var(--primary)" : "var(--muted-foreground)",
          transition: "color 0.35s ease",
        }}
      >
        NNAI
      </span>
    </div>
  );
}

// ── Front Face ────────────────────────────────────────────────────

function FrontFace({
  cityData,
  size,
  isHovered = false,
}: {
  cityData: CityData;
  size: CardSize;
  isHovered?: boolean;
}) {
  const cfg = SIZE_CONFIG[size];
  const flag = countryFlagEmoji(cityData.country_id);
  const cost = formatTravelCost(cityData.est_cost_krw);
  const bestMonths = formatBestMonths(cityData.best_months);
  const tags = [cityData.vibe, cost, bestMonths].filter(Boolean).slice(0, 3);

  return (
    <div
      className="absolute inset-0 flex flex-col items-center overflow-hidden pointer-events-none"
      style={{
        borderRadius: 12,
        background: "var(--card)",
        border: isHovered
          ? "1px solid color-mix(in srgb, var(--primary) 22%, var(--border))"
          : "1px solid var(--border)",
        padding: cfg.pad,
        backfaceVisibility: "hidden",
        WebkitBackfaceVisibility: "hidden",
        transform: "rotateY(180deg)",
        transition: "border 0.2s ease",
      }}
    >
      {/* Top — compass mini (뒷면 compass rose의 축소 echo) */}
      <CompassRose diameter={cfg.compassMiniD} active={isHovered} />

      {/* Center — flag + city_kr + city/country (flex-1) */}
      <div className="flex-1 flex flex-col items-center justify-center">
        <span className="leading-none" style={{ fontSize: cfg.flag }}>{flag}</span>
        <p
          className="font-serif font-bold text-center leading-tight mt-1.5"
          style={{ fontSize: cfg.cityKr, color: "var(--foreground)" }}
        >
          <CityTitle title={cityData.city_kr} />
        </p>
        <p
          className="font-mono text-center leading-tight mt-0.5"
          style={{ fontSize: cfg.cityEn, color: "var(--muted-foreground)", letterSpacing: "0.03em" }}
        >
          {cityData.city}, {cityData.country_id}
        </p>
        {tags.length > 0 && (
          <div className="mt-3 flex max-w-full flex-wrap justify-center gap-1">
            {tags.map((tag) => (
              <span
                key={tag}
                className="max-w-full truncate px-1.5 py-0.5 font-mono text-[9px]"
                style={{
                  border: "1px solid var(--border)",
                  borderRadius: 9999,
                  color: "var(--muted-foreground)",
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Bottom divider */}
      <div
        style={{
          width: "100%",
          height: 1,
          background: "color-mix(in srgb, var(--border) 40%, transparent)",
        }}
      />

      {/* Bottom — NNAI label (뒷면과 대칭 위치) */}
      <span
        className="font-mono mt-2"
        style={{
          fontSize: cfg.nnaiFs,
          letterSpacing: "0.2em",
          color: isHovered ? "var(--primary)" : "var(--muted-foreground)",
          transition: "color 0.35s ease",
        }}
      >
        NNAI
      </span>
    </div>
  );
}

// ── 540deg exponential flip ───────────────────────────────────────

const FLIP_KEYFRAMES = [0, 180, 360, 450, 540];
const FLIP_TIMES = [0, 0.15, 0.4, 0.7, 1.0];

// ── Main Component ────────────────────────────────────────────────

export default function TarotCard({
  state,
  size = "md",
  cityData,
  isSelected = false,
  isFlipped = false,
  onClick,
}: TarotCardProps) {
  const cfg = SIZE_CONFIG[size];
  const isLocked = state === "locked";
  const isFront = state === "front";
  const [isHovered, setIsHovered] = useState(false);
  const clickable = !!onClick;

  return (
    <motion.div
      className={`relative select-none ${clickable ? "cursor-pointer" : ""}`}
      style={{ perspective: 1200, width: cfg.w, height: cfg.h, borderRadius: 12 }}
      animate={{
        opacity: !isLocked ? 1 : isHovered ? 0.85 : 0.65,
      }}
      whileHover={
        clickable
          ? {
              scale: 1.025,
              boxShadow:
                "0 6px 18px color-mix(in srgb, var(--background) 70%, transparent)",
            }
          : undefined
      }
      transition={{
        opacity: { duration: 0.4, ease: "easeOut" },
        scale: { duration: 0.2, ease: "easeOut" },
        boxShadow: { duration: 0.2, ease: "easeOut" },
      }}
      onHoverStart={() => setIsHovered(true)}
      onHoverEnd={() => setIsHovered(false)}
      onClick={onClick}
    >
      <motion.div
        className="relative w-full h-full pointer-events-none"
        style={{ transformStyle: "preserve-3d" }}
        animate={{ rotateY: isFlipped ? FLIP_KEYFRAMES : 0 }}
        transition={
          isFlipped
            ? { duration: 1.1, times: FLIP_TIMES, ease: ["easeIn", "linear", "easeOut", "easeOut"] }
            : { duration: 0 }
        }
      >
        {/* Back face */}
        <BackFace isSelected={isSelected} size={size} />

        {/* Front face */}
        {cityData ? (
          <FrontFace
            cityData={cityData}
            size={size}
            isHovered={isFront && isHovered}
          />
        ) : (
          <div
            className="absolute inset-0"
            style={{
              borderRadius: 12,
              background: "var(--card)",
              border: "1px solid var(--border)",
              backfaceVisibility: "hidden",
              WebkitBackfaceVisibility: "hidden",
              transform: "rotateY(180deg)",
            }}
          />
        )}
      </motion.div>

      {/* Lock dim */}
      {isLocked && (
        <div
          className="absolute inset-0 flex items-center justify-center pointer-events-none"
          style={{ borderRadius: 12, background: "color-mix(in srgb, var(--card) 60%, transparent)" }}
        >
          <span
            style={{
              fontSize: size === "sm" ? 24 : 32,
              transform: `scale(${isHovered ? 1.08 : 1})`,
              transition: "transform 0.25s ease-out",
              display: "inline-block",
            }}
          >
            🔒
          </span>
        </div>
      )}
    </motion.div>
  );
}
