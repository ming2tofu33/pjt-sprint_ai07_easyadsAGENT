"use client";

import { Cpu, Sparkles, Zap } from "lucide-react";
import type { ImageGenerationEngine } from "@/lib/generation-engine";
import { generationEngineOptions } from "@/lib/generation-engine";
import { ChoiceChip } from "./ChoiceChip";
import styles from "./generate.module.css";

type GenerationEngineSelectorProps = {
  value: ImageGenerationEngine;
  onChange: (engine: ImageGenerationEngine) => void;
};

const icons = {
  gpt_image_2: Sparkles,
  flux2_klein_4b: Zap,
  sd35_large: Cpu
} satisfies Partial<Record<ImageGenerationEngine, typeof Sparkles>>;

export function GenerationEngineSelector({ value, onChange }: GenerationEngineSelectorProps) {
  return (
    <div className={styles.engineGrid} aria-label="이미지 생성 모델 선택">
      {generationEngineOptions.map((option) => {
        const Icon = icons[option.id] ?? Sparkles;
        return (
          <ChoiceChip key={option.id} selected={value === option.id} onClick={() => onChange(option.id)}>
            <Icon size={16} aria-hidden="true" />
            <span className={styles.engineChipText}>
              <strong>{option.label}</strong>
              <small>{option.modelName}</small>
            </span>
          </ChoiceChip>
        );
      })}
    </div>
  );
}
