"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { CityData } from "./types";
import { countryFlagEmoji } from "@/lib/country-flag";

function formatKrw(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) return "확인 중";
  return `약 ${Math.round(value / 10000)}만원`;
}

function formatMonths(months: CityData["best_months"]): string {
  if (!Array.isArray(months) || months.length === 0) return "확인 중";
  return months.map((month) => `${month}월`).join(", ");
}

interface TarotReadingProps {
  cities: CityData[];
  onComplete: () => void;
  onRequestDetail: (cityIndex: number) => void;
}

function useTypingEffect(text: string, speed: number = 50) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);

  useEffect(() => {
    setDisplayed("");
    setDone(false);
    if (!text) {
      setDone(true);
      return;
    }

    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(interval);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return { displayed, done };
}

function CityReading({
  city,
  index,
  onNext,
  isLast,
}: {
  city: CityData;
  index: number;
  onNext: () => void;
  isLast: boolean;
}) {
  const flag = countryFlagEmoji(city.country_id);
  const readingText =
    city.reading_text ??
    city.reasons?.map((reason) => reason.point).filter(Boolean).join(" ") ??
    city.city_description ??
    "";
  const { displayed, done } = useTypingEffect(readingText, 50);

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.4 }}
      className="flex flex-col items-center gap-8 w-full max-w-md mx-auto px-4"
    >
      {/* Card number */}
      <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-muted-foreground">
        Destination {index + 1}
      </span>

      {/* City header */}
      <div className="text-center">
        <span className="text-4xl">{flag}</span>
        <h2 className="font-serif text-2xl font-bold text-foreground mt-2">
          {city.city_kr}
        </h2>
        <p className="font-mono text-sm text-muted-foreground mt-1 tracking-wide">
          {city.city}, {city.country}
        </p>
      </div>

      {/* Reading text with typing effect */}
      {readingText && (
        <div className="w-full border-l-2 border-primary pl-4 min-h-[3rem]">
          <p className="font-serif text-base text-foreground leading-relaxed">
            {displayed}
            {!done && (
              <span className="animate-pulse text-primary">|</span>
            )}
          </p>
        </div>
      )}

      {/* Metrics fade in after typing completes */}
      {done && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.4 }}
          className="w-full flex flex-col gap-3"
        >
          <div className="w-full h-px bg-border" />
          <div className="flex justify-around font-mono text-center">
            <div className="flex flex-col items-center gap-1">
              <span className="text-lg">💰</span>
              <span className="text-xs uppercase tracking-widest text-muted-foreground">
                Budget
              </span>
              <span className="text-sm font-medium text-foreground">
                {formatKrw(city.est_cost_krw)}
              </span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-lg">🗓️</span>
              <span className="text-xs uppercase tracking-widest text-muted-foreground">
                Best
              </span>
              <span className="text-sm font-medium text-foreground">
                {formatMonths(city.best_months)}
              </span>
            </div>
            {city.avg_flight_hours_from_icn != null && (
              <div className="flex flex-col items-center gap-1">
                <span className="text-lg">✈️</span>
                <span className="text-xs uppercase tracking-widest text-muted-foreground">
                  Flight
                </span>
                <span className="text-sm font-medium text-foreground">
                  약 {city.avg_flight_hours_from_icn}시간
                </span>
              </div>
            )}
          </div>
          <div className="w-full h-px bg-border" />
        </motion.div>
      )}

      {/* Next / Complete button */}
      {done && (
        <motion.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.2 }}
          type="button"
          onClick={onNext}
          className="px-8 py-3 text-sm font-semibold bg-primary text-primary-foreground transition-opacity"
        >
          {isLast ? "리딩 완료" : "다음 여행지 →"}
        </motion.button>
      )}
    </motion.div>
  );
}

export default function TarotReading({
  cities,
  onComplete,
  onRequestDetail,
}: TarotReadingProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [readingComplete, setReadingComplete] = useState(false);

  const handleNext = useCallback(() => {
    if (currentIndex < cities.length - 1) {
      setCurrentIndex((prev) => prev + 1);
    } else {
      setReadingComplete(true);
    }
  }, [currentIndex, cities.length]);

  const [toastVisible, setToastVisible] = useState(false);

  function handleGuideClick() {
    setToastVisible(true);
    setTimeout(() => setToastVisible(false), 2500);
  }

  // Reading complete: CTA screen
  if (readingComplete) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="flex flex-col items-center gap-8 w-full max-w-md mx-auto px-4 py-16"
      >
        <h2 className="font-serif text-xl font-bold text-foreground text-center">
          세 장의 카드가 모두 열렸습니다
        </h2>

        <button
          type="button"
          onClick={onComplete}
          className="w-full py-3.5 text-sm font-semibold bg-primary text-primary-foreground transition-opacity"
        >
          여행지 비교 보기 →
        </button>

        <div className="flex flex-col items-center gap-3">
          <p className="text-xs text-muted-foreground">
            이 여행지로 일정을 만들고 싶다면
          </p>
          <button
            type="button"
            onClick={handleGuideClick}
            className="px-6 py-2.5 text-sm font-medium border border-border text-foreground hover:border-primary transition-colors"
          >
            일정 만들기
          </button>
        </div>

        {/* Toast */}
        <AnimatePresence>
          {toastVisible && (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 16 }}
              className="fixed bottom-8 left-1/2 -translate-x-1/2 px-5 py-3 bg-card border border-border text-sm text-foreground"
            >
              곧 오픈될 예정이에요 🔜
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    );
  }

  // Sequential reading
  return (
    <div className="min-h-[80vh] flex items-center justify-center py-16">
      <AnimatePresence mode="wait">
        <CityReading
          key={currentIndex}
          city={cities[currentIndex]}
          index={currentIndex}
          onNext={handleNext}
          isLast={currentIndex === cities.length - 1}
        />
      </AnimatePresence>
    </div>
  );
}
