import React from "react";
import clsx from "clsx";
import Image from "next/image";
import { mascotAssets, type MascotRole } from "@/lib/mascot-assets";
import styles from "./generate.module.css";

type MascotImageProps = {
  role: MascotRole;
  className?: string;
  alt?: string;
  decorative?: boolean;
  priority?: boolean;
};

export function MascotImage({
  role,
  className,
  alt,
  decorative = false,
  priority = false
}: MascotImageProps) {
  const asset = mascotAssets[role];

  return (
    <Image
      src={asset.src}
      width={asset.width}
      height={asset.height}
      alt={decorative ? "" : alt ?? "개떡찰떡 마스코트"}
      aria-hidden={decorative ? "true" : undefined}
      className={clsx(styles.mascotArt, className)}
      draggable={false}
      priority={priority}
    />
  );
}
